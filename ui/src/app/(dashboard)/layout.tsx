import { createClient } from '@/lib/supabase/server'
import { Sidebar } from '@/components/app/sidebar'
import { BreadcrumbNav } from '@/components/app/breadcrumb-nav'
import { redirect } from 'next/navigation'

async function getPendingTopics(): Promise<number> {
  const supabase = await createClient()
  const { count } = await supabase
    .from('topics')
    .select('*', { count: 'exact', head: true })
    .eq('status', 'pending')
  return count ?? 0
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/login')

  const pendingTopics = await getPendingTopics()

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar pendingTopics={pendingTopics} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-14 border-b border-border-default flex items-center px-6 flex-shrink-0 bg-bg-base/80 backdrop-blur-sm">
          <BreadcrumbNav />
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
