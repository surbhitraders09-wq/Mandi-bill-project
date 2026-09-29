import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'

interface SmartTableProps<T> {
  columns: ColumnDef<T, any>[]
  data: T[]
  loading?: boolean
  searchPlaceholder?: string
  filterKey?: string
  exportName?: string
  onRowClick?: (row: T) => void
}

export function SmartTable<T>({
  columns,
  data,
  loading = false,
  searchPlaceholder = 'Search…',
  filterKey,
  exportName,
  onRowClick,
}: SmartTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [globalFilter, setGlobalFilter] = useState('')

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
    globalFilterFn: 'includesString',
  })

  const exportCsv = () => {
    const header = columns
      .map((c) => (c as { header?: string }).header ?? '')
      .filter(Boolean)
      .join(',')
    const rows = table.getFilteredRowModel().rows.map((r) =>
      r.getVisibleCells()
        .map((c) => {
          const v = c.getValue()
          const s = typeof v === 'string' ? v : JSON.stringify(v ?? '')
          return `"${s.replace(/"/g, '""')}"`
        })
        .join(','),
    )
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${exportName ?? 'export'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
          placeholder={searchPlaceholder}
          className="max-w-xs"
          data-testid={filterKey}
        />
        {exportName && (
          <Button variant="outline" size="sm" onClick={exportCsv} className="ml-auto">
            <Download className="mr-1 h-3.5 w-3.5" />
            Export CSV
          </Button>
        )}
      </div>

      <div className="overflow-hidden rounded-md border border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/5 text-xs uppercase tracking-wide text-muted">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th key={header.id} className="whitespace-nowrap px-3 py-2.5 font-semibold">
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-border">
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {columns.map((_, j) => (
                        <td key={j} className="px-3 py-2">
                          <Skeleton className="h-4 w-full max-w-[12rem]" />
                        </td>
                      ))}
                    </tr>
                  ))
                : table.getRowModel().rows.map((row) => (
                    <tr
                      key={row.id}
                      className={onRowClick ? 'cursor-pointer hover:bg-muted/5' : 'hover:bg-muted/5'}
                      onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                    >
                      {row.getVisibleCells().map((cell) => (
                        <td key={cell.id} className="whitespace-nowrap px-3 py-2 text-text">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
        {!loading && table.getRowModel().rows.length === 0 && (
          <div className="px-3 py-8 text-center text-sm text-muted">No records match your search.</div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 text-sm text-muted">
        <span>
          {table.getFilteredRowModel().rows.length} result{table.getFilteredRowModel().rows.length === 1 ? '' : 's'}
        </span>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <span className="px-2">
            {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            aria-label="Next page"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}
