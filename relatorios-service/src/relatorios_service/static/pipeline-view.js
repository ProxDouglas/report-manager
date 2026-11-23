import { PipelineStepView } from "./pipeline-step-view.js?v=2";
import { i18n, t } from "./i18n.js?v=2";
export const PipelineStatus = Object.freeze({
  READY: "ready",
  AWAITING_DECISION: "awaiting_decision",
  COMPLETED: "completed",
  CANCELLED: "cancelled",
});

const OperationLabel = Object.freeze({
  trim: "Remover espaços",
  null_markers: "Padronizar valores nulos",
  cast: "Converter tipos e formatos",
  drop_nulls: "Remover linhas com nulos",
  deduplicate: "Tratar duplicatas",
  fill_nulls: "Preencher valores nulos",
  select: "Selecionar colunas",
  join: "Conectar conjuntos de dados",
  filter: "Filtrar linhas",
  split_explode: "Separar valores em linhas",
  aggregate: "Agrupar e agregar",
  bucket: "Agrupar valores em faixas",
  extract_measurements: "Separar valores e unidades",
});

const StatusLabel = Object.freeze({
  ready: "Plano pronto",
  awaiting_decision: "Aguardando decisão",
  completed: "Concluído",
  cancelled: "Cancelado",
});

export class PipelineView {
  constructor(handlers) {
    this.steps = new PipelineStepView(this, handlers);
    this.ids = new Map();
    for (const element of document.querySelectorAll("[id]")) {
      this.ids.set(element.id, element);
    }
  }

  element(id) {
    return this.ids.get(id);
  }

  text(id, value) {
    this.element(id).textContent = value;
  }

