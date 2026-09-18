import { useEffect, useMemo, useState } from 'react'

import { StatusCard } from './components/StatusCard'
import { StatusBadge } from './components/ui'
import {
  ApiError,
  bootstrapOperator,
  changeOrganizationLicense,
  changePassword,
  createDestination,
  createLlmConfiguration,
  createPreset,
  createMember,
  createOrganization,
  createReport,
  createReportGrant,
  createReportVersion,
  createSource,
  downloadArtifact,
  deactivatePreset,
  executeReport,
  getSourceCatalog,
  getSourceVersionDiff,
  getExecution,
  getArtifactPreview,
  getHealth,
  getReportVersionDiff,
  getSession,
  listAuditEvents,
  listDestinations,
  listLlmConfigurations,
  listOperatorPresets,
  listMembers,
  listOrganizations,
  listPresets,
  listReadyReports,
  listReportGrants,
  listReportVersions,
  listReports,
  listSourceVersions,
  listSources,
  login,
  logout,
  proposeReport,
  publishReportVersion,
  selectOrganization,
  testSource,
  updateCatalogField,
  updateMember,
  uploadSource,
} from './lib/api'
import type {
  AuditEvent,
  Destination,
  HealthResponse,
  LlmConfiguration,
  Membership,
  Organization,
  Preset,
  Report,
  ReportDiff,
  ReportGrant,
  ReportVersion,
  ReadyReport,
  Session,
  Source,
  SourceCatalog,
  SourceDiff,
  SourceVersion,
  ScreenResult,
} from './types/api'

type View = 'overview' | 'sources' | 'reports' | 'ready' | 'users' | 'llm' | 'delivery' | 'audit' | 'operator'

const sourceTypes = [
  { value: 'ARQUIVO_CSV', label: 'CSV' },
  { value: 'ARQUIVO_EXCEL', label: 'Excel' },
  { value: 'ARQUIVO_JSON', label: 'JSON' },
]

