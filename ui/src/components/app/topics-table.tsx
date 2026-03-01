'use client'

import { useState, useTransition } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { StatusBadge } from './status-badge'
import { RejectModal } from './reject-modal'
import { approveTopic, rejectTopic, bulkApprove, bulkReject } from '@/app/actions/topics'
import type { Topic, TopicStatus } from '@/lib/types'
import { Check, X, Search } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { cn } from '@/lib/utils'

const TABS: { value: TopicStatus | 'all'; label: string }[] = [
  { value: 'all',       label: 'Todos' },
  { value: 'pending',   label: 'Pendentes' },
  { value: 'approved',  label: 'Aprovados' },
  { value: 'rejected',  label: 'Rejeitados' },
  { value: 'published', label: 'Publicados' },
]

interface TopicsTableProps {
  topics: Topic[]
}

export function TopicsTable({ topics }: TopicsTableProps) {
  const [tab, setTab]           = useState<string>('pending')
  const [search, setSearch]     = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [rejectTarget, setRejectTarget] = useState<Topic | null>(null)
  const [bulkRejectOpen, setBulkRejectOpen] = useState(false)
  const [, startTransition]     = useTransition()

  const filtered = topics
    .filter(t => tab === 'all' || t.status === tab)
    .filter(t => !search || t.title.toLowerCase().includes(search.toLowerCase()))

  const counts = TABS.reduce((acc, { value }) => {
    acc[value] = value === 'all'
      ? topics.length
      : topics.filter(t => t.status === value).length
    return acc
  }, {} as Record<string, number>)

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  function toggleAll() {
    if (selected.size === filtered.length) setSelected(new Set())
    else setSelected(new Set(filtered.map(t => t.id)))
  }

  return (
    <div className="space-y-4">
      <Tabs value={tab} onValueChange={v => { setTab(v); setSelected(new Set()) }}>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <TabsList className="bg-bg-elevated border border-border-default">
            {TABS.map(({ value, label }) => (
              <TabsTrigger key={value} value={value} className="text-xs">
                {label}
                {counts[value] > 0 && (
                  <span className="ml-1.5 text-content-tertiary">({counts[value]})</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-content-tertiary" />
              <Input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Buscar tópicos..."
                className="pl-8 h-8 text-sm w-52"
              />
            </div>

            {selected.size > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-content-tertiary">{selected.size} selecionados</span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-green-400 border-green-500/30 hover:bg-green-500/10"
                  onClick={() => startTransition(() => bulkApprove(Array.from(selected)).then(() => setSelected(new Set())))}
                >
                  <Check size={12} className="mr-1" /> Aprovar todos
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 text-red-400 border-red-500/30 hover:bg-red-500/10"
                  onClick={() => setBulkRejectOpen(true)}
                >
                  <X size={12} className="mr-1" /> Rejeitar todos
                </Button>
              </div>
            )}
          </div>
        </div>

        {TABS.map(({ value }) => (
          <TabsContent key={value} value={value}>
            <div className="card-base overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-subtle">
                    <th className="w-8 px-4 py-3">
                      <Checkbox
                        checked={filtered.length > 0 && selected.size === filtered.length}
                        onCheckedChange={toggleAll}
                      />
                    </th>
                    <th className="px-4 py-3 text-left section-label">Título</th>
                    <th className="px-4 py-3 text-left section-label w-24">Similaridade</th>
                    <th className="px-4 py-3 text-left section-label w-28">Status</th>
                    <th className="px-4 py-3 text-left section-label w-28">Criado</th>
                    <th className="px-4 py-3 text-right section-label w-28">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-subtle">
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-content-tertiary text-xs">
                        Nenhum tópico encontrado.
                      </td>
                    </tr>
                  )}
                  {filtered.map(topic => (
                    <tr key={topic.id} className={cn('hover:bg-bg-overlay transition-colors', selected.has(topic.id) && 'bg-bg-overlay')}>
                      <td className="px-4 py-3">
                        <Checkbox
                          checked={selected.has(topic.id)}
                          onCheckedChange={() => toggleSelect(topic.id)}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-content-primary font-medium leading-snug">{topic.title}</p>
                          {topic.rationale && (
                            <p className="text-xs text-content-tertiary mt-0.5 line-clamp-1">{topic.rationale}</p>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {topic.similarity_score != null ? (
                          <span className={cn(
                            'font-mono text-xs',
                            topic.similarity_score > 0.65 ? 'text-red-400' : 'text-content-secondary'
                          )}>
                            {(topic.similarity_score * 100).toFixed(0)}%
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={topic.status} />
                      </td>
                      <td className="px-4 py-3 text-xs text-content-tertiary">
                        {formatDistanceToNow(new Date(topic.created_at), { addSuffix: true, locale: ptBR })}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {topic.status === 'pending' && (
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-green-400 hover:bg-green-500/10"
                              onClick={() => startTransition(() => approveTopic(topic.id))}
                            >
                              <Check size={13} />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 px-2 text-red-400 hover:bg-red-500/10"
                              onClick={() => setRejectTarget(topic)}
                            >
                              <X size={13} />
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>
        ))}
      </Tabs>

      {/* Reject single */}
      <RejectModal
        open={!!rejectTarget}
        title={rejectTarget?.title}
        onClose={() => setRejectTarget(null)}
        onConfirm={reason => {
          if (rejectTarget) {
            startTransition(() => rejectTopic(rejectTarget.id, reason))
          }
        }}
      />

      {/* Bulk reject */}
      <RejectModal
        open={bulkRejectOpen}
        onClose={() => setBulkRejectOpen(false)}
        onConfirm={reason => {
          startTransition(() =>
            bulkReject(Array.from(selected), reason).then(() => setSelected(new Set()))
          )
        }}
      />
    </div>
  )
}
