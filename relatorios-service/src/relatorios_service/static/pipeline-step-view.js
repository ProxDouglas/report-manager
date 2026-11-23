import { t } from "./i18n.js?v=2";

export class PipelineStepView {
  constructor(view, handlers) {
    this.view = view;
    this.handlers = handlers;
  }

  render(state, step, allowCorrection) {
    const details = this.view.node("details", "step-result");
    details.append(this.view.node("summary", "", t("Ver resultado da etapa")));
    const content = this.view.node("div", "step-preview");
    details.append(content);
    let loaded = false;
    details.addEventListener("toggle", async () => {
      if (!details.open || loaded) return;
      loaded = true;
      content.textContent = t("Carregando resultado…");
      try {
        const preview = await this.handlers.preview(state.id, step.id);
        this.renderPreview(content, preview, state, step, allowCorrection);
      } catch (error) {
        loaded = false;
        content.textContent = t(error.message);
      }
    });
    return details;
  }

  renderPreview(content, preview, state, step, allowCorrection) {
    content.replaceChildren();
    content.append(this.view.node("p", "field-hint",
      t`Prévia de até 15 linhas · ${this.view.formatNumber(preview.row_count)} linhas no total.`,
    ));
    const scroll = this.view.node("div", "step-table-scroll");
    const table = this.view.node("table", "step-table");
    const caption = this.view.node("caption", "visually-hidden", t`Resultado da etapa ${step.id}`);
    const head = this.view.node("thead");
    const header = this.view.node("tr");
    for (const column of preview.columns) {
      const cell = this.view.node("th", "", column);
      cell.scope = "col";
      header.append(cell);
    }
    head.append(header);
    const body = this.view.node("tbody");
    for (const values of preview.rows) {
      const row = this.view.node("tr");
      for (const value of values) {
        let text = String(value);
        if (value === null) text = "NULL";
        row.append(this.view.node("td", "", text));
      }
      body.append(row);
    }
    table.append(caption, head, body);
    scroll.append(table);
    content.append(scroll);
    if (!preview.row_count) content.append(this.view.node("p", "field-hint", t("Esta etapa não produziu linhas.")));
    const download = this.view.node("a", "button button-secondary", t("Baixar CSV completo da etapa"));
    download.href = `/pipelines/${encodeURIComponent(state.id)}/steps/${encodeURIComponent(step.id)}/csv`;
    download.setAttribute("download", `${step.id}.csv`);
    content.append(download);
    if (allowCorrection) content.append(this.editor(state, step));
  }

  editor(state, step) {
    const details = this.view.node("details", "step-correction");
    details.append(this.view.node("summary", "", t("Corrigir etapa executada")));
    details.append(this.view.node("p", "field-hint", t("Ao salvar, esta etapa e todas as posteriores precisarão ser executadas e aprovadas novamente. As saídas anteriores deixarão de ser exibidas.")));
    const form = this.view.node("form");
    const label = this.view.node("label", "", t("Definição JSON da etapa"));
    const input = this.view.node("textarea");
    input.value = JSON.stringify(step, null, 2);
    input.rows = 10;
    input.spellcheck = false;
    label.append(input);
    const error = this.view.node("p", "field-hint");
    error.setAttribute("role", "alert");
    const save = this.view.node("button", "button button-secondary", t("Salvar correção e revisar novamente"));
    save.type = "submit";
    form.append(label, error, save);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      error.textContent = "";
      let replacement;
      try {
        replacement = JSON.parse(input.value);
      } catch {
        error.textContent = t("O ajuste não é um JSON válido. Revise a definição da etapa.");
        return;
      }
      if (replacement?.id !== step.id) {
        error.textContent = t("Preserve o id da etapa ao ajustar os parâmetros.");
        return;
      }
      await this.handlers.revise(step.id, replacement, state.revision);
    });
    details.append(form);
    return details;
  }
}