const databaseSourceTypes = [
  { value: 'BANCO_POSTGRESQL', label: 'PostgreSQL' },
  { value: 'BANCO_ORACLE', label: 'Oracle Database' },
  { value: 'BANCO_SQLSERVER', label: 'Microsoft SQL Server' },
]

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [organizationId, setOrganizationId] = useState('')
  const [view, setView] = useState<View>('overview')
  const [sources, setSources] = useState<Source[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [readyReports, setReadyReports] = useState<ReadyReport[]>([])
  const [screenPreview, setScreenPreview] = useState<ScreenResult | null>(null)
  const [selectedReport, setSelectedReport] = useState<Report | null>(null)
  const [versions, setVersions] = useState<ReportVersion[]>([])
  const [reportDiff, setReportDiff] = useState<ReportDiff | null>(null)
  const [grants, setGrants] = useState<ReportGrant[]>([])
  const [grantTargetType, setGrantTargetType] = useState('PAPEL')
  const [grantTargetId, setGrantTargetId] = useState('VISUALIZADOR')
  const [grantPermission, setGrantPermission] = useState('VIEW')
  const [definitionText, setDefinitionText] = useState('{}')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [loginMode, setLoginMode] = useState<'login' | 'bootstrap'>('login')
  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [sourceName, setSourceName] = useState('')
  const [sourceType, setSourceType] = useState('ARQUIVO_CSV')
  const [sourceFile, setSourceFile] = useState<File | null>(null)
  const [sourceMode, setSourceMode] = useState<'file' | 'database'>('file')
  const [databaseSourceType, setDatabaseSourceType] = useState('BANCO_POSTGRESQL')
  const [databaseHost, setDatabaseHost] = useState('')
  const [databasePort, setDatabasePort] = useState('5432')
  const [databaseName, setDatabaseName] = useState('')
  const [databaseUser, setDatabaseUser] = useState('')
  const [databaseSchema, setDatabaseSchema] = useState('')
  const [databaseSecretRef, setDatabaseSecretRef] = useState('env://SOURCE_PASSWORD')
  const [databaseAllowedTables, setDatabaseAllowedTables] = useState('')
  const [selectedSource, setSelectedSource] = useState<Source | null>(null)
  const [sourceCatalog, setSourceCatalog] = useState<SourceCatalog | null>(null)
  const [sourceVersions, setSourceVersions] = useState<SourceVersion[]>([])
  const [sourceDiff, setSourceDiff] = useState<SourceDiff | null>(null)
  const [reportName, setReportName] = useState('')
  const [reportObjective, setReportObjective] = useState('')
  const [reportSourceId, setReportSourceId] = useState('')
  const [reportFields, setReportFields] = useState('')
  const [reportGroupBy, setReportGroupBy] = useState('')
  const [reportMetricField, setReportMetricField] = useState('')
  const [reportQuery, setReportQuery] = useState('')
  const [organizationName, setOrganizationName] = useState('')
  const [organizationSlug, setOrganizationSlug] = useState('')
  const [adminEmail, setAdminEmail] = useState('')
  const [adminName, setAdminName] = useState('')
  const [temporaryPassword, setTemporaryPassword] = useState('')
  const [platformOrganizations, setPlatformOrganizations] = useState<Organization[]>([])
  const [members, setMembers] = useState<Membership[]>([])
  const [memberEmail, setMemberEmail] = useState('')
  const [memberName, setMemberName] = useState('')
  const [memberPassword, setMemberPassword] = useState('')
  const [memberRole, setMemberRole] = useState('VISUALIZADOR')
  const [presets, setPresets] = useState<Preset[]>([])
  const [operatorPresets, setOperatorPresets] = useState<Preset[]>([])
  const [llmConfigurations, setLlmConfigurations] = useState<LlmConfiguration[]>([])
  const [llmName, setLlmName] = useState('')
  const [llmPresetId, setLlmPresetId] = useState('')
  const [llmSecretRef, setLlmSecretRef] = useState('env://CLIENT_LLM_API_KEY')
  const [llmReasoning, setLlmReasoning] = useState('')
  const [llmTemperature, setLlmTemperature] = useState('0.2')
  const [proposalObjective, setProposalObjective] = useState('')
  const [proposalConfigurationId, setProposalConfigurationId] = useState('')
  const [proposalText, setProposalText] = useState('')
  const [destinations, setDestinations] = useState<Destination[]>([])
  const [destinationName, setDestinationName] = useState('')
  const [destinationRecipients, setDestinationRecipients] = useState('')
  const [destinationWebhookUrl, setDestinationWebhookUrl] = useState('')
  const [destinationSecretRef, setDestinationSecretRef] = useState('env://WEBHOOK_SECRET')
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])

  useEffect(() => {
    const initialize = async () => {
      getHealth().then(setHealth).catch(() => setHealth(null))
      try {
        const nextSession = await getSession()
        setSession(nextSession)
        const firstOrganization = nextSession.active_organization_id ?? nextSession.organizations[0]?.id ?? ''
        setOrganizationId(firstOrganization)
        await refreshWorkspace(firstOrganization)
      } catch {
        return
      }
    }
    void initialize()
  }, [])

  const currentOrganization = useMemo<Organization | null>(() => {
    if (!session) {
      return null
    }
    return session.organizations.find((organization) => organization.id === organizationId) ?? null
  }, [organizationId, session])

  const refreshWorkspace = async (nextOrganizationId: string) => {
    if (!nextOrganizationId) {
      return
    }
    setLoading(true)
    try {
      const [nextSources, nextReports, nextReadyReports] = await Promise.all([
        listSources(nextOrganizationId),
        listReports(nextOrganizationId),
        listReadyReports(nextOrganizationId),
      ])
      setSources(nextSources)
      setReports(nextReports)
      setReadyReports(nextReadyReports)
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      let nextSession: Session
      if (loginMode === 'bootstrap') {
        nextSession = await bootstrapOperator(email, displayName, password)
      } else {
        nextSession = await login(email, password)
      }
      setSession(nextSession)
      const firstOrganization = nextSession.active_organization_id ?? nextSession.organizations[0]?.id ?? ''
      setOrganizationId(firstOrganization)
      setMessage('Sessão iniciada.')
      await refreshWorkspace(firstOrganization)
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordChange = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      const nextSession = await changePassword(currentPassword, newPassword)
      setSession(nextSession)
      setMessage('Senha alterada. A plataforma está liberada.')
      setCurrentPassword('')
      setNewPassword('')
      await refreshWorkspace(organizationId)
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleOrganizationChange = async (nextOrganizationId: string) => {
    setError('')
    setLoading(true)
    try {
      const nextSession = await selectOrganization(nextOrganizationId)
      setSession(nextSession)
      setOrganizationId(nextOrganizationId)
      await refreshWorkspace(nextOrganizationId)
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    await logout().catch(() => undefined)
    setSession(null)
    setOrganizationId('')
    setSources([])
    setReports([])
    setReadyReports([])
    setScreenPreview(null)
  }

  const handleUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!sourceFile || !organizationId) {
      setError('Selecione uma organização e um arquivo.')
      return
    }
    setError('')
    setLoading(true)
    try {
      await uploadSource(organizationId, sourceName, sourceType, sourceFile)
      await refreshWorkspace(organizationId)
      setMessage('Fonte validada e nova versão criada.')
      setSourceFile(null)
      setSourceName('')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleCreateDatabaseSource = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!organizationId) {
      setError('Selecione uma organização.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const source = await createSource(organizationId, {
        name: sourceName,
        source_type: databaseSourceType,
        secret_ref: databaseSecretRef,
        connection: {
          host: databaseHost,
          port: Number(databasePort),
          database: databaseName,
          username: databaseUser,
          schema_name: databaseSchema || undefined,
          allowed_tables: splitValues(databaseAllowedTables),
          tls_verify: true,
        },
      })
      await testSource(organizationId, source.id)
      await refreshWorkspace(organizationId)
      setMessage('Fonte de banco criada e conexão validada.')
      clearDatabaseSourceForm()
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const clearDatabaseSourceForm = () => {
    setSourceName('')
    setDatabaseHost('')
    setDatabaseName('')
    setDatabaseUser('')
    setDatabaseSchema('')
    setDatabaseAllowedTables('')
  }

  const handleOpenSource = async (source: Source) => {
    setSelectedSource(source)
    setError('')
    try {
      const [catalog, nextVersions] = await Promise.all([
        getSourceCatalog(organizationId, source.id),
        listSourceVersions(organizationId, source.id),
      ])
      setSourceCatalog(catalog)
      setSourceVersions(nextVersions)
      setSourceDiff(null)
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleSourceDiff = async (versionId: string) => {
    if (!selectedSource) {
      return
    }
    try {
      setSourceDiff(await getSourceVersionDiff(organizationId, selectedSource.id, versionId))
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleCatalogFieldChange = async (sourceId: string, fieldId: string, classification: string, sensitivityAction: string) => {
    try {
      await updateCatalogField(organizationId, sourceId, fieldId, classification, sensitivityAction)
      const source = sources.find((item) => item.id === sourceId)
      if (source) {
        await handleOpenSource(source)
      }
      setMessage('Classificação do campo atualizada.')
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const loadOperatorOrganizations = async () => {
    try {
      setPlatformOrganizations(await listOrganizations())
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const loadOperatorPresets = async () => {
    try {
      setOperatorPresets(await listOperatorPresets())
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const loadOrganizationUsers = async () => {
    try {
      setMembers(await listMembers(organizationId))
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const loadLlm = async () => {
    try {
      const [nextPresets, nextConfigurations] = await Promise.all([
        listPresets(organizationId),
        listLlmConfigurations(organizationId),
      ])
      setPresets(nextPresets)
      setLlmConfigurations(nextConfigurations)
      if (!llmPresetId) {
        setLlmPresetId(nextPresets[0]?.id ?? '')
      }
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const loadDestinations = async () => {
    try {
      setDestinations(await listDestinations(organizationId))
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const loadAudit = async () => {
    try {
      setAuditEvents(await listAuditEvents(organizationId))
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleViewChange = (nextView: View) => {
    setView(nextView)
    if (!organizationId) {
      if (nextView === 'operator') {
        void loadOperatorOrganizations()
        void loadOperatorPresets()
      }
      return
    }
    if (nextView === 'users') {
      void loadOrganizationUsers()
    }
    if (nextView === 'llm') {
      void loadLlm()
    }
    if (nextView === 'delivery') {
      void loadDestinations()
    }
    if (nextView === 'audit') {
      void loadAudit()
    }
  }

  const handleLicenseChange = async (organization: Organization, action: 'suspend' | 'reactivate') => {
    setLoading(true)
    setError('')
    try {
      let reason = 'Licença reativada pelo operador'
      if (action === 'suspend') {
        reason = 'Ação manual do operador'
      }
      await changeOrganizationLicense(organization.id, action, reason)
      await loadOperatorOrganizations()
      if (action === 'suspend') {
        setMessage('Licença suspensa.')
      } else {
        setMessage('Licença reativada.')
      }
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleCreatePreset = async (payload: { provider: string; model_identifier: string; name: string; reasoning_levels: string[] }) => {
    try {
      await createPreset({ ...payload, capabilities: { reasoning_effort: payload.reasoning_levels }, max_tokens: 4096 })
      await loadOperatorPresets()
      setMessage('Preset criado.')
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleDeactivatePreset = async (preset: Preset) => {
    try {
      await deactivatePreset(preset.id)
      await loadOperatorPresets()
      setMessage(`Preset ${preset.name} desativado.`)
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleCreateMember = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await createMember(organizationId, {
        email: memberEmail,
        display_name: memberName,
        temporary_password: memberPassword,
        role: memberRole,
      })
      await loadOrganizationUsers()
      setMessage('Usuário criado com troca obrigatória de senha.')
      setMemberEmail('')
      setMemberName('')
      setMemberPassword('')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleMemberChange = async (member: Membership, role: string, isActive: boolean) => {
    setError('')
    try {
      await updateMember(organizationId, member.id, { role, is_active: isActive })
      await loadOrganizationUsers()
      setMessage('Membership atualizado.')
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleCreateLlmConfiguration = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await createLlmConfiguration(organizationId, {
        name: llmName,
        preset_id: llmPresetId,
        secret_ref: llmSecretRef,
        reasoning_level: llmReasoning || undefined,
        temperature: Number(llmTemperature),
      })
      await loadLlm()
      setMessage('Configuração BYOK criada sem armazenar a API key.')
      setLlmName('')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleProposal = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const proposal = await proposeReport(organizationId, {
        configuration_id: proposalConfigurationId,
        objective: proposalObjective,
        catalog_context: sourceCatalog ?? {},
      })
      setProposalText(JSON.stringify(proposal, null, 2))
      setMessage('Proposta recebida. Revise e confirme antes de salvar ou executar.')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleCreateDestination = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const isEmail = destinationRecipients.trim().length > 0
      let payload: {
        name: string
        destination_type: string
        configuration: Record<string, unknown>
        secret_ref?: string
      }
      if (isEmail) {
        payload = {
          name: destinationName,
          destination_type: 'EMAIL',
          configuration: { recipients: splitValues(destinationRecipients), artifact_type: 'PDF' },
        }
      } else {
        payload = {
          name: destinationName,
          destination_type: 'WEBHOOK',
          configuration: { url: destinationWebhookUrl, artifact_type: 'CSV' },
          secret_ref: destinationSecretRef,
        }
      }
      await createDestination(organizationId, payload)
      await loadDestinations()
      setMessage('Destino criado.')
      setDestinationName('')
      setDestinationRecipients('')
      setDestinationWebhookUrl('')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const reportDefinition = () => {
    const fields = splitValues(reportFields)
    const groupBy = splitValues(reportGroupBy)
    const definition: Record<string, unknown> = {
      source_id: reportSourceId,
      fields,
      group_by: groupBy,
      metrics: reportMetricField ? [{ name: `total_${reportMetricField}`, field: reportMetricField, operation: 'sum' }] : [],
      formats: ['TELA', 'CSV', 'XLSX', 'PDF'],
    }
    if (reportQuery.trim()) {
      definition.query = reportQuery.trim()
    }
    if (groupBy.length > 0 && reportMetricField) {
      definition.chart = { type: 'bar', x: groupBy[0], y: `total_${reportMetricField}` }
    }
    return definition
  }

  const handleCreateReport = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!organizationId || !reportSourceId) {
      setError('Selecione a organização e a fonte do relatório.')
      return
    }
    setError('')
    setLoading(true)
    try {
      await createReport(organizationId, reportName, reportObjective, reportDefinition())
      await refreshWorkspace(organizationId)
      setMessage('Relatório criado como rascunho. Publique uma versão para executá-lo.')
      setReportName('')
      setReportObjective('')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const openReport = async (report: Report) => {
    setSelectedReport(report)
    setError('')
    try {
      const [nextVersions, nextGrants] = await Promise.all([
        listReportVersions(organizationId, report.id),
        listReportGrants(organizationId, report.id),
      ])
      setVersions(nextVersions)
      setGrants(nextGrants)
      setDefinitionText(JSON.stringify(nextVersions[0]?.definition ?? {}, null, 2))
      setReportDiff(null)
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleReportDiff = async (versionId: string) => {
    if (!selectedReport) {
      return
    }
    try {
      setReportDiff(await getReportVersionDiff(organizationId, selectedReport.id, versionId))
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handlePublish = async (version: ReportVersion) => {
    if (!selectedReport) {
      return
    }
    setLoading(true)
    try {
      await publishReportVersion(organizationId, selectedReport.id, version.id)
      await refreshWorkspace(organizationId)
      const nextVersions = await listReportVersions(organizationId, selectedReport.id)
      setVersions(nextVersions)
      setMessage(`Versão ${version.version_number} publicada.`)
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleCreateVersion = async () => {
    if (!selectedReport) {
      return
    }
    try {
      const definition = JSON.parse(definitionText) as Record<string, unknown>
      const nextVersion = await createReportVersion(organizationId, selectedReport.id, 'Alteração criada pelo editor.', definition)
      const nextVersions = await listReportVersions(organizationId, selectedReport.id)
      setVersions(nextVersions)
      setDefinitionText(JSON.stringify(nextVersion.definition, null, 2))
      await refreshWorkspace(organizationId)
      setMessage(`Rascunho da versão ${nextVersion.version_number} criado. A versão publicada anterior foi preservada.`)
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  const handleCreateGrant = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedReport) {
      return
    }
    setLoading(true)
    setError('')
    try {
      await createReportGrant(organizationId, selectedReport.id, {
        target_type: grantTargetType,
        target_id: grantTargetId,
        permission: grantPermission,
      })
      setGrants(await listReportGrants(organizationId, selectedReport.id))
      setMessage('Acesso do relatório atualizado.')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async (report: Report) => {
    setLoading(true)
    setError('')
    try {
      const createdExecution = await executeReport(organizationId, report.id)
      let currentExecution = createdExecution
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await delay(500)
        currentExecution = await getExecution(organizationId, createdExecution.id)
        if (['SUCESSO', 'FALHA', 'CANCELADA'].includes(currentExecution.status)) {
          break
        }
      }
      await refreshWorkspace(organizationId)
      setMessage(`Execução finalizada com status ${currentExecution.status}.`)
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handleCreateOrganization = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      await createOrganization({ name: organizationName, slug: organizationSlug, admin_email: adminEmail, admin_name: adminName, temporary_password: temporaryPassword })
      const nextSession = await getSession()
      setSession(nextSession)
      setMessage('Cliente criado com usuário administrador e troca obrigatória de senha.')
      setOrganizationName('')
      setOrganizationSlug('')
      setAdminEmail('')
      setAdminName('')
      setTemporaryPassword('')
    } catch (requestError) {
      setError(readError(requestError))
    } finally {
      setLoading(false)
    }
  }

  const handlePreviewArtifact = async (artifactId: string) => {
    try {
      setScreenPreview(await getArtifactPreview(organizationId, artifactId))
    } catch (requestError) {
      setError(readError(requestError))
    }
  }

  if (!session) {
    return <LoginPanel loginMode={loginMode} setLoginMode={setLoginMode} email={email} setEmail={setEmail} displayName={displayName} setDisplayName={setDisplayName} password={password} setPassword={setPassword} error={error} loading={loading} onSubmit={handleLogin} health={health} />
  }

  if (session.user.must_change_password) {
    return <PasswordChangePanel currentPassword={currentPassword} setCurrentPassword={setCurrentPassword} newPassword={newPassword} setNewPassword={setNewPassword} error={error} loading={loading} onSubmit={handlePasswordChange} />
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col md:flex-row">
        <Sidebar view={view} setView={handleViewChange} user={session.user.display_name} onLogout={handleLogout} isOperator={session.user.is_platform_operator} role={session.active_role} />
        <section className="min-w-0 flex-1 bg-slate-50 text-slate-900">
          <header className="flex flex-col gap-4 border-b border-slate-200 bg-white px-6 py-5 md:flex-row md:items-center md:justify-between">
            <div><p className="text-sm font-semibold uppercase tracking-[0.2em] text-brand-600">Report Manager</p><h1 className="mt-1 text-2xl font-bold">Painel operacional</h1></div>
            <div className="flex flex-wrap items-center gap-3"><label className="text-sm text-slate-500" htmlFor="organization">Organização</label><select id="organization" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" value={organizationId} onChange={(event) => void handleOrganizationChange(event.target.value)}><option value="">Selecione</option>{session.organizations.map((organization) => <option key={organization.id} value={organization.id}>{organization.name}</option>)}</select><span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">{currentOrganization?.license?.status ?? 'Operador'}</span></div>
          </header>
          <div className="space-y-6 p-6">
            {message && <Notice tone="success" onClose={() => setMessage('')}>{message}</Notice>}
            {error && <Notice tone="error" onClose={() => setError('')}>{error}</Notice>}
            {loading && <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">Processando operação...</div>}
            {!organizationId && session.user.is_platform_operator && <div className="space-y-6"><OrganizationPanel organizationName={organizationName} setOrganizationName={setOrganizationName} organizationSlug={organizationSlug} setOrganizationSlug={setOrganizationSlug} adminEmail={adminEmail} setAdminEmail={setAdminEmail} adminName={adminName} setAdminName={setAdminName} temporaryPassword={temporaryPassword} setTemporaryPassword={setTemporaryPassword} onSubmit={handleCreateOrganization} /><OperatorPanel organizations={platformOrganizations} onRefresh={() => void loadOperatorOrganizations()} onChangeLicense={(organization, action) => void handleLicenseChange(organization, action)} /><OperatorPresetPanel presets={operatorPresets} onCreate={handleCreatePreset} onDeactivate={handleDeactivatePreset} /></div>}
            {view === 'operator' && session.user.is_platform_operator && <div className="space-y-6"><OperatorPanel organizations={platformOrganizations} onRefresh={() => void loadOperatorOrganizations()} onChangeLicense={(organization, action) => void handleLicenseChange(organization, action)} /><OperatorPresetPanel presets={operatorPresets} onCreate={handleCreatePreset} onDeactivate={handleDeactivatePreset} /></div>}
            {organizationId && view === 'overview' && <Overview health={health} sources={sources} reports={reports} readyReports={readyReports} onRefresh={() => void refreshWorkspace(organizationId)} />}
            {organizationId && view === 'sources' && <SourcesView sources={sources} sourceName={sourceName} setSourceName={setSourceName} sourceType={sourceType} setSourceType={setSourceType} sourceFile={sourceFile} setSourceFile={setSourceFile} onSubmit={handleUpload} sourceMode={sourceMode} setSourceMode={setSourceMode} databaseSourceType={databaseSourceType} setDatabaseSourceType={setDatabaseSourceType} databaseHost={databaseHost} setDatabaseHost={setDatabaseHost} databasePort={databasePort} setDatabasePort={setDatabasePort} databaseName={databaseName} setDatabaseName={setDatabaseName} databaseUser={databaseUser} setDatabaseUser={setDatabaseUser} databaseSchema={databaseSchema} setDatabaseSchema={setDatabaseSchema} databaseSecretRef={databaseSecretRef} setDatabaseSecretRef={setDatabaseSecretRef} databaseAllowedTables={databaseAllowedTables} setDatabaseAllowedTables={setDatabaseAllowedTables} onCreateDatabase={handleCreateDatabaseSource} selectedSource={selectedSource} catalog={sourceCatalog} versions={sourceVersions} sourceDiff={sourceDiff} onDiff={(versionId) => void handleSourceDiff(versionId)} onOpenSource={(source) => void handleOpenSource(source)} onFieldChange={(fieldId, classification, action) => selectedSource && void handleCatalogFieldChange(selectedSource.id, fieldId, classification, action)} />}
            {organizationId && view === 'reports' && <ReportsView reports={reports} sources={sources} reportName={reportName} setReportName={setReportName} reportObjective={reportObjective} setReportObjective={setReportObjective} reportSourceId={reportSourceId} setReportSourceId={setReportSourceId} reportFields={reportFields} setReportFields={setReportFields} reportGroupBy={reportGroupBy} setReportGroupBy={setReportGroupBy} reportMetricField={reportMetricField} setReportMetricField={setReportMetricField} reportQuery={reportQuery} setReportQuery={setReportQuery} onCreate={handleCreateReport} onOpen={openReport} onExecute={handleExecute} selectedReport={selectedReport} versions={versions} reportDiff={reportDiff} onDiff={(versionId) => void handleReportDiff(versionId)} definitionText={definitionText} setDefinitionText={setDefinitionText} onPublish={handlePublish} onCreateVersion={() => void handleCreateVersion()} grants={grants} grantTargetType={grantTargetType} setGrantTargetType={setGrantTargetType} grantTargetId={grantTargetId} setGrantTargetId={setGrantTargetId} grantPermission={grantPermission} setGrantPermission={setGrantPermission} onCreateGrant={handleCreateGrant} />}
            {organizationId && view === 'ready' && <ReadyReportsView reports={readyReports} organizationId={organizationId} preview={screenPreview} onPreview={(artifactId) => void handlePreviewArtifact(artifactId)} onClosePreview={() => setScreenPreview(null)} onDownload={(artifactId, fileName) => downloadArtifact(organizationId, artifactId, fileName).catch((requestError) => setError(readError(requestError)))} />}
            {organizationId && view === 'users' && <UsersView members={members} memberEmail={memberEmail} setMemberEmail={setMemberEmail} memberName={memberName} setMemberName={setMemberName} memberPassword={memberPassword} setMemberPassword={setMemberPassword} memberRole={memberRole} setMemberRole={setMemberRole} onSubmit={handleCreateMember} onChange={handleMemberChange} />}
            {organizationId && view === 'llm' && <LlmView presets={presets} configurations={llmConfigurations} name={llmName} setName={setLlmName} presetId={llmPresetId} setPresetId={setLlmPresetId} secretRef={llmSecretRef} setSecretRef={setLlmSecretRef} reasoning={llmReasoning} setReasoning={setLlmReasoning} temperature={llmTemperature} setTemperature={setLlmTemperature} onSubmit={handleCreateLlmConfiguration} objective={proposalObjective} setObjective={setProposalObjective} proposalConfigurationId={proposalConfigurationId} setProposalConfigurationId={setProposalConfigurationId} proposalText={proposalText} onProposal={handleProposal} />}
            {organizationId && view === 'delivery' && <DeliveryView destinations={destinations} name={destinationName} setName={setDestinationName} recipients={destinationRecipients} setRecipients={setDestinationRecipients} webhookUrl={destinationWebhookUrl} setWebhookUrl={setDestinationWebhookUrl} secretRef={destinationSecretRef} setSecretRef={setDestinationSecretRef} onSubmit={handleCreateDestination} />}
            {organizationId && view === 'audit' && <AuditView events={auditEvents} onRefresh={() => void loadAudit()} />}
          </div>
        </section>
      </div>
    </main>
  )
}

function readError(requestError: unknown): string {
  if (requestError instanceof ApiError) {
    return requestError.message
  }
  if (requestError instanceof Error) {
    return requestError.message
  }
  return 'Não foi possível concluir a operação.'
}

function splitValues(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

function LoginPanel(props: { loginMode: 'login' | 'bootstrap'; setLoginMode: (value: 'login' | 'bootstrap') => void; email: string; setEmail: (value: string) => void; displayName: string; setDisplayName: (value: string) => void; password: string; setPassword: (value: string) => void; error: string; loading: boolean; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void; health: HealthResponse | null }) {
  return <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-10"><form className="w-full max-w-md rounded-3xl bg-white p-8 text-slate-900 shadow-2xl" onSubmit={props.onSubmit}><p className="text-sm font-semibold uppercase tracking-[0.2em] text-brand-600">Report Manager</p><h1 className="mt-4 text-3xl font-bold">{props.loginMode === 'login' ? 'Entrar na plataforma' : 'Inicializar operador'}</h1><p className="mt-2 text-sm text-slate-500">Ambiente: {props.health?.environment ?? 'verificando'}</p>{props.loginMode === 'bootstrap' && <Field label="Nome" value={props.displayName} onChange={props.setDisplayName} />}<Field label="E-mail" type="email" value={props.email} onChange={props.setEmail} /><Field label="Senha" type="password" value={props.password} onChange={props.setPassword} />{props.error && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{props.error}</p>}<button className="mt-6 w-full rounded-xl bg-brand-600 px-4 py-3 font-semibold text-white transition hover:bg-brand-700 disabled:opacity-50" disabled={props.loading}>{props.loading ? 'Aguarde...' : 'Continuar'}</button><button type="button" className="mt-4 w-full text-sm text-slate-500 underline" onClick={() => props.setLoginMode(props.loginMode === 'login' ? 'bootstrap' : 'login')}>{props.loginMode === 'login' ? 'Inicializar operador local' : 'Voltar para login'}</button></form></main>
}

function PasswordChangePanel(props: { currentPassword: string; setCurrentPassword: (value: string) => void; newPassword: string; setNewPassword: (value: string) => void; error: string; loading: boolean; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-10"><form className="w-full max-w-md rounded-3xl bg-white p-8 text-slate-900 shadow-2xl" onSubmit={props.onSubmit}><p className="text-sm font-semibold uppercase tracking-[0.2em] text-brand-600">Primeiro acesso</p><h1 className="mt-4 text-3xl font-bold">Troque sua senha</h1><p className="mt-2 text-sm text-slate-500">A senha temporária não libera as funções da organização.</p><Field label="Senha temporária" type="password" value={props.currentPassword} onChange={props.setCurrentPassword} /><Field label="Nova senha" type="password" value={props.newPassword} onChange={props.setNewPassword} />{props.error && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{props.error}</p>}<button className="mt-6 w-full rounded-xl bg-brand-600 px-4 py-3 font-semibold text-white disabled:opacity-50" disabled={props.loading}>Alterar senha</button></form></main>
}

function Sidebar(props: { view: View; setView: (view: View) => void; user: string; onLogout: () => void; isOperator: boolean; role: string | null }) {
  const items: Array<{ value: View; label: string }> = [
    { value: 'overview', label: 'Visão geral' },
    { value: 'sources', label: 'Fontes e catálogo' },
    { value: 'reports', label: 'Relatórios' },
    { value: 'ready', label: 'Relatórios prontos' },
    { value: 'audit', label: 'Auditoria' },
  ]
  const isAdmin = props.isOperator || props.role === 'ADMIN_ORGANIZACAO'
  const canManageLlm = isAdmin
  if (isAdmin) {
    items.splice(4, 0, { value: 'users', label: 'Usuários e papéis' })
  }
  if (canManageLlm) {
    items.splice(5, 0, { value: 'llm', label: 'IA e modelos' })
    items.splice(6, 0, { value: 'delivery', label: 'Distribuição' })
  }
  if (props.isOperator) {
    items.push({ value: 'operator', label: 'Clientes e licenças' })
  }
  return <aside className="flex w-full flex-col bg-slate-950 p-6 md:min-h-screen md:w-64"><div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-300">MVP</p><h2 className="mt-2 text-xl font-bold">Plataforma</h2></div><nav className="mt-10 space-y-2">{items.map((item) => <button key={item.value} className={`w-full rounded-xl px-4 py-3 text-left text-sm font-medium transition ${props.view === item.value ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`} onClick={() => props.setView(item.value)}>{item.label}</button>)}</nav><div className="mt-auto pt-10"><p className="truncate text-sm text-slate-400">{props.user}</p><button className="mt-3 text-sm text-slate-300 underline" onClick={props.onLogout}>Sair</button></div></aside>
}

function Overview(props: { health: HealthResponse | null; sources: Source[]; reports: Report[]; readyReports: ReadyReport[]; onRefresh: () => void }) {
  return <div className="space-y-6"><div className="flex items-center justify-between"><div><h2 className="text-2xl font-bold">Visão geral</h2><p className="mt-1 text-slate-500">Fontes, versões publicadas e resultados prontos.</p></div><button className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold" onClick={props.onRefresh}>Atualizar</button></div><div className="grid gap-4 md:grid-cols-4"><StatusCard label="Backend" value={props.health?.status === 'ok' ? 'Online' : 'Indisponível'} detail={props.health?.environment ?? 'Sem conexão'} /><StatusCard label="Fontes" value={String(props.sources.length)} detail="Dentro da organização" /><StatusCard label="Relatórios" value={String(props.reports.length)} detail="Versionados" /><StatusCard label="Prontos" value={String(props.readyReports.length)} detail="Execuções concluídas" /></div><div className="rounded-2xl border border-slate-200 bg-white p-6"><h3 className="text-lg font-semibold">Regras ativas</h3><div className="mt-4 grid gap-3 text-sm text-slate-600 md:grid-cols-3"><p className="rounded-xl bg-slate-50 p-4">Versões publicadas são imutáveis.</p><p className="rounded-xl bg-slate-50 p-4">Execuções usam a versão mais recente publicada.</p><p className="rounded-xl bg-slate-50 p-4">Artefatos ficam no PostgreSQL por três anos.</p></div></div></div>
}

function SourcesView(props: {
  sources: Source[]
  sourceName: string
  setSourceName: (value: string) => void
  sourceType: string
  setSourceType: (value: string) => void
  sourceFile: File | null
  setSourceFile: (value: File | null) => void
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void
  sourceMode: 'file' | 'database'
  setSourceMode: (value: 'file' | 'database') => void
  databaseSourceType: string
  setDatabaseSourceType: (value: string) => void
  databaseHost: string
  setDatabaseHost: (value: string) => void
  databasePort: string
  setDatabasePort: (value: string) => void
  databaseName: string
  setDatabaseName: (value: string) => void
  databaseUser: string
  setDatabaseUser: (value: string) => void
  databaseSchema: string
  setDatabaseSchema: (value: string) => void
  databaseSecretRef: string
  setDatabaseSecretRef: (value: string) => void
  databaseAllowedTables: string
  setDatabaseAllowedTables: (value: string) => void
  onCreateDatabase: (event: React.FormEvent<HTMLFormElement>) => void
  selectedSource: Source | null
  catalog: SourceCatalog | null
  versions: SourceVersion[]
  sourceDiff: SourceDiff | null
  onDiff: (versionId: string) => void
  onOpenSource: (source: Source) => void
  onFieldChange: (fieldId: string, classification: string, action: string) => void
}) {
  return <div className="space-y-6">
    <div><h2 className="text-2xl font-bold">Fontes de dados</h2><p className="mt-1 text-slate-500">Bancos somente leitura por IP público e arquivos versionados.</p></div>
    <div className="flex gap-2"><button className={props.sourceMode === 'file' ? 'rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white' : 'rounded-lg border border-slate-300 px-4 py-2 text-sm'} onClick={() => props.setSourceMode('file')}>Arquivo</button><button className={props.sourceMode === 'database' ? 'rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white' : 'rounded-lg border border-slate-300 px-4 py-2 text-sm'} onClick={() => props.setSourceMode('database')}>Banco de dados</button></div>
    {props.sourceMode === 'file' && <form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onSubmit}><div className="grid gap-4 md:grid-cols-3"><Field label="Nome da fonte" value={props.sourceName} onChange={props.setSourceName} /><label className="text-sm font-medium text-slate-700">Tipo<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.sourceType} onChange={(event) => props.setSourceType(event.target.value)}>{sourceTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><label className="text-sm font-medium text-slate-700">Arquivo<input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" type="file" accept=".csv,.xls,.xlsx,.json" onChange={(event) => props.setSourceFile(event.target.files?.[0] ?? null)} /></label></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Validar e criar versão</button></form>}
    {props.sourceMode === 'database' && <form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onCreateDatabase}><div className="grid gap-4 md:grid-cols-3"><Field label="Nome da fonte" value={props.sourceName} onChange={props.setSourceName} /><label className="text-sm font-medium text-slate-700">Banco<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.databaseSourceType} onChange={(event) => props.setDatabaseSourceType(event.target.value)}>{databaseSourceTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label><Field label="IP público" value={props.databaseHost} onChange={props.setDatabaseHost} /><Field label="Porta" value={props.databasePort} onChange={props.setDatabasePort} /><Field label="Banco/service" value={props.databaseName} onChange={props.setDatabaseName} /><Field label="Usuário somente leitura" value={props.databaseUser} onChange={props.setDatabaseUser} /><Field label="Schema (opcional)" value={props.databaseSchema} onChange={props.setDatabaseSchema} /><Field label="Referência do segredo" value={props.databaseSecretRef} onChange={props.setDatabaseSecretRef} /><Field label="Tabelas permitidas (vírgula)" value={props.databaseAllowedTables} onChange={props.setDatabaseAllowedTables} /></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Criar e testar conexão</button></form>}
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-5 py-3">Nome</th><th className="px-5 py-3">Tipo</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Ação</th></tr></thead><tbody>{props.sources.map((source) => <tr className="border-t border-slate-100" key={source.id}><td className="px-5 py-3 font-medium">{source.name}</td><td className="px-5 py-3">{source.source_type}</td><td className="px-5 py-3"><StatusBadge value={source.status} /></td><td className="px-5 py-3"><button className="text-brand-700 underline" onClick={() => props.onOpenSource(source)}>Catálogo</button></td></tr>)}</tbody></table></div>
    {props.selectedSource && <div className="rounded-2xl border border-slate-200 bg-white p-6"><h3 className="text-lg font-semibold">Catálogo: {props.selectedSource.name}</h3><p className="mt-1 text-sm text-slate-500">Versões preservadas: {props.versions.length}</p><div className="mt-3 flex flex-wrap gap-2">{props.versions.map((version) => <button type="button" className="rounded border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50" key={version.id} onClick={() => props.onDiff(version.id)}>Comparar versão {version.version_number}</button>)}</div>{props.sourceDiff && <div className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm"><p className="font-semibold">Diferenças contra a versão {props.sourceDiff.compare_to_version_id ? 'anterior' : 'base'}</p><p className="mt-2">Adicionados: {props.sourceDiff.added.join(', ') || 'nenhum'}</p><p>Removidos: {props.sourceDiff.removed.join(', ') || 'nenhum'}</p><p>Alterados: {props.sourceDiff.changed.join(', ') || 'nenhum'}</p></div>}{props.catalog?.objects.map((catalogObject) => <div className="mt-4" key={catalogObject.object_name}><h4 className="font-medium">{catalogObject.object_name}</h4><div className="mt-2 overflow-auto"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-3 py-2">Campo</th><th className="px-3 py-2">Tipo</th><th className="px-3 py-2">Classificação</th><th className="px-3 py-2">Ação</th></tr></thead><tbody>{catalogObject.fields.map((field) => <tr className="border-t border-slate-100" key={field.id}><td className="px-3 py-2">{field.name}</td><td className="px-3 py-2">{field.type}</td><td className="px-3 py-2"><select className="rounded border border-slate-300 px-2 py-1" value={field.classification} onChange={(event) => props.onFieldChange(field.id, event.target.value, field.action)}><option value="PUBLICO">Público</option><option value="INTERNO">Interno</option><option value="CONFIDENCIAL">Confidencial</option><option value="SENSIVEL">Sensível</option><option value="SECRETO">Secreto</option></select></td><td className="px-3 py-2"><select className="rounded border border-slate-300 px-2 py-1" value={field.action} onChange={(event) => props.onFieldChange(field.id, field.classification, event.target.value)}><option value="PERMITIR">Permitir</option><option value="MASCARAR">Mascarar</option><option value="AGREGAR">Agregar</option><option value="TOKENIZAR">Tokenizar</option><option value="BLOQUEAR">Bloquear</option></select></td></tr>)}</tbody></table></div></div>)}</div>}
  </div>
}

function ReportsView(props: { reports: Report[]; sources: Source[]; reportName: string; setReportName: (value: string) => void; reportObjective: string; setReportObjective: (value: string) => void; reportSourceId: string; setReportSourceId: (value: string) => void; reportFields: string; setReportFields: (value: string) => void; reportGroupBy: string; setReportGroupBy: (value: string) => void; reportMetricField: string; setReportMetricField: (value: string) => void; reportQuery: string; setReportQuery: (value: string) => void; onCreate: (event: React.FormEvent<HTMLFormElement>) => void; onOpen: (report: Report) => void; onExecute: (report: Report) => void; selectedReport: Report | null; versions: ReportVersion[]; reportDiff: ReportDiff | null; onDiff: (versionId: string) => void; definitionText: string; setDefinitionText: (value: string) => void; onPublish: (version: ReportVersion) => void; onCreateVersion: () => void; grants: ReportGrant[]; grantTargetType: string; setGrantTargetType: (value: string) => void; grantTargetId: string; setGrantTargetId: (value: string) => void; grantPermission: string; setGrantPermission: (value: string) => void; onCreateGrant: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return <div className="space-y-6"><div><h2 className="text-2xl font-bold">Relatórios</h2><p className="mt-1 text-slate-500">Crie rascunhos, publique versões e execute sob demanda.</p></div><form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onCreate}><h3 className="font-semibold">Novo relatório manual</h3><div className="mt-4 grid gap-4 md:grid-cols-2"><Field label="Nome" value={props.reportName} onChange={props.setReportName} /><Field label="Objetivo" value={props.reportObjective} onChange={props.setReportObjective} /><label className="text-sm font-medium text-slate-700">Fonte<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.reportSourceId} onChange={(event) => props.setReportSourceId(event.target.value)}><option value="">Selecione</option>{props.sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label><Field label="Campos (separados por vírgula)" value={props.reportFields} onChange={props.setReportFields} /><Field label="Agrupamento (separado por vírgula)" value={props.reportGroupBy} onChange={props.setReportGroupBy} /><Field label="Campo numérico para soma" value={props.reportMetricField} onChange={props.setReportMetricField} /><label className="text-sm font-medium text-slate-700 md:col-span-2">Consulta SQL somente leitura (obrigatória para banco)<textarea className="mt-1 h-24 w-full rounded-lg border border-slate-300 p-3 font-mono text-xs" value={props.reportQuery} onChange={(event) => props.setReportQuery(event.target.value)} placeholder="SELECT categoria, valor FROM schema.tabela" /></label></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Salvar rascunho</button></form><div className="grid gap-6 xl:grid-cols-[1fr_1.15fr]"><div className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-5 py-3">Relatório</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Ações</th></tr></thead><tbody>{props.reports.map((report) => <tr className="border-t border-slate-100" key={report.id}><td className="px-5 py-3 font-medium">{report.name}</td><td className="px-5 py-3"><StatusBadge value={report.status} /></td><td className="space-x-2 px-5 py-3"><button className="text-brand-700 underline" onClick={() => props.onOpen(report)}>Versões</button>{report.published_version_id && <button className="text-emerald-700 underline" onClick={() => props.onExecute(report)}>Executar</button>}</td></tr>)}</tbody></table></div>{props.selectedReport && <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6"><div><h3 className="text-lg font-semibold">{props.selectedReport.name}</h3><p className="mt-1 text-sm text-slate-500">Histórico imutável e acesso por grant.</p></div><label className="block text-sm font-medium text-slate-700">Definição selecionada<textarea className="mt-1 h-44 w-full rounded-lg border border-slate-300 p-3 font-mono text-xs" value={props.definitionText} onChange={(event) => props.setDefinitionText(event.target.value)} /></label><button className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold" onClick={props.onCreateVersion}>Criar próxima versão</button><div className="space-y-3">{props.versions.map((version) => <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-4" key={version.id}><div><p className="font-semibold">Versão {version.version_number}</p><p className="text-xs text-slate-500">{version.status} · {new Date(version.created_at).toLocaleString('pt-BR')}</p></div><div className="flex gap-3">{version.status === 'RASCUNHO' && <button className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white" onClick={() => props.onPublish(version)}>Publicar</button>}<button type="button" className="text-xs text-brand-700 underline" onClick={() => props.onDiff(version.id)}>Comparar</button></div></div>)}</div>{props.reportDiff && <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm"><p className="font-semibold">Diferenças da versão selecionada</p><p className="mt-2">Campos alterados: {props.reportDiff.changed_keys.join(', ') || 'nenhum'}</p><p>Versão comparada: {props.reportDiff.compare_to_version_id ?? 'base'}</p></div>}<form className="border-t border-slate-200 pt-4" onSubmit={props.onCreateGrant}><h4 className="font-semibold">Conceder acesso</h4><div className="mt-3 grid gap-3 md:grid-cols-3"><label className="text-sm font-medium text-slate-700">Alvo<select className="mt-1 w-full rounded border border-slate-300 px-2 py-2" value={props.grantTargetType} onChange={(event) => props.setGrantTargetType(event.target.value)}><option value="PAPEL">Papel</option><option value="USUARIO">Usuário</option><option value="ORGANIZACAO">Organização</option></select></label><Field label="ID ou valor do alvo" value={props.grantTargetId} onChange={props.setGrantTargetId} /><Field label="Permissão" value={props.grantPermission} onChange={props.setGrantPermission} /></div><button className="mt-3 rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white">Salvar grant</button></form><div className="space-y-2">{props.grants.map((grant) => <div className="rounded bg-slate-50 p-3 text-xs" key={grant.id}>{grant.target_type} · {grant.target_id} · {grant.permission}</div>)}</div></div>}</div></div>
}

function ReadyReportsView(props: { reports: ReadyReport[]; organizationId: string; preview: ScreenResult | null; onPreview: (artifactId: string) => void; onClosePreview: () => void; onDownload: (artifactId: string, fileName: string) => void }) {
  const preview = props.preview
  return <div className="space-y-6"><div><h2 className="text-2xl font-bold">Relatórios prontos</h2><p className="mt-1 text-slate-500">Somente execuções concluídas e autorizadas aparecem aqui.</p></div>{preview && <div className="rounded-2xl border border-blue-200 bg-blue-50 p-6"><div className="flex items-center justify-between"><h3 className="font-semibold">Visualização em tela ({preview.row_count} linhas)</h3><button className="text-sm underline" onClick={props.onClosePreview}>Fechar</button></div><div className="mt-4 overflow-auto"><table className="min-w-full text-left text-sm"><thead className="bg-white text-slate-500"><tr>{preview.columns.map((column) => <th className="px-3 py-2" key={column}>{column}</th>)}</tr></thead><tbody>{preview.rows.slice(0, 100).map((row, index) => <tr className="border-t border-blue-100" key={index}>{preview.columns.map((column) => <td className="px-3 py-2" key={column}>{String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div></div>}{props.reports.map((readyReport) => <article className="rounded-2xl border border-slate-200 bg-white p-6" key={readyReport.execution.id}><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">{readyReport.report_name}</h3><p className="text-sm text-slate-500">Versão {readyReport.version_number} · {new Date(readyReport.execution.finished_at ?? readyReport.execution.created_at).toLocaleString('pt-BR')}</p></div><StatusBadge value={readyReport.execution.status} /></div><div className="mt-4 flex flex-wrap gap-2">{readyReport.execution.artifacts.map((artifact) => <span className="flex items-center gap-1" key={artifact.id}>{artifact.artifact_type === 'TELA' && <button className="rounded-lg border border-blue-300 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-50" onClick={() => props.onPreview(artifact.id)}>Visualizar</button>}<button className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50" onClick={() => props.onDownload(artifact.id, artifact.file_name)}>{artifact.file_name}</button></span>)}</div>{readyReport.execution.artifacts.some((artifact) => new Date(artifact.expires_at).getTime() < Date.now() + 30 * 24 * 60 * 60 * 1000) && <p className="mt-3 text-xs text-amber-700">Algum artefato expira nos próximos 30 dias.</p>}</article>)}{props.reports.length === 0 && <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">Nenhum relatório pronto ainda.</div>}</div>
}

function OperatorPanel(props: { organizations: Organization[]; onRefresh: () => void; onChangeLicense: (organization: Organization, action: 'suspend' | 'reactivate') => void }) {
  return <section className="rounded-2xl border border-slate-200 bg-white p-6"><div className="flex items-center justify-between"><div><h2 className="text-xl font-bold">Clientes e licenças</h2><p className="mt-1 text-sm text-slate-500">O operador controla somente o estado operacional da licença.</p></div><button className="rounded-lg border border-slate-300 px-3 py-2 text-sm" onClick={props.onRefresh}>Atualizar</button></div><div className="mt-5 overflow-auto"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-4 py-2">Organização</th><th className="px-4 py-2">Licença</th><th className="px-4 py-2">Ação</th></tr></thead><tbody>{props.organizations.map((organization) => <tr className="border-t border-slate-100" key={organization.id}><td className="px-4 py-3">{organization.name}</td><td className="px-4 py-3"><StatusBadge value={organization.license?.status ?? organization.status} /></td><td className="px-4 py-3">{organization.license?.status === 'ATIVA' ? <button className="text-rose-700 underline" onClick={() => props.onChangeLicense(organization, 'suspend')}>Suspender</button> : <button className="text-emerald-700 underline" onClick={() => props.onChangeLicense(organization, 'reactivate')}>Reativar</button>}</td></tr>)}</tbody></table></div>{props.organizations.length === 0 && <p className="mt-5 text-sm text-slate-500">Nenhuma organização cadastrada.</p>}</section>
}

function OperatorPresetPanel(props: { presets: Preset[]; onCreate: (payload: { provider: string; model_identifier: string; name: string; reasoning_levels: string[] }) => void; onDeactivate: (preset: Preset) => void }) {
  const [provider, setProvider] = useState('OPENAI')
  const [model, setModel] = useState('gpt-4o-mini')
  const [name, setName] = useState('Preset inicial')
  const [reasoning, setReasoning] = useState('low,medium,high')
  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    props.onCreate({ provider, model_identifier: model, name, reasoning_levels: splitValues(reasoning) })
  }
  return <section className="rounded-2xl border border-slate-200 bg-white p-6"><div><h2 className="text-xl font-bold">Presets de modelos</h2><p className="mt-1 text-sm text-slate-500">O operador controla capacidades e validação sem acessar API keys de clientes.</p></div><form className="mt-5 grid gap-3 md:grid-cols-4" onSubmit={submit}><label className="text-sm font-medium">Provedor<select className="mt-1 w-full rounded border border-slate-300 px-2 py-2" value={provider} onChange={(event) => setProvider(event.target.value)}><option>OPENAI</option><option>ANTHROPIC</option><option>DEEPSEEK</option><option>GEMINI</option><option>COPILOT</option></select></label><Field label="Modelo" value={model} onChange={setModel} /><Field label="Nome" value={name} onChange={setName} /><Field label="Reasoning (vírgula)" value={reasoning} onChange={setReasoning} /><button className="rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white md:col-span-4">Adicionar preset</button></form><div className="mt-5 overflow-auto"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-3 py-2">Preset</th><th className="px-3 py-2">Capacidades</th><th className="px-3 py-2">Última validação</th><th className="px-3 py-2">Estado</th><th className="px-3 py-2">Ação</th></tr></thead><tbody>{props.presets.map((preset) => <tr className="border-t border-slate-100" key={preset.id}><td className="px-3 py-2">{preset.name} · {preset.provider}/{preset.model_identifier}</td><td className="px-3 py-2">{preset.reasoning_levels.join(', ') || 'padrão'}</td><td className="px-3 py-2">{preset.last_validated_at ? new Date(preset.last_validated_at).toLocaleString('pt-BR') : 'Nunca validado'}</td><td className="px-3 py-2"><StatusBadge value={preset.is_active ? 'ATIVO' : 'INATIVO'} /></td><td className="px-3 py-2">{preset.is_active && <button type="button" className="text-rose-700 underline" onClick={() => props.onDeactivate(preset)}>Desativar</button>}</td></tr>)}</tbody></table></div></section>
}

function UsersView(props: { members: Membership[]; memberEmail: string; setMemberEmail: (value: string) => void; memberName: string; setMemberName: (value: string) => void; memberPassword: string; setMemberPassword: (value: string) => void; memberRole: string; setMemberRole: (value: string) => void; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void; onChange: (member: Membership, role: string, isActive: boolean) => void }) {
  return <div className="space-y-6"><div><h2 className="text-2xl font-bold">Usuários e papéis</h2><p className="mt-1 text-slate-500">O usuário criado recebe uma senha temporária e deve trocá-la no primeiro acesso.</p></div><form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onSubmit}><div className="grid gap-4 md:grid-cols-4"><Field label="Nome" value={props.memberName} onChange={props.setMemberName} /><Field label="E-mail" type="email" value={props.memberEmail} onChange={props.setMemberEmail} /><Field label="Senha temporária" type="password" value={props.memberPassword} onChange={props.setMemberPassword} /><label className="text-sm font-medium text-slate-700">Papel<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.memberRole} onChange={(event) => props.setMemberRole(event.target.value)}><option value="VISUALIZADOR">Visualizador</option><option value="CRIADOR_RELATORIOS">Criador de relatórios</option><option value="ADMIN_ORGANIZACAO">Administrador</option></select></label></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Criar usuário</button></form><div className="overflow-auto rounded-2xl border border-slate-200 bg-white"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-5 py-3">Nome</th><th className="px-5 py-3">E-mail</th><th className="px-5 py-3">Papel</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Salvar</th></tr></thead><tbody>{props.members.map((member) => <MembershipRow member={member} onChange={props.onChange} key={member.id} />)}</tbody></table></div></div>
}

function MembershipRow(props: { member: Membership; onChange: (member: Membership, role: string, isActive: boolean) => void }) {
  const [role, setRole] = useState<string>(props.member.role)
  const [isActive, setIsActive] = useState(props.member.is_active)
  return <tr className="border-t border-slate-100"><td className="px-5 py-3">{props.member.display_name}</td><td className="px-5 py-3">{props.member.email}</td><td className="px-5 py-3"><label className="sr-only" htmlFor={`role-${props.member.id}`}>Papel de {props.member.display_name}</label><select id={`role-${props.member.id}`} className="rounded border border-slate-300 px-2 py-1" value={role} onChange={(event) => setRole(event.target.value)}><option value="VISUALIZADOR">Visualizador</option><option value="CRIADOR_RELATORIOS">Criador de relatórios</option><option value="ADMIN_ORGANIZACAO">Administrador</option></select></td><td className="px-5 py-3"><label className="flex items-center gap-2"><input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} /> <span>{isActive ? 'Ativo' : 'Inativo'}</span></label></td><td className="px-5 py-3"><button type="button" className="text-brand-700 underline" onClick={() => props.onChange(props.member, role, isActive)}>Salvar</button></td></tr>
}

function LlmView(props: { presets: Preset[]; configurations: LlmConfiguration[]; name: string; setName: (value: string) => void; presetId: string; setPresetId: (value: string) => void; secretRef: string; setSecretRef: (value: string) => void; reasoning: string; setReasoning: (value: string) => void; temperature: string; setTemperature: (value: string) => void; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void; objective: string; setObjective: (value: string) => void; proposalConfigurationId: string; setProposalConfigurationId: (value: string) => void; proposalText: string; onProposal: (event: React.FormEvent<HTMLFormElement>) => void }) {
  const selectedPreset = props.presets.find((preset) => preset.id === props.presetId)
  return <div className="space-y-6"><div><h2 className="text-2xl font-bold">IA e modelos</h2><p className="mt-1 text-slate-500">A organização informa a referência da própria API key; o segredo não passa pelo frontend.</p></div><form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onSubmit}><div className="grid gap-4 md:grid-cols-3"><Field label="Nome" value={props.name} onChange={props.setName} /><label className="text-sm font-medium text-slate-700">Preset<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.presetId} onChange={(event) => props.setPresetId(event.target.value)}><option value="">Selecione</option>{props.presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name} · {preset.provider}</option>)}</select></label><Field label="Referência do segredo" value={props.secretRef} onChange={props.setSecretRef} /><label className="text-sm font-medium text-slate-700">Reasoning<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.reasoning} onChange={(event) => props.setReasoning(event.target.value)}><option value="">Padrão</option>{selectedPreset?.reasoning_levels.map((level) => <option key={level} value={level}>{level}</option>)}</select></label><Field label="Temperatura" value={props.temperature} onChange={props.setTemperature} /></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Salvar configuração</button></form><div className="rounded-2xl border border-slate-200 bg-white p-6"><h3 className="font-semibold">Configurações ativas</h3><div className="mt-3 space-y-2">{props.configurations.map((configuration) => <div className="rounded-lg bg-slate-50 p-3 text-sm" key={configuration.id}>{configuration.name} · {configuration.secret_ref} · reasoning {configuration.reasoning_level ?? 'padrão'}</div>)}</div></div><form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onProposal}><h3 className="font-semibold">Solicitar proposta de relatório</h3><p className="mt-1 text-sm text-slate-500">A proposta é apenas um rascunho até a confirmação explícita.</p><div className="mt-4 grid gap-4 md:grid-cols-2"><Field label="Objetivo" value={props.objective} onChange={props.setObjective} /><label className="text-sm font-medium text-slate-700">Configuração<select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" value={props.proposalConfigurationId} onChange={(event) => props.setProposalConfigurationId(event.target.value)}><option value="">Selecione</option>{props.configurations.map((configuration) => <option key={configuration.id} value={configuration.id}>{configuration.name}</option>)}</select></label></div><button className="mt-5 rounded-lg border border-slate-300 px-4 py-2 font-semibold">Gerar proposta</button>{props.proposalText && <pre className="mt-4 max-h-80 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-100">{props.proposalText}</pre>}</form></div>
}

function DeliveryView(props: { destinations: Destination[]; name: string; setName: (value: string) => void; recipients: string; setRecipients: (value: string) => void; webhookUrl: string; setWebhookUrl: (value: string) => void; secretRef: string; setSecretRef: (value: string) => void; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return <div className="space-y-6"><div><h2 className="text-2xl font-bold">Distribuição</h2><p className="mt-1 text-slate-500">Informe destinatários de e-mail ou webhook. O SMTP global fica configurado no `.env`.</p></div><form className="rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onSubmit}><div className="grid gap-4 md:grid-cols-2"><Field label="Nome do destino" value={props.name} onChange={props.setName} /><Field label="Destinatários de e-mail (vírgula)" value={props.recipients} onChange={props.setRecipients} /><Field label="URL webhook (se não informar e-mail)" value={props.webhookUrl} onChange={props.setWebhookUrl} /><Field label="Referência do segredo webhook" value={props.secretRef} onChange={props.setSecretRef} /></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Cadastrar destino</button></form><div className="space-y-2">{props.destinations.map((destination) => <div className="rounded-xl border border-slate-200 bg-white p-4" key={destination.id}><span className="font-medium">{destination.name}</span><span className="ml-3 text-sm text-slate-500">{destination.destination_type} · {destination.status}</span></div>)}</div></div>
}

function AuditView(props: { events: AuditEvent[]; onRefresh: () => void }) {
  return <div className="space-y-6"><div className="flex items-center justify-between"><div><h2 className="text-2xl font-bold">Auditoria</h2><p className="mt-1 text-slate-500">A trilha mostra ação, resultado e correlation ID sem payloads sensíveis.</p></div><button className="rounded-lg border border-slate-300 px-3 py-2 text-sm" onClick={props.onRefresh}>Atualizar</button></div><div className="overflow-auto rounded-2xl border border-slate-200 bg-white"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr><th className="px-4 py-2">Data</th><th className="px-4 py-2">Ação</th><th className="px-4 py-2">Resultado</th><th className="px-4 py-2">Correlation ID</th></tr></thead><tbody>{props.events.map((event) => <tr className="border-t border-slate-100" key={event.id}><td className="px-4 py-3">{new Date(event.created_at).toLocaleString('pt-BR')}</td><td className="px-4 py-3">{event.action}</td><td className="px-4 py-3">{event.result}</td><td className="px-4 py-3 font-mono text-xs">{event.correlation_id}</td></tr>)}</tbody></table></div></div>
}

function OrganizationPanel(props: { organizationName: string; setOrganizationName: (value: string) => void; organizationSlug: string; setOrganizationSlug: (value: string) => void; adminEmail: string; setAdminEmail: (value: string) => void; adminName: string; setAdminName: (value: string) => void; temporaryPassword: string; setTemporaryPassword: (value: string) => void; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  return <form className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-6" onSubmit={props.onSubmit}><h2 className="text-xl font-bold">Criar cliente</h2><p className="mt-1 text-sm text-slate-500">A organização recebe uma licença ativa e um usuário administrador com troca obrigatória de senha.</p><div className="mt-5 grid gap-4 md:grid-cols-2"><Field label="Nome da organização" value={props.organizationName} onChange={props.setOrganizationName} /><Field label="Slug" value={props.organizationSlug} onChange={props.setOrganizationSlug} /><Field label="E-mail administrador" type="email" value={props.adminEmail} onChange={props.setAdminEmail} /><Field label="Nome administrador" value={props.adminName} onChange={props.setAdminName} /><Field label="Senha temporária" type="password" value={props.temporaryPassword} onChange={props.setTemporaryPassword} /></div><button className="mt-5 rounded-lg bg-brand-600 px-4 py-2 font-semibold text-white">Criar cliente</button></form>
}

function Field(props: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return <label className="block text-sm font-medium text-slate-700">{props.label}<input className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-normal outline-none ring-brand-200 focus:ring-2" type={props.type ?? 'text'} value={props.value} onChange={(event) => props.onChange(event.target.value)} /></label>
}

function Notice(props: { tone: 'success' | 'error'; children: string; onClose: () => void }) {
  const toneClass = props.tone === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-rose-200 bg-rose-50 text-rose-800'
  return <div role="status" aria-live="polite" className={`flex items-center justify-between rounded-xl border px-4 py-3 text-sm ${toneClass}`}><span>{props.children}</span><button type="button" className="ml-4 rounded underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2" onClick={props.onClose}>Fechar</button></div>
}

export default App
