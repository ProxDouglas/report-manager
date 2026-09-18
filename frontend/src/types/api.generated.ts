/* Generated from the FastAPI OpenAPI document. Do not edit manually. */
export type ApiSchemas = {
  ArtifactResponse: {
    id: string;
    artifact_type: ApiSchemas["ArtifactType"];
    storage_key: string;
    file_name: string;
    content_type: string;
    checksum: string;
    size_bytes: number;
    expires_at: string;
  };
  ArtifactType: "TELA" | "CSV" | "XLSX" | "PDF" | "GRAFICO";
  Body_upload_source_api_v1_sources_upload_post: {
    name: string;
    source_type: ApiSchemas["SourceType"];
    file: string;
    import_config?: string;
  };
  Body_upload_source_version_api_v1_sources__source_id__upload_post: {
    file: string;
    import_config?: string;
  };
  BootstrapRequest: {
    email: string;
    display_name: string;
    password: string;
  };
  CatalogFieldUpdateRequest: {
    classification: ApiSchemas["DataClassification"];
    sensitivity_action: ApiSchemas["SensitivityAction"];
  };
  ChangePasswordRequest: {
    current_password: string;
    new_password: string;
  };
  ConnectionConfig: {
    host: string;
    port: number;
    database: string;
    username: string;
    schema_name?: string | null;
    allowed_tables?: Array<string>;
    tls_verify?: boolean;
  };
  DataClassification: "PUBLICO" | "INTERNO" | "CONFIDENCIAL" | "SENSIVEL" | "SECRETO";
  DestinationCreateRequest: {
    name: string;
    destination_type: ApiSchemas["DestinationType"];
    configuration?: {
    [key: string]: unknown;
  };
    secret_ref?: string | null;
  };
  DestinationResponse: {
    id: string;
    name: string;
    destination_type: ApiSchemas["DestinationType"];
    status: ApiSchemas["DestinationStatus"];
    configuration: {
    [key: string]: unknown;
  };
    secret_ref: string | null;
  };
  DestinationStatus: "ATIVO" | "PAUSADO";
  DestinationStatusRequest: {
    status: ApiSchemas["DestinationStatus"];
  };
  DestinationType: "EMAIL" | "WEBHOOK";
  ExecutionCreateRequest: {
    parameters?: {
    [key: string]: unknown;
  };
    idempotency_key?: string | null;
  };
  ExecutionResponse: {
    id: string;
    report_id: string;
    report_version_id: string;
    status: ApiSchemas["ExecutionStatus"];
    parameters: {
    [key: string]: unknown;
  };
    attempt_count: number;
    started_at: string | null;
    finished_at: string | null;
    error_summary: string | null;
    created_at: string;
    artifacts?: Array<ApiSchemas["ArtifactResponse"]>;
  };
  ExecutionStatus: "CRIADA" | "EM_EXECUCAO" | "SUCESSO" | "CONCLUIDA_COM_ALERTAS" | "FALHA" | "CANCELADA" | "EXPIRADA";
  GrantTargetType: "USUARIO" | "PAPEL" | "ORGANIZACAO";
  HTTPValidationError: {
    detail?: Array<ApiSchemas["ValidationError"]>;
  };
  HealthResponse: {
    status: string;
    service: string;
    environment: string;
    timestamp: string;
  };
  LicenseChangeRequest: {
    reason: string;
  };
  LicenseResponse: {
    id: string;
    status: string;
    starts_on: string;
    ends_on: string | null;
    reason: string | null;
  };
  LlmConfigurationRequest: {
    name: string;
    preset_id: string;
    secret_ref: string;
    reasoning_level?: string | null;
    temperature?: number | null;
    max_tokens?: number | null;
  };
  LlmConfigurationResponse: {
    id: string;
    name: string;
    preset_id: string;
    secret_ref: string;
    reasoning_level: string | null;
    temperature: number | null;
    max_tokens: number | null;
    is_active: boolean;
  };
  LlmProvider: "OPENAI" | "ANTHROPIC" | "DEEPSEEK" | "GEMINI" | "COPILOT";
  LoginRequest: {
    email: string;
    password: string;
  };
  MembershipChangeRequest: {
    role: ApiSchemas["Role"];
    is_active?: boolean;
  };
  MembershipResponse: {
    id: string;
    user_id: string;
    email: string;
    display_name: string;
    role: ApiSchemas["Role"];
    is_active: boolean;
  };
  MessageResponse: {
    message: string;
  };
  OrganizationCreateRequest: {
    name: string;
    slug: string;
    admin_email: string;
    admin_name: string;
    temporary_password: string;
    starts_on?: string | null;
    ends_on?: string | null;
  };
  OrganizationResponse: {
    id: string;
    name: string;
    slug: string;
    status: string;
    license?: ApiSchemas["LicenseResponse"] | null;
  };
  PresetCreateRequest: {
    provider: ApiSchemas["LlmProvider"];
    model_identifier: string;
    name: string;
    capabilities?: {
    [key: string]: unknown;
  };
    reasoning_levels?: Array<string>;
    max_tokens?: number | null;
  };
  PresetResponse: {
    id: string;
    provider: ApiSchemas["LlmProvider"];
    model_identifier: string;
    name: string;
    capabilities: {
    [key: string]: unknown;
  };
    reasoning_levels: Array<string>;
    max_tokens: number | null;
    is_active: boolean;
    last_validated_at: string | null;
  };
  PresetUpdateRequest: {
    name?: string | null;
    capabilities?: {
    [key: string]: unknown;
  } | null;
    reasoning_levels?: Array<string> | null;
    max_tokens?: number | null;
    is_active?: boolean | null;
  };
  ProposalRequest: {
    configuration_id: string;
    objective: string;
    catalog_context?: {
    [key: string]: unknown;
  };
  };
  ProposalResponse: {
    name: string;
    objective?: string | null;
    definition: {
    [key: string]: unknown;
  };
  };
  ReadyReportResponse: {
    execution: ApiSchemas["ExecutionResponse"];
    report_name: string;
    version_number: number;
  };
  ReportCreateRequest: {
    name: string;
    objective?: string | null;
    definition?: {
    [key: string]: unknown;
  };
  };
  ReportGrantCreateRequest: {
    target_type: ApiSchemas["GrantTargetType"];
    target_id: string;
    permission?: string;
  };
  ReportGrantResponse: {
    id: string;
    report_id: string;
    target_type: ApiSchemas["GrantTargetType"];
    target_id: string;
    permission: string;
    created_at: string;
  };
  ReportResponse: {
    id: string;
    name: string;
    objective: string | null;
    status: ApiSchemas["ReportStatus"];
    published_version_id: string | null;
    created_at: string;
    updated_at: string;
  };
  ReportStatus: "RASCUNHO" | "EM_REVISAO" | "PUBLICADO" | "PAUSADO" | "ARQUIVADO";
  ReportUpdateRequest: {
    change_summary: string;
    definition: {
    [key: string]: unknown;
  };
  };
  ReportVersionResponse: {
    id: string;
    report_id: string;
    version_number: number;
    status: ApiSchemas["ReportVersionStatus"];
    definition: {
    [key: string]: unknown;
  };
    change_summary: string | null;
    published_at: string | null;
    created_at: string;
  };
  ReportVersionStatus: "RASCUNHO" | "EM_REVISAO" | "PUBLICADO" | "ARQUIVADO";
  Role: "OPERADOR_PLATAFORMA" | "ADMIN_ORGANIZACAO" | "CRIADOR_RELATORIOS" | "VISUALIZADOR";
  SensitivityAction: "PERMITIR" | "MASCARAR" | "AGREGAR" | "TOKENIZAR" | "BLOQUEAR";
  SessionResponse: {
    user: ApiSchemas["UserResponse"];
    organizations: Array<ApiSchemas["OrganizationResponse"]>;
    active_organization_id: string | null;
    active_role?: ApiSchemas["Role"] | null;
  };
  SourceCreateRequest: {
    name: string;
    source_type: ApiSchemas["SourceType"];
    connection?: ApiSchemas["ConnectionConfig"] | null;
    secret_ref?: string | null;
    import_config?: {
    [key: string]: unknown;
  };
  };
  SourceGrantCreateRequest: {
    target_type: ApiSchemas["GrantTargetType"];
    target_id: string;
    permission?: string;
  };
  SourceGrantResponse: {
    id: string;
    data_source_id: string;
    target_type: ApiSchemas["GrantTargetType"];
    target_id: string;
    permission: string;
    created_at: string;
  };
  SourceResponse: {
    id: string;
    name: string;
    source_type: ApiSchemas["SourceType"];
    status: ApiSchemas["SourceStatus"];
    last_tested_at: string | null;
    last_test_error: string | null;
  };
  SourceStatus: "RASCUNHO" | "ATIVA" | "PAUSADA" | "ERRO" | "REVOGADA";
  SourceTestResponse: {
    success: boolean;
    message: string;
    schema_snapshot?: {
    [key: string]: unknown;
  };
  };
  SourceType: "BANCO_POSTGRESQL" | "BANCO_ORACLE" | "BANCO_SQLSERVER" | "ARQUIVO_CSV" | "ARQUIVO_EXCEL" | "ARQUIVO_JSON";
  SourceVersionResponse: {
    id: string;
    data_source_id: string;
    version_number: number;
    status: string;
    is_latest_valid: boolean;
    file_name: string | null;
    content_type: string | null;
    checksum: string | null;
    schema_snapshot: {
    [key: string]: unknown;
  };
    created_at: string;
  };
  UserCreateRequest: {
    email: string;
    display_name: string;
    temporary_password: string;
    role?: ApiSchemas["Role"];
  };
  UserResponse: {
    id: string;
    email: string;
    display_name: string;
    must_change_password: boolean;
    is_platform_operator: boolean;
    is_active: boolean;
  };
  ValidationError: {
    loc: Array<string | number>;
    msg: string;
    type: string;
  };
}

