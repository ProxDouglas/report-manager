from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from RestrictedPython import compile_restricted

from app.core.config import Settings
from app.core.errors import DomainError


@dataclass(frozen=True)
class PythonPolicyValidator:
    """Valida a política antes que o código alcance o executor Docker."""

    blocked_tokens: tuple[str, ...] = (
        "__import__",
        "import os",
        "import sys",
        "import subprocess",
        "import socket",
        "open(",
        "eval(",
        "exec(",
    )

    def validate(self, source_code: str) -> None:
        if len(source_code) > 100_000:
            raise DomainError("O script excede o tamanho permitido.", "sandbox_policy_rejected")
        lower_code = source_code.lower()
        if any(token in lower_code for token in self.blocked_tokens):
            raise DomainError(
                "O script contém operação bloqueada pela política.", "sandbox_policy_rejected"
            )
        try:
            compile_restricted(source_code, filename="<report-script>", mode="exec")
        except SyntaxError as exc:
            raise DomainError(
                "O script não passou pela validação RestrictedPython.", "sandbox_policy_rejected"
            ) from exc


@dataclass(frozen=True)
class DockerSandboxExecutor:
    settings: Settings
    validator: PythonPolicyValidator = PythonPolicyValidator()

    def execute(self, source_code: str, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.validator.validate(source_code)
        workspace_root = Path(self.settings.sandbox_workspace)
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix="report-manager-", dir=workspace_root))
        workspace.chmod(0o777)
        input_path = workspace / "input.json"
        script_path = workspace / "script.py"
        runner_path = workspace / "runner.py"
        output_path = workspace / "output.json"
        try:
            input_path.write_text(
                json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8"
            )
            script_path.write_text(source_code, encoding="utf-8")
            runner_path.write_text(
                """
import json
import sys

with open(sys.argv[1], encoding="utf-8") as input_file:
    data = json.load(input_file)

namespace = {"data": data}
with open("/workspace/script.py", encoding="utf-8") as source_file:
    source = source_file.read()
exec(compile(source, "<report-script>", "exec"), namespace, namespace)
result = namespace.get("result")
if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
    raise ValueError("result deve ser uma lista de objetos")
with open(sys.argv[2], "w", encoding="utf-8") as output_file:
    json.dump(result, output_file, ensure_ascii=False, default=str)
""".strip(),
                encoding="utf-8",
            )
            command = [
                "docker",
                "run",
                "--rm",
                "--network",
                self.settings.sandbox_network_mode,
                "--cpus",
                str(self.settings.sandbox_cpu_limit),
                "--memory",
                f"{self.settings.sandbox_memory_mb}m",
                "--pids-limit",
                "128",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--read-only",
                "--user",
                "65532:65532",
                "-v",
                f"{workspace}:/workspace:rw",
                self.settings.sandbox_image,
                "python",
                "/workspace/runner.py",
                "/workspace/input.json",
                "/workspace/output.json",
            ]
            try:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.settings.execution_timeout_seconds,
                    env={"PATH": os.environ.get("PATH", "")},
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                raise DomainError(
                    "Executor Docker indisponível ou expirado.", "sandbox_unavailable", 503
                ) from exc
            if result.returncode != 0:
                raise DomainError("O script falhou no sandbox Docker.", "sandbox_execution_failed")
            if not output_path.exists():
                raise DomainError(
                    "O script não produziu um resultado válido.", "sandbox_invalid_output"
                )
            if output_path.stat().st_size > self.settings.execution_max_result_bytes:
                raise DomainError(
                    "O resultado do sandbox excede o tamanho permitido.",
                    "sandbox_invalid_output",
                    413,
                )
            try:
                output = json.loads(output_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise DomainError(
                    "O script produziu JSON inválido.", "sandbox_invalid_output"
                ) from exc
            if not isinstance(output, list) or not all(isinstance(item, dict) for item in output):
                raise DomainError(
                    "O resultado do sandbox deve ser uma lista de objetos.",
                    "sandbox_invalid_output",
                )
            return output
        finally:
            for path in (output_path, runner_path, script_path, input_path):
                path.unlink(missing_ok=True)
            shutil.rmtree(workspace, ignore_errors=True)
