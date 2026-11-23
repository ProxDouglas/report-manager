import { i18n, t } from "./i18n.js?v=2";
import { PipelineApi } from "./pipeline-api.js?v=2";
import { PipelineView } from "./pipeline-view.js?v=2";

const Mode = Object.freeze({ SEPARATE: "separate", JOINED: "joined" });
const Decision = Object.freeze({ APPROVE: "approve" });

class PipelineStudio {
  constructor() {
    this.api = new PipelineApi();
    this.view = new PipelineView({
      preview: (id, stepId) => this.api.previewStep(id, stepId),
      revise: (stepId, replacement, revision) => this.revise(stepId, replacement, revision),
    });
    this.files = [];
    this.uploaded = null;
    this.state = null;
    this.busy = false;
    this.configuration = null;
    this.nextAlias = 1;
    this.bindEvents();
    i18n.apply();
  }

  bindEvents() {
    this.view.element("language").addEventListener("change", (event) => {
      i18n.setLanguage(event.target.value);
      const editor = this.view.element("step-json");
      const definition = editor.value;
      const editorOpen = this.view.element("step-editor").open;
      this.renderFiles();
      this.view.renderPipeline(this.state);
      editor.value = definition;
      this.view.element("step-editor").open = editorOpen;
      this.view.setBusy(this.busy, "", this.state);
      this.updateAutonomyHint();
      this.renderLimits();
    });
    this.view.element("pipeline-form").addEventListener("submit", (event) => {
      event.preventDefault();
      this.create();
    });
    this.view.element("csv-files").addEventListener("change", (event) => {
      this.addFiles(event.target.files);
      event.target.value = "";
    });
    const zone = this.view.element("dropzone");
    zone.addEventListener("dragover", (event) => {
      event.preventDefault();
      if (!this.busy && !this.state) zone.classList.add("dragging");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("dragging");
      this.addFiles(event.dataTransfer.files);
    });
    this.view
      .element("new-pipeline")
      .addEventListener("click", () => this.reset());
    this.view
      .element("run-pipeline")
      .addEventListener("click", () => this.run());
    this.view
      .element("refresh-pipeline")
      .addEventListener("click", () => this.refresh());
    for (const button of document.querySelectorAll("[data-decision]")) {
      button.addEventListener("click", () =>
        this.decide(button.dataset.decision),
      );
    }
    this.view
      .element("approve-edited")
      .addEventListener("click", () => this.decide(Decision.APPROVE, true));
    for (const input of document.querySelectorAll('[name="autonomy"]')) {
      input.addEventListener("change", () => this.updateAutonomyHint());
    }
    // Não permitir que soltar um arquivo fora da área navegue para seu conteúdo.
    window.addEventListener("dragover", (event) => event.preventDefault());
    window.addEventListener("drop", (event) => event.preventDefault());
  }

  async start() {
    await this.withBusy(t("Carregando workspace…"), async () => {
      this.configuration = await this.api.configuration();
      this.renderLimits();
    });
  }

  renderLimits() {
    if (!this.configuration) return;
    const limits = this.configuration;
    this.view.text(
      "upload-limits",
      t`Até ${limits.max_files} arquivos · ${this.view.formatSize(limits.max_file_bytes)} por arquivo · ${this.view.formatSize(limits.max_batch_bytes)} no total`,
    );
  }

  addFiles(selected) {
    if (this.busy) return;
    if (this.state) {
      this.view.showError(
        t("Há uma execução nesta tela. Clique em Novo pipeline para anexar outros arquivos."),
      );
      this.view.element("new-pipeline").focus();
      return;
    }
    if (!this.configuration) return;
    this.view.showError("");
    const next = [...this.files];
    for (const file of selected) {
      if (!file.name.toLowerCase().endsWith(".csv")) {
        this.view.showError(t("Selecione apenas arquivos com extensão .csv."));
        return;
      }
      if (!file.size || file.size > this.configuration.max_file_bytes) {
        this.view.showError(
          t("Um arquivo está vazio ou excede o limite de tamanho informado."),
        );
        return;
      }
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      if (next.some((entry) => entry.key === key)) continue;
      next.push({ key, file });
    }
    if (next.length > this.configuration.max_files) {
      this.view.showError(
        t`Selecione no máximo ${this.configuration.max_files} arquivos.`,
      );
      return;
    }
    if (
      next.reduce((sum, entry) => sum + entry.file.size, 0) >
      this.configuration.max_batch_bytes
    ) {
      this.view.showError(
        t("O tamanho total dos arquivos excede o limite informado."),
      );
      return;
    }
    for (const entry of next) {
      if (!entry.alias) entry.alias = `tabela_${this.nextAlias++}`;
    }
    this.files = next;
    this.uploaded = null;
    this.renderFiles();
  }

