import { createClient } from '@/lib/supabase/server'
import { TopicsTable } from '@/components/app/topics-table'
import type { Topic } from '@/lib/types'

export default async function TopicsPage() {
  const supabase = await createClient()
  const { data } = await supabase
    .from('topics')
    .select('*')
    .order('created_at', { ascending: false })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-content-primary">Topics</h1>
        <p className="text-sm text-content-tertiary mt-0.5">
          Aprove ou rejeite tópicos antes de entrar no pipeline
        </p>
      </div>
      <TopicsTable topics={(data ?? []) as Topic[]} />
    </div>
  )
}
