import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'
import { installFetchMock, jsonResponse } from './test/fetchMock'
import {
  healthFixture,
  organizationB,
  reportFixture,
  sessionFixture,
  sourceFixture,
} from './test/fixtures'

function responseForWorkspace(url: string): Response | null {
  if (url.endsWith('/sources')) return jsonResponse([])
  if (url.endsWith('/reports')) return jsonResponse([])
  if (url.endsWith('/executions/ready')) return jsonResponse([])
  return null
}

describe('fluxos principais do frontend', () => {
  it('faz login e exige troca da senha temporária', async () => {
    let changedPassword = false
    installFetchMock((url) => {
      if (url.endsWith('/health')) return jsonResponse(healthFixture)
      if (url.endsWith('/auth/me')) return jsonResponse({}, 401)
      if (url.endsWith('/auth/login')) {
        return jsonResponse(
          sessionFixture({
            user: { ...sessionFixture().user, must_change_password: true },
          }),
        )
      }
      if (url.endsWith('/auth/change-password')) {
        changedPassword = true
        return jsonResponse(sessionFixture())
      }
      return responseForWorkspace(url) ?? jsonResponse({}, 404)
    })

    render(<App />)
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'admin@example.com' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'StrongPassword#123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Continuar' }))

    expect(await screen.findByText('Troque sua senha')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Senha temporária'), { target: { value: 'StrongPassword#123' } })
    fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: 'NewStrongPassword#123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Alterar senha' }))

    await waitFor(() => expect(changedPassword).toBe(true))
    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeInTheDocument()
  })

  it('troca a organização ativa e mantém a lista isolada por organização', async () => {
    installFetchMock((url) => {
      if (url.endsWith('/health')) return jsonResponse(healthFixture)
      if (url.endsWith('/auth/me')) return jsonResponse(sessionFixture())
      if (url.includes('/auth/select-organization/org-b')) {
        return jsonResponse(sessionFixture({ active_organization_id: organizationB.id }))
      }
      return responseForWorkspace(url) ?? jsonResponse({}, 404)
    })

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeInTheDocument()
    const organizationSelect = screen.getByLabelText('Organização')
    fireEvent.change(organizationSelect, { target: { value: organizationB.id } })

    await waitFor(() => expect((organizationSelect as HTMLSelectElement).value).toBe(organizationB.id))
    expect(screen.getByText('Organização B')).toBeInTheDocument()
  })

  it('exibe o bloqueio do backend quando uma organização tenta acessar recurso de outra', async () => {
    installFetchMock((url, init) => {
      if (url.endsWith('/health')) return jsonResponse(healthFixture)
      if (url.endsWith('/auth/me')) return jsonResponse(sessionFixture())
      if (url.includes('/auth/select-organization/org-b')) {
        return jsonResponse(sessionFixture({ active_organization_id: organizationB.id }))
      }
      if (url.endsWith('/reports')) {
        const selectedOrganization = new Headers(init?.headers).get('X-Organization-Id')
        if (selectedOrganization === organizationB.id) {
          return jsonResponse({ message: 'Acesso negado pela organização.' }, 403)
        }
        return jsonResponse([])
      }
      return responseForWorkspace(url) ?? jsonResponse({}, 404)
    })

    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Visão geral' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Organização'), { target: { value: organizationB.id } })

    expect(await screen.findByText('Acesso negado pela organização.')).toBeInTheDocument()
  })

  it('cria uma fonte por upload e abre catálogo e diff de versão', async () => {
    const sourceVersion = {
      id: 'source-version-a',
      version_number: 1,
      status: 'VALIDA',
      is_latest_valid: true,
      file_name: 'vendas.csv',
      content_type: 'text/csv',
      checksum: 'checksum',
      schema_snapshot: { columns: [] },
      created_at: '2026-09-18T00:00:00Z',
    }
    let sourceCreated = false
    installFetchMock((url) => {
      if (url.endsWith('/health')) return jsonResponse(healthFixture)
      if (url.endsWith('/auth/me')) return jsonResponse(sessionFixture())
      if (url.endsWith('/sources/upload')) {
        sourceCreated = true
        return jsonResponse(sourceVersion, 201)
      }
      if (url.endsWith('/sources')) return jsonResponse(sourceCreated ? [sourceFixture] : [])
      if (url.endsWith('/reports')) return jsonResponse([])
      if (url.endsWith('/executions/ready')) return jsonResponse([])
      if (url.endsWith('/sources/source-a/catalog')) {
        return jsonResponse({ source_id: 'source-a', version_id: 'source-version-a', version_number: 1, objects: [] })
      }
      if (url.endsWith('/sources/source-a/versions')) return jsonResponse([sourceVersion])
      if (url.endsWith('/sources/source-a/versions/source-version-a/diff')) {
        return jsonResponse({ source_id: 'source-a', version_id: 'source-version-a', compare_to_version_id: null, added: ['valor'], removed: [], changed: [] })
      }
      return jsonResponse({}, 404)
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Fontes e catálogo' }))
    fireEvent.change(screen.getByLabelText('Nome da fonte'), { target: { value: 'Vendas CSV' } })
    const file = new File(['id,valor\n1,10\n'], 'vendas.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('Arquivo'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Validar e criar versão' }))

    await waitFor(() => expect(sourceCreated).toBe(true))
    fireEvent.click(await screen.findByRole('button', { name: 'Catálogo' }))
    expect(await screen.findByText('Catálogo: Vendas CSV')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Comparar versão 1' }))
    expect(await screen.findByText('Adicionados: valor')).toBeInTheDocument()
  })

  it('cria relatório e cria a próxima versão sem apagar o histórico', async () => {
    const versions: Array<{
      id: string
      version_number: number
      status: string
      definition: Record<string, unknown>
      change_summary: string | null
      created_at: string
      published_at: string | null
    }> = [
      { id: 'report-version-a', version_number: 1, status: 'PUBLICADO', definition: { source_id: 'source-a' }, change_summary: null, created_at: '2026-09-18T00:00:00Z', published_at: '2026-09-18T00:00:00Z' },
    ]
    let reportCreated = false
    installFetchMock((url, init) => {
      if (url.endsWith('/health')) return jsonResponse(healthFixture)
      if (url.endsWith('/auth/me')) return jsonResponse(sessionFixture())
      if (url.endsWith('/sources')) return jsonResponse([sourceFixture])
      if (url.endsWith('/executions/ready')) return jsonResponse([])
      if (url.endsWith('/reports')) {
        if (init?.method === 'POST') {
          reportCreated = true
          return jsonResponse(reportFixture, 201)
        }
        return jsonResponse(reportCreated ? [reportFixture] : [])
      }
      if (url.endsWith('/reports/report-a/versions')) {
        if (init?.method === 'POST') {
          const nextVersion = { id: 'report-version-b', version_number: 2, status: 'RASCUNHO', definition: { source_id: 'source-a', fields: ['id'] }, change_summary: 'Ajuste', created_at: '2026-09-18T00:00:00Z', published_at: null }
          versions.push(nextVersion)
          return jsonResponse(nextVersion, 201)
        }
        return jsonResponse(versions)
      }
      if (url.includes('/reports/report-a/versions/') && url.endsWith('/diff')) {
        return jsonResponse({ report_id: 'report-a', version_id: 'report-version-a', compare_to_version_id: null, changed_keys: ['fields'], current: {}, previous: {} })
      }
      if (url.includes('/reports/report-a/grants')) return jsonResponse([])
      return jsonResponse({}, 404)
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Relatórios' }))
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Relatório novo' } })
    fireEvent.change(screen.getByLabelText('Objetivo'), { target: { value: 'Acompanhar' } })
    fireEvent.change(screen.getByLabelText('Fonte'), { target: { value: sourceFixture.id } })
    fireEvent.change(screen.getByLabelText('Campos (separados por vírgula)'), { target: { value: 'id,valor' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar rascunho' }))

    expect(await screen.findByText('Relatório de vendas')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Versões' }))
    expect(await screen.findByText('Versão 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Criar próxima versão' }))
    expect(await screen.findByText('Versão 2')).toBeInTheDocument()
    expect(screen.getByText('Versão 1')).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: 'Comparar' })[0])
    expect(await screen.findByText('Campos alterados: fields')).toBeInTheDocument()
  })

  it('lista relatório pronto e solicita visualização do artefato', async () => {
    const artifact = { id: 'artifact-a', artifact_type: 'TELA', storage_key: 'postgres://artifact-a', file_name: 'relatorio.json', content_type: 'application/json', checksum: 'checksum', size_bytes: 10, expires_at: '2029-09-18T00:00:00Z' }
    const execution = { id: 'execution-a', report_id: 'report-a', report_version_id: 'report-version-a', status: 'SUCESSO', parameters: {}, attempt_count: 1, started_at: '2026-09-18T00:00:00Z', finished_at: '2026-09-18T00:01:00Z', error_summary: null, created_at: '2026-09-18T00:00:00Z', artifacts: [artifact] }
    installFetchMock((url) => {
      if (url.endsWith('/health')) return jsonResponse(healthFixture)
      if (url.endsWith('/auth/me')) return jsonResponse(sessionFixture())
      if (url.endsWith('/sources')) return jsonResponse([])
      if (url.endsWith('/reports')) return jsonResponse([])
      if (url.endsWith('/executions/ready')) return jsonResponse([{ execution, report_name: 'Relatório pronto', version_number: 1 }])
      if (url.endsWith('/artifacts/artifact-a/download')) return jsonResponse({ columns: ['id'], rows: [{ id: 1 }], row_count: 1 })
      return jsonResponse({}, 404)
    })

    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Relatórios prontos' }))
    expect(await screen.findByText('Relatório pronto')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Visualizar' }))
    expect(await screen.findByText('Visualização em tela (1 linhas)')).toBeInTheDocument()
  })
})
