'use client'

import { usePathname } from 'next/navigation'
import { ChevronRight } from 'lucide-react'
import Link from 'next/link'

const LABELS: Record<string, string> = {
  '':         'Dashboard',
  'topics':   'Topics',
  'videos':   'Videos',
  'pipeline': 'Pipeline',
}

export function BreadcrumbNav() {
  const pathname = usePathname()
  const segments = pathname.split('/').filter(Boolean)

  const crumbs = [
    { label: 'Apogee', href: '/' },
    ...segments.map((seg, i) => ({
      label: LABELS[seg] ?? seg,
      href:  '/' + segments.slice(0, i + 1).join('/'),
    })),
  ]

  return (
    <nav className="flex items-center gap-1 text-sm">
      {crumbs.map((crumb, i) => (
        <span key={crumb.href} className="flex items-center gap-1">
          {i > 0 && <ChevronRight size={14} className="text-content-tertiary" />}
          {i < crumbs.length - 1 ? (
            <Link href={crumb.href} className="text-content-tertiary hover:text-content-secondary transition-colors">
              {crumb.label}
            </Link>
          ) : (
            <span className="text-content-primary font-medium">{crumb.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
