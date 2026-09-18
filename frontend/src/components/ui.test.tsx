import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { Alert, ConfirmButton, DataTable, Pagination, StatusBadge } from './ui'

describe('componentes de interface', () => {
  it('renderiza estados e tabela vazia', () => {
    render(
      <>
        <StatusBadge value="ATIVO" />
        <Alert tone="warning">Atenção operacional</Alert>
        <DataTable rows={[]} columns={[]} emptyMessage="Nenhum registro" />
      </>,
    )

    expect(screen.getByText('ATIVO')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Atenção operacional')
    expect(screen.getByText('Nenhum registro')).toBeInTheDocument()
  })

  it('renderiza linhas, confirma uma ação e pagina', () => {
    const onConfirm = vi.fn()
    const onPageChange = vi.fn()
    render(
      <>
        <DataTable
          rows={[{ id: '1', name: 'Relatório mensal' }]}
          columns={[{ key: 'name', label: 'Nome', render: (row) => row.name }]}
          emptyMessage="Nenhum registro"
        />
        <ConfirmButton label="Suspender" confirmation="Confirma?" onConfirm={onConfirm} />
        <Pagination page={1} pageCount={2} onChange={onPageChange} />
      </>,
    )

    expect(screen.getByText('Relatório mensal')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Suspender' }))
    expect(screen.getByText('Confirma?')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(onConfirm).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: 'Próxima' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })
})
