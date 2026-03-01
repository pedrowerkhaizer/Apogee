import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Play, CheckSquare } from 'lucide-react'

export function QuickActions() {
  return (
    <div className="flex gap-3">
      <Button asChild size="sm">
        <Link href="/pipeline">
          <Play size={14} className="mr-1.5" />
          Run Pipeline
        </Link>
      </Button>
      <Button asChild variant="outline" size="sm">
        <Link href="/topics?status=pending">
          <CheckSquare size={14} className="mr-1.5" />
          Approve Topics
        </Link>
      </Button>
    </div>
  )
}
