#!/usr/bin/env bash
set -euo pipefail

base_url="${E2E_BASE_URL:-http://127.0.0.1:5173}"
organization_label="${E2E_ORGANIZATION_LABEL:-}"
email="${E2E_EMAIL:-}"
password="${E2E_PASSWORD:-}"

if [[ -z "${email}" || -z "${password}" ]]; then
  echo "Defina E2E_EMAIL e E2E_PASSWORD para executar o smoke test." >&2
  exit 2
fi

playwright_cli="${PLAYWRIGHT_CLI_BIN:-playwright-cli}"
if ! command -v "${playwright_cli}" >/dev/null 2>&1; then
  fallback="/home/proxsider/.npm/_npx/31e32ef8478fbf80/node_modules/.bin/playwright-cli"
  if [[ -x "${fallback}" ]]; then
    playwright_cli="${fallback}"
  else
    echo "playwright-cli não encontrado. Instale-o ou defina PLAYWRIGHT_CLI_BIN." >&2
    exit 2
  fi
fi

session="report-manager-e2e-$$"
temp_dir="$(mktemp -d)"
browser_executable="${PLAYWRIGHT_MCP_EXECUTABLE_PATH:-}"

cleanup() {
  "${playwright_cli}" --session="${session}" close >/dev/null 2>&1 || true
  rm -rf "${temp_dir}"
}
trap cleanup EXIT

run_cli() {
  if [[ -n "${browser_executable}" ]]; then
    PLAYWRIGHT_MCP_EXECUTABLE_PATH="${browser_executable}" "${playwright_cli}" --session="${session}" "$@"
    return
  fi
  "${playwright_cli}" --session="${session}" "$@"
}

snapshot() {
  run_cli snapshot >"${temp_dir}/snapshot.yml"
}

require_text() {
  local text="$1"
  if ! rg -Fq -- "${text}" "${temp_dir}/snapshot.yml"; then
    echo "Elemento esperado não encontrado: ${text}" >&2
    exit 1
  fi
}

ref_for() {
  local role="$1"
  local name="$2"
  rg -m1 "${role} \"${name}\" .*\[ref=" "${temp_dir}/snapshot.yml" \
    | sed -E 's/.*\[ref=([^]]+)\].*/\1/'
}

run_cli open "${base_url}"
snapshot
require_text "Entrar na plataforma"

email_ref="$(ref_for textbox E-mail)"
password_ref="$(ref_for textbox Senha)"
continue_ref="$(ref_for button Continuar)"
run_cli fill "${email_ref}" "${email}"
run_cli fill "${password_ref}" "${password}"
run_cli click "${continue_ref}"
snapshot

if rg -Fq "Troque sua senha" "${temp_dir}/snapshot.yml"; then
  current_password_ref="$(ref_for textbox 'Senha temporária')"
  new_password_ref="$(ref_for textbox 'Nova senha')"
  change_password_ref="$(ref_for button 'Alterar senha')"
  run_cli fill "${current_password_ref}" "${password}"
  run_cli fill "${new_password_ref}" "${E2E_NEW_PASSWORD:-${password}}"
  run_cli click "${change_password_ref}"
  snapshot
fi

require_text "Painel operacional"

if [[ -n "${organization_label}" ]]; then
  organization_ref="$(ref_for combobox Organização)"
  run_cli select "${organization_ref}" "${organization_label}"
  snapshot
fi

reports_ref="$(ref_for button Relatórios)"
run_cli click "${reports_ref}"
snapshot
require_text "Relatórios"

versions_ref="$(ref_for button Versões)"
if [[ -n "${versions_ref}" ]]; then
  run_cli click "${versions_ref}"
  snapshot
  require_text "Histórico imutável"
  require_text "Versão"
fi

execute_ref="$(ref_for button Executar)"
if [[ -n "${execute_ref}" ]]; then
  run_cli click "${execute_ref}"
  snapshot
  require_text "Execução finalizada"
fi

ready_ref="$(ref_for button 'Relatórios prontos')"
run_cli click "${ready_ref}"
snapshot
require_text "Relatórios prontos"

preview_ref="$(ref_for button Visualizar)"
if [[ -n "${preview_ref}" ]]; then
  run_cli click "${preview_ref}"
  snapshot
  require_text "Visualização em tela"
fi

artifact_ref="$(rg -m1 'button \"[^\"]+\.(csv|xlsx|pdf|json)\" .*\[ref=' "${temp_dir}/snapshot.yml" | sed -E 's/.*\[ref=([^]]+)\].*/\1/')"
if [[ -n "${artifact_ref}" ]]; then
  run_cli click "${artifact_ref}"
fi

echo "Frontend E2E smoke: ok"
