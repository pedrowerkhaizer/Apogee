import { createClient } from '@/lib/supabase/server'
import { KpiCard } from '@/components/app/kpi-card'
import { ActivityFeed } from '@/components/app/activity-feed'
import { QuickActions } from '@/components/app/quick-actions'
import {
  Film, DollarSign, Lightbulb, CheckCircle2
} from 'lucide-react'
import type { VideoStatus } from '@/lib/types'

async function getKpis() {
  const supabase = await createClient()

  // Videos por status
  const { data: videos } = await supabase
    .from('videos')
    .select('status')
  const byStatus = (videos ?? []).reduce((acc, v) => {
    acc[v.status as VideoStatus] = (acc[v.status as VideoStatus] ?? 0) + 1
    return acc
  }, {} as Record<VideoStatus, number>)

  // Custo do mês atual
  const startOfMonth = new Date()
  startOfMonth.setDate(1)
  startOfMonth.setHours(0, 0, 0, 0)

  const { data: runs } = await supabase
    .from('agent_runs')
    .select('cost_usd')
    .gte('created_at', startOfMonth.toISOString())

  const costThisMonth = (runs ?? []).reduce(
    (sum, r) => sum + Number(r.cost_usd), 0
  )

  // Topics pendentes
  const { count: pendingTopics } = await supabase
    .from('topics')
    .select('*', { count: 'exact', head: true })
    .eq('status', 'pending')

  // Última execução
  const { data: lastRun } = await supabase
    .from('agent_runs')
    .select('created_at, status')
    .order('created_at', { ascending: false })
    .limit(1)
    .single()

  return { byStatus, costThisMonth, pendingTopics: pendingTopics ?? 0, lastRun }
}

export default async function DashboardPage() {
  const { byStatus, costThisMonth, pendingTopics, lastRun } = await getKpis()

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-content-primary">Dashboard</h1>
          <p className="text-sm text-content-tertiary mt-0.5">Visão geral do pipeline</p>
        </div>
        <QuickActions />
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiCard
          title="Publicados"
          value={byStatus.published ?? 0}
          icon={CheckCircle2}
          mono
        />
        <KpiCard
          title="Custo do mês"
          value={`$${costThisMonth.toFixed(2)}`}
          icon={DollarSign}
          mono
        />
        <KpiCard
          title="Topics pendentes"
          value={pendingTopics}
          icon={Lightbulb}
          delta={pendingTopics > 0 ? { value: pendingTopics, label: `${pendingTopics} aguardando aprovação` } : undefined}
          mono
        />
        <KpiCard
          title="Em produção"
          value={(byStatus.draft ?? 0) + (byStatus.scripted ?? 0) + (byStatus.rendered ?? 0)}
          icon={Film}
          mono
        />
      </div>

      {/* Status breakdown */}
      <div className="grid grid-cols-5 gap-2">
        {(['draft','scripted','rendered','published','failed'] as VideoStatus[]).map(s => (
          <div key={s} className="card-base px-3 py-2 text-center">
            <p className="section-label mb-1">{s}</p>
            <p className="text-xl font-bold font-mono text-content-primary">{byStatus[s] ?? 0}</p>
          </div>
        ))}
      </div>

      {/* Activity feed */}
      <div className="space-y-3">
        <h2 className="text-base font-medium text-content-primary">Atividade recente</h2>
        <ActivityFeed />
      </div>
    </div>
  )
}
