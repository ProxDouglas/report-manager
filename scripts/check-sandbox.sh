#!/usr/bin/env bash
set -euo pipefail

image_name="${SANDBOX_IMAGE:-report-manager-sandbox:local}"
if ! docker image inspect "$image_name" >/dev/null 2>&1; then
  printf 'Imagem %s não encontrada; execute o build do sandbox antes do check.\n' "$image_name"
  exit 0
fi

SANDBOX_IMAGE="$image_name" PYTHONPATH=backend .venv/bin/python - <<'PY'
from app.core.config import Settings
from app.services.sandbox import DockerSandboxExecutor

settings = Settings(sandbox_image=__import__("os").environ["SANDBOX_IMAGE"])
result = DockerSandboxExecutor(settings).execute(
    "result = [{**row, 'double': row['value'] * 2} for row in data]",
    [{"value": 3}],
)
assert result == [{"value": 3, "double": 6}]
print("sandbox contract: ok")
PY
