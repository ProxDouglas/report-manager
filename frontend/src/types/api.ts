import type { ApiSchemas } from './api.generated'

export type HealthResponse = ApiSchemas['HealthResponse']
export type User = ApiSchemas['UserResponse']
export type License = ApiSchemas['LicenseResponse']
export type Organization = ApiSchemas['OrganizationResponse']
export type Session = Omit<ApiSchemas['SessionResponse'], 'active_role'> & { active_role: string | null }
export type Source = ApiSchemas['SourceResponse']
export type SourceConnection = ApiSchemas['ConnectionConfig']
export type SourceVersion = ApiSchemas['SourceVersionResponse'] & {
  schema_snapshot: {
    row_count?: number
    columns?: Array<{ name: string; type: string; classification: string; action: string }>
  }
}

export type CatalogField = {
  id: string
  name: string
  type: string
  classification: string
  action: string
  confidence: string
  confirmed: boolean
}

export type CatalogObject = {
  object_name: string
  object_type: string
  fields: CatalogField[]
}

export type SourceCatalog = {
  source_id: string
  version_id: string
  version_number: number
  objects: CatalogObject[]
}

export type SourceDiff = {
  source_id: string
  version_id: string
  compare_to_version_id: string | null
  added: string[]
  removed: string[]
  changed: string[]
}

export type SourceGrant = {
  id: string
  data_source_id: string
  target_type: string
  target_id: string
  permission: string
  created_at: string
}

export type Report = ApiSchemas['ReportResponse']
export type ReportVersion = ApiSchemas['ReportVersionResponse']
export type ReportGrant = ApiSchemas['ReportGrantResponse']

export type ReportDiff = {
  report_id: string
  version_id: string
  compare_to_version_id: string | null
  changed_keys: string[]
  current: Record<string, unknown>
  previous: Record<string, unknown>
}

export type Artifact = ApiSchemas['ArtifactResponse']
export type Execution = Omit<ApiSchemas['ExecutionResponse'], 'artifacts'> & { artifacts: Artifact[] }
export type ReadyReport = Omit<ApiSchemas['ReadyReportResponse'], 'execution'> & { execution: Execution }

export type ScreenResult = {
  columns: string[]
  rows: Array<Record<string, unknown>>
  row_count: number
}

export type PlatformOrganization = Organization

export type Membership = ApiSchemas['MembershipResponse']
export type Preset = ApiSchemas['PresetResponse']
export type LlmConfiguration = ApiSchemas['LlmConfigurationResponse']
export type Destination = ApiSchemas['DestinationResponse']

export type AuditEvent = {
  id: string
  action: string
  resource_type: string | null
  resource_id: string | null
  result: string
  correlation_id: string
  details: Record<string, unknown>
  created_at: string
}

export type OperationalAlert = {
  code: string
  severity: string
  message: string
  count?: number
  bytes?: number
  days?: number
}

export type OperationalAlerts = {
  generated_at: string
  alerts: OperationalAlert[]
}
