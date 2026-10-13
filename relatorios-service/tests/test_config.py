import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
CONFIG_ENV = {"OPENAI_API_KEY": "test-key", "LLM_MODEL": "test-model"}


def run_python(code: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    # Diretório temporário e ambiente limpo evitam ler o .env do projeto.
    subprocess_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(SRC),
        **env,
    }
    with tempfile.TemporaryDirectory() as directory:
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=directory,
            env=subprocess_env,
            capture_output=True,
            text=True,
            timeout=120,
        )


class ConfigurationLoadingTests(unittest.TestCase):
    def test_importing_services_does_not_read_settings(self):
        result = run_python(
            "import relatorios_service.common.dependencies\n"
            "import relatorios_service.database\n"
            "import relatorios_service.llm\n"
            "import relatorios_service.services.analysis_service\n",
            env={},
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_importing_main_does_not_build_application(self):
        result = run_python("import relatorios_service.main", env={})

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_settings_are_required_when_requested(self):
        result = run_python(
            "from relatorios_service.config import get_settings\n"
            "get_settings()\n",
            env={},
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("openai_api_key", result.stderr)

    def test_audit_log_is_enabled_by_default_in_logs_directory(self):
        result = run_python(
            "from relatorios_service.config import get_settings\n"
            "settings = get_settings()\n"
            "print(settings.audit_log_enabled, settings.audit_log_file)\n",
            env=CONFIG_ENV,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True logs/auditoria.txt")

    def test_audit_log_can_be_disabled_by_environment(self):
        result = run_python(
            "from relatorios_service.config import get_settings\n"
            "print(get_settings().audit_log_enabled)\n",
            env={**CONFIG_ENV, "AUDIT_LOG_ENABLED": "false"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_application_is_built_on_first_access(self):
        result = run_python(
            "from relatorios_service.main import app\n"
            "print(type(app).__name__)\n",
            env=CONFIG_ENV,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "FastAPI")


if __name__ == "__main__":
    unittest.main()