  node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  icon(name) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("icon");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#i-${name}`);
    svg.append(use);
    return svg;
  }

  formatNumber(value) {
    return new Intl.NumberFormat(i18n.language).format(value);
  }

  formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  showError(message) {
    const notice = this.element("notice");
    notice.hidden = !message;
    notice.textContent = t(message);
    if (message) notice.scrollIntoView({ block: "nearest" });
  }

  renderFiles(files, onRemove) {
    const list = this.element("file-list");
    list.replaceChildren();
    this.text("file-count", t`${files.length} arquivo(s)`);
    for (const entry of files) {
      const row = this.node("li", "file-row");
      const info = this.node("div", "file-info");
      info.append(this.node("span", "file-name", entry.file.name));
      info.append(
        this.node("span", "file-meta", this.formatSize(entry.file.size)),
      );
      const remove = this.node("button", "remove-file");
      remove.type = "button";
      remove.setAttribute("aria-label", t`Remover ${entry.file.name}`);
      remove.append(this.icon("close"));
      remove.addEventListener("click", () => onRemove(entry.key));
      row.append(
        this.icon("file"),
        info,
        this.node("code", "alias-tag", entry.alias),
        remove,
      );
      list.append(row);
    }
  }

  setBusy(busy, message, state) {
    this.element("execution-panel").classList.toggle("is-loading", busy);
    this.element("execution-panel").setAttribute("aria-busy", String(busy));
    this.element("composer-fields").disabled = busy || Boolean(state);
    this.element("create-pipeline").disabled = busy || Boolean(state);
    this.element("new-pipeline").disabled = busy;
    this.element("language").disabled = busy;
    for (const button of this.element("pipeline-content").querySelectorAll(
      "button",
    )) {
      button.disabled = busy;
    }
    if (busy) {
      this.text("compose-status", message);
      this.text("execution-status", message);
      this.text("status-badge", message);
      this.element("status-badge").dataset.status = "loading";
      return;
    }
    if (state) {
      this.text(
        "compose-status",
        t("Anexos bloqueados nesta execução. Clique em Novo pipeline para adicionar outros arquivos."),
      );
      this.renderStatus(state);
    } else {
      this.text(
        "compose-status",
        t("Primeiro, veja o plano. Depois, inicie a execução."),
      );
      this.text("status-badge", t("Aguardando arquivos"));
      this.element("status-badge").removeAttribute("data-status");
      this.text("execution-status", t("Adicione os arquivos para começar."));
    }
  }

  renderStatus(state) {
    const label = t(StatusLabel[state.status] || state.status);
    this.text("status-badge", label);
    this.element("status-badge").dataset.status = state.status;
    this.text(
      "execution-status",
      t`${label}. ${state.next_step} de ${state.plan.steps.length} etapas executadas.`,
    );
  }

  renderPipeline(state) {
    this.element("empty-state").hidden = Boolean(state);
    this.element("pipeline-content").hidden = !state;
    this.renderPhase(state);
    if (!state) return;
    this.renderStatus(state);
    this.text("pipeline-id", state.id);
    this.text("plan-json", JSON.stringify(state.plan, null, 2));
    this.text(
      "step-count",
      t`${state.next_step} de ${state.plan.steps.length} concluídas`,
    );
    this.element("ready-panel").hidden = state.status !== PipelineStatus.READY;
    this.element("pipeline-error").hidden = !state.error;
    this.text("pipeline-error", state.error || "");
    this.renderDecision(state);
    this.renderSteps(state);
    this.renderOutputs(state);
  }

  renderPhase(state) {
    let active = "configure";
    if (state) active = "plan";
    if (state && state.status !== PipelineStatus.READY) active = "execute";
    for (const phase of document.querySelectorAll("[data-phase]")) {
      phase.classList.toggle("active", phase.dataset.phase === active);
      phase.removeAttribute("aria-current");
      if (phase.dataset.phase === active)
        phase.setAttribute("aria-current", "step");
    }
  }

  renderDecision(state) {
    const pending = state.pending_decision;
    this.element("decision-panel").hidden = !pending;
    if (!pending) return;
    const step = state.plan.steps[state.next_step];
    this.text(
      "decision-title",
      t`Etapa ${state.next_step + 1}: ${t(OperationLabel[step.operation])}`,
    );
    this.text("decision-reason", step.reason);
    this.element("step-json").value = JSON.stringify(step, null, 2);
    this.element("step-editor").open = false;
  }

  renderSteps(state) {
    const list = this.element("step-list");
    list.replaceChildren();
    for (const limitation of state.plan.limitations || []) {
      list.append(this.node("li", "field-hint", t`Limitação: ${limitation}`));
    }
    if (!state.plan.steps.length) {
      list.append(
        this.node(
          "li",
          "field-hint",
          t("O plano preserva as entradas sem transformações. Execute para gerar as saídas."),
        ),
      );
    }
    state.plan.steps.forEach((step, index) => {
      const row = this.node("li", "step-item");
      let label = t("Planejada");
      const marker = this.node("span", "step-marker", index + 1);
      if (index < state.next_step) {
        row.classList.add("done");
        marker.replaceChildren(this.icon("check"));
        label = t("Concluída");
      }
      if (state.pending_decision?.step_id === step.id) {
        row.classList.add("pending");
        label = t("Decisão pendente");
      }
      const body = this.node("div", "step-body");
      const heading = this.node("div", "step-header");
      heading.append(
        this.node("strong", "", t(OperationLabel[step.operation])),
        this.node("span", "step-tag", label),
      );
      const parameters = this.node("div", "step-parameters");
      for (const value of this.describeStep(step))
        parameters.append(this.node("code", "", value));
      body.append(heading, this.node("p", "", step.reason), parameters);
      const report = state.reports[index];
      if (report) {
        let actor = t("sistema");
        if (report.decided_by === "supervised") actor = t("você");
        body.append(
          this.node(
            "div",
            "step-report",
            t`${report.input_rows.map((value) => this.formatNumber(value)).join(" + ")} → ${this.formatNumber(report.output_rows)} linhas · decisão: ${actor}`,
          ),
        );
      }
      if (index < state.next_step) body.append(this.steps.render(state, step, state.status !== PipelineStatus.CANCELLED));
      row.append(marker, body);
      list.append(row);
    });
  }

  describeStep(step) {
    if (step.operation === "join") {
      return [
        `${step.left} + ${step.right}`,
        `${step.left_on.join(", ")} ↔ ${step.right_on.join(", ")}`,
        step.how,
        step.cardinality,
      ];
    }
    const items = [step.input];
    if (step.columns) items.push(step.columns.join(", "));
    if (step.column) items.push(step.column);
    if (step.conditions) items.push(JSON.stringify(step.conditions), step.match);
    if (step.separator) items.push(t`separador: ${step.separator}`);
    if (step.group_by) items.push(t`agrupar: ${step.group_by.join(", ")}`);
    if (step.metrics) items.push(JSON.stringify(step.metrics));
    if (step.edges) items.push(JSON.stringify(step.edges), step.labels.join(", "), step.scale);
    if (step.output_column) items.push(t`saída: ${step.output_column}`);
    if (step.target) items.push(step.target);
    if (step.date_format) items.push(step.date_format);
    if (step.number_format === "brazilian") items.push(t("número brasileiro"));
    if (step.errors === "null") items.push(t("inválidos → nulo"));
    if (step.strategy) items.push(step.strategy);
    if (step.keep) items.push(`keep: ${step.keep}`);
    return items;
  }

  renderOutputs(state) {
    this.element("results").hidden = state.status !== PipelineStatus.COMPLETED;
    const list = this.element("output-list");
    list.replaceChildren();
    for (const output of state.outputs) {
      const row = this.node("li", "output-row");
      const info = this.node("div", "output-info");
      info.append(this.node("strong", "", `${output.reference}.csv`));
      info.append(
        this.node(
          "small",
          "",
          t`${this.formatNumber(output.row_count)} linhas · ${output.columns.length} colunas`,
        ),
      );
      const link = this.node("a", "button button-secondary", t("Baixar CSV"));
      link.href = `/datasets/${encodeURIComponent(output.dataset_id)}/csv`;
      link.setAttribute("download", `${output.reference}.csv`);
      link.prepend(this.icon("download"));
      row.append(this.icon("file"), info, link);
      list.append(row);
      const planned = state.plan.charts?.find((chart) => chart.reference === output.reference);
      list.append(this.chartForm(state.id, output, planned));
      if (planned && output.row_count > 0) {
        const chart = this.node("iframe", "pipeline-chart");
        chart.title = t`Gráfico de ${output.reference}`;
        chart.src = `/pipelines/${encodeURIComponent(state.id)}/outputs/${encodeURIComponent(output.reference)}/chart`;
        list.append(chart);
      }
    }
  }

  chartForm(pipelineId, output, planned) {
    const form = this.node("form", "output-row");
    form.method = "get";
    form.action = `/pipelines/${encodeURIComponent(pipelineId)}/outputs/${encodeURIComponent(output.reference)}/chart`;
    form.target = "_blank";
    for (const [name, label] of [["x", t("Eixo X")], ["y", t("Série numérica")], ["chart_type", t("Tipo de gráfico")]]) {
      const field = this.node("label", "", label);
      const select = this.node("select");
      select.name = name;
      let options = output.columns.map((column) => [column, column]);
      if (name === "chart_type") {
        options = [["bar", t("Barras")], ["line", t("Linhas")], ["pie", t("Pizza")], ["scatter", t("Dispersão")]];
      }
      for (const [value, text] of options) {
        const option = this.node("option", "", text);
        option.value = value;
        select.append(option);
      }
      if (planned?.[name]) select.value = planned[name];
      field.append(select);
      form.append(field);
    }
    const button = this.node("button", "button button-secondary", t("Gerar gráfico"));
    button.type = "submit";
    form.append(button);
    return form;
  }

  syncInputs(state) {
    this.element("prompt").value = state.request.prompt || "";
    this.element("pipeline-mode").value = state.request.mode;
    this.element("allow-data-sample").checked = Boolean(state.request.allow_data_sample);
    for (const input of document.querySelectorAll('[name="autonomy"]')) {
      input.checked = input.value === state.request.autonomy;
    }
  }

}