  renderFiles() {
    this.view.renderFiles(this.files, (key) => {
      if (this.busy || this.state) return;
      this.files = this.files.filter((entry) => entry.key !== key);
      this.uploaded = null;
      this.renderFiles();
    });
  }

  async create() {
    if (this.busy || this.state) return;
    if (!this.configuration) {
      await this.start();
      return;
    }
    if (!this.files.length) {
      this.view.showError(
        t("Adicione pelo menos um arquivo CSV para gerar o pipeline."),
      );
      this.view.element("csv-files").focus();
      return;
    }
    const mode = this.view.element("pipeline-mode").value;
    if (mode === Mode.JOINED && this.files.length < 2) {
      this.view.showError(
        t("Para conectar arquivos por joins, adicione pelo menos dois CSVs."),
      );
      return;
    }
    await this.withBusy(t("Enviando arquivos…"), async () => {
      if (!this.uploaded) this.uploaded = await this.api.upload(this.files);
      this.view.setBusy(true, t("Planejando com os dados autorizados…"), null);
      const datasets = this.uploaded.map((dataset, index) => ({
        alias: this.files[index].alias,
        dataset_id: dataset.dataset_id,
      }));
      const state = await this.api.create({
        datasets,
        language: i18n.language,
        prompt: this.view.element("prompt").value.trim(),
        mode,
        allow_data_sample: this.view.element("allow-data-sample").checked,
        autonomy: document.querySelector('[name="autonomy"]:checked').value,
      });
      this.setState(state);
      this.view
        .element("execution-panel")
        .scrollIntoView({ block: "start", behavior: "smooth" });
    });
  }

  async run() {
    if (!this.state) return;
    await this.withBusy(t("Executando localmente…"), async () => {
      this.setState(await this.api.run(this.state.id));
    });
  }

  async refresh() {
    if (!this.state) return;
    await this.withBusy(t("Atualizando estado…"), async () => {
      this.setState(await this.api.get(this.state.id));
    });
  }

  async decide(action, edited = false) {
    if (this.busy || !this.state?.pending_decision) return;
    const decision = { step_id: this.state.pending_decision.step_id, action };
    if (edited) {
      try {
        decision.replacement = JSON.parse(this.view.element("step-json").value);
      } catch {
        this.view.showError(
          t("O ajuste não é um JSON válido. Revise a definição da etapa."),
        );
        return;
      }
      if (decision.replacement?.id !== decision.step_id) {
        this.view.showError(t("Preserve o id da etapa ao ajustar os parâmetros."));
        return;
      }
    }
    await this.withBusy(t("Aplicando decisão…"), async () => {
      this.setState(await this.api.decide(this.state.id, decision));
      this.view.syncInputs(this.state);
      this.updateAutonomyHint();
    });
  }

  async revise(stepId, replacement, revision) {
    if (this.busy || !this.state) return;
    await this.withBusy(t("Salvando correção…"), async () => {
      this.setState(await this.api.reviseStep(this.state.id, stepId, {
        replacement,
        expected_revision: revision,
      }));
      this.view.syncInputs(this.state);
      this.updateAutonomyHint();
    });
  }

  async withBusy(message, action) {
    if (this.busy) return;
    this.busy = true;
    this.view.showError("");
    this.view.setBusy(true, message, this.state);
    try {
      await action();
    } catch (error) {
      if (error.status === 404 && !this.state) this.uploaded = null;
      this.view.showError(error.message);
    } finally {
      this.busy = false;
      this.view.setBusy(false, "", this.state);
    }
  }

  setState(state) {
    this.state = state;
    this.view.renderPipeline(state);
  }

  updateAutonomyHint() {
    let hint =
      t("Mesmo durante a revisão, você pode delegar uma etapa ou todas as restantes.");
    if (
      document.querySelector('[name="autonomy"]:checked').value === "autonomous"
    ) {
      hint =
        t("Ao executar, você autoriza todas as etapas. Falhas interrompem o fluxo para sua revisão.");
    }
    this.view.text("autonomy-hint", hint);
  }

  reset() {
    if (this.busy) return;
    this.state = null;
    this.files = [];
    this.uploaded = null;
    this.nextAlias = 1;
    this.view.element("pipeline-form").reset();
    this.view.showError("");
    this.renderFiles();
    this.view.renderPipeline(null);
    this.view.setBusy(false, "", null);
    this.updateAutonomyHint();
    this.view.element("csv-files").focus();
  }
}

const studio = new PipelineStudio();
studio.start();
