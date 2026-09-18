import { useState } from 'react'

export function StatusBadge(props: { value: string }) {
  return <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{props.value}</span>
}

export function Alert(props: { tone: 'success' | 'error' | 'warning'; children: string }) {
  const toneClass = getAlertTone(props.tone)
  return <div role="alert" className={`rounded-xl border px-4 py-3 text-sm ${toneClass}`}>{props.children}</div>
}

function getAlertTone(tone: 'success' | 'error' | 'warning'): string {
  if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800'
  if (tone === 'error') return 'border-rose-200 bg-rose-50 text-rose-800'
  return 'border-amber-200 bg-amber-50 text-amber-800'
}

export function ConfirmButton(props: { label: string; confirmation: string; onConfirm: () => void }) {
  const [confirming, setConfirming] = useState(false)
  if (confirming) {
    return <span className="inline-flex items-center gap-2"><span className="text-xs">{props.confirmation}</span><button type="button" className="underline" onClick={props.onConfirm}>Confirmar</button><button type="button" className="underline" onClick={() => setConfirming(false)}>Cancelar</button></span>
  }
  return <button type="button" className="underline" onClick={() => setConfirming(true)}>{props.label}</button>
}

export function DataTable<T extends { id: string }>(props: { rows: T[]; columns: Array<{ key: string; label: string; render: (row: T) => React.ReactNode }>; emptyMessage: string }) {
  return <div className="overflow-auto rounded-xl border border-slate-200 bg-white"><table className="min-w-full text-left text-sm"><thead className="bg-slate-100 text-slate-500"><tr>{props.columns.map((column) => <th scope="col" className="px-4 py-2" key={column.key}>{column.label}</th>)}</tr></thead><tbody>{props.rows.map((row) => <tr className="border-t border-slate-100" key={row.id}>{props.columns.map((column) => <td className="px-4 py-3" key={column.key}>{column.render(row)}</td>)}</tr>)}</tbody></table>{props.rows.length === 0 && <p className="p-5 text-sm text-slate-500">{props.emptyMessage}</p>}</div>
}

export function Pagination(props: { page: number; pageCount: number; onChange: (page: number) => void }) {
  const previousDisabled = props.page <= 1
  const nextDisabled = props.page >= props.pageCount
  return <nav aria-label="Paginação" className="flex items-center gap-3 text-sm"><button type="button" disabled={previousDisabled} className="rounded border border-slate-300 px-3 py-1 disabled:opacity-40" onClick={() => props.onChange(props.page - 1)}>Anterior</button><span>Página {props.page} de {props.pageCount}</span><button type="button" disabled={nextDisabled} className="rounded border border-slate-300 px-3 py-1 disabled:opacity-40" onClick={() => props.onChange(props.page + 1)}>Próxima</button></nav>
}
