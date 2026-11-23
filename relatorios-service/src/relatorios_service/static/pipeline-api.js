import { t } from "./i18n.js?v=2";
export class PipelineApi {
  async request(path, options = {}) {
    let response;
    try {
      response = await fetch(path, options);
    } catch {
      throw new Error(
        t("Não foi possível conectar ao servidor. Verifique a conexão e tente novamente."),
      );
    }
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(
        t("O servidor retornou uma resposta inesperada. Tente atualizar o estado."),
      );
    }
    if (!response.ok) {
      let message =
        t("Não foi possível concluir a operação. Revise os campos e tente novamente.");
      if (typeof data.detail === "string") message = data.detail;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return data;
  }

  configuration() {
    return this.request("/ui/config");
  }

  async upload(files) {
    const body = new FormData();
    for (const entry of files) body.append("files", entry.file);
    const result = await this.request("/datasets/batch", {
      method: "POST",
      body,
    });
    return result.datasets;
  }

  post(path, payload) {
    return this.request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  create(request) {
    return this.post("/pipelines", request);
  }

  stepPath(id, stepId) {
    return `/pipelines/${encodeURIComponent(id)}/steps/${encodeURIComponent(stepId)}`;
  }

  previewStep(id, stepId) {
    return this.request(`${this.stepPath(id, stepId)}/preview`);
  }

  reviseStep(id, stepId, revision) {
    return this.request(this.stepPath(id, stepId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(revision),
    });
  }

  get(id) {
    return this.request(`/pipelines/${encodeURIComponent(id)}`);
  }

  run(id) {
    return this.post(`/pipelines/${encodeURIComponent(id)}/run`, {});
  }

  decide(id, decision) {
    return this.post(
      `/pipelines/${encodeURIComponent(id)}/decisions`,
      decision,
    );
  }
}
