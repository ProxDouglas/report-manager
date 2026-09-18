export const organizationA = {
  id: 'org-a',
  name: 'Organização A',
  slug: 'organizacao-a',
  status: 'ATIVA',
  license: null,
}

export const organizationB = {
  id: 'org-b',
  name: 'Organização B',
  slug: 'organizacao-b',
  status: 'ATIVA',
  license: null,
}

export function sessionFixture(overrides: Record<string, unknown> = {}) {
  return {
    user: {
      id: 'user-a',
      email: 'admin@example.com',
      display_name: 'Administrador',
      must_change_password: false,
      is_platform_operator: false,
      is_active: true,
    },
    organizations: [organizationA, organizationB],
    active_organization_id: organizationA.id,
    active_role: 'ADMIN_ORGANIZACAO',
    ...overrides,
  }
}

export const healthFixture = {
  status: 'ok',
  service: 'report-manager-api',
  environment: 'test',
  timestamp: '2026-09-18T00:00:00Z',
}

export const sourceFixture = {
  id: 'source-a',
  name: 'Vendas CSV',
  source_type: 'ARQUIVO_CSV',
  status: 'ATIVA',
  last_tested_at: null,
  latest_version_number: 1,
  latest_valid_version_id: 'source-version-a',
}

export const reportFixture = {
  id: 'report-a',
  name: 'Relatório de vendas',
  objective: 'Acompanhar vendas',
  status: 'PUBLICADO',
  published_version_id: 'report-version-a',
  created_at: '2026-09-18T00:00:00Z',
  updated_at: '2026-09-18T00:00:00Z',
}
