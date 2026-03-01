'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Lightbulb, Film, Workflow,
  Terminal, ChevronLeft, ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'

const NAV = [
  {
    section: 'MAIN',
    items: [
      { href: '/',        icon: LayoutDashboard, label: 'Dashboard' },
      { href: '/topics',  icon: Lightbulb,       label: 'Topics',   badgeKey: 'pendingTopics' },
      { href: '/videos',  icon: Film,            label: 'Videos' },
    ],
  },
  {
    section: 'PIPELINE',
    items: [
      { href: '/pipeline', icon: Workflow,  label: 'Pipeline' },
      { href: '/pipeline#logs', icon: Terminal, label: 'Logs' },
    ],
  },
]

interface SidebarProps {
  pendingTopics?: number
}

export function Sidebar({ pendingTopics = 0 }: SidebarProps) {
  const pathname  = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  const badges: Record<string, number> = { pendingTopics }

  return (
    <aside
      className={cn(
        'relative flex flex-col h-full border-r border-border-default bg-bg-surface transition-all duration-200',
        collapsed ? 'w-14' : 'w-[220px]'
      )}
    >
      {/* Logo */}
      <div className={cn(
        'flex items-center gap-2.5 px-4 h-14 border-b border-border-default flex-shrink-0',
        collapsed && 'justify-center px-0'
      )}>
        <span className="text-accent text-xl">⬡</span>
        {!collapsed && (
          <span className="font-semibold text-content-primary text-sm">Apogee</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-4">
        {NAV.map(({ section, items }) => (
          <div key={section}>
            {!collapsed && (
              <p className="section-label px-3 mb-1">{section}</p>
            )}
            <ul className="space-y-0.5 px-2">
              {items.map(({ href, icon: Icon, label, badgeKey }) => {
                const active = pathname === href || (href !== '/' && pathname.startsWith(href))
                const count  = badgeKey ? badges[badgeKey] : 0

                return (
                  <li key={href}>
                    <Link
                      href={href}
                      className={cn(
                        'flex items-center gap-2.5 px-2 py-2 rounded-sm text-sm transition-all duration-150',
                        'hover:bg-bg-overlay',
                        active
                          ? 'bg-bg-overlay text-content-primary border-l-2 border-accent -ml-[1px] pl-[9px]'
                          : 'text-content-secondary',
                        collapsed && 'justify-center px-0'
                      )}
                    >
                      <Icon size={16} className={active ? 'text-accent' : ''} />
                      {!collapsed && (
                        <>
                          <span className="flex-1">{label}</span>
                          {count > 0 && (
                            <Badge className="h-5 px-1.5 text-xs bg-accent-muted text-accent border-0">
                              {count}
                            </Badge>
                          )}
                        </>
                      )}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className={cn(
          'absolute -right-3 top-[72px] z-10',
          'w-6 h-6 rounded-full bg-bg-elevated border border-border-default',
          'flex items-center justify-center text-content-tertiary hover:text-content-primary',
          'transition-colors duration-150'
        )}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
    </aside>
  )
}
