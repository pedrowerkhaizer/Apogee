import { NextRequest, NextResponse } from 'next/server'
import { redis } from '@/lib/redis'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: jobId } = await params

  const data = await redis.hgetall(`apogee:job:${jobId}`)
  if (!data || Object.keys(data).length === 0) {
    return NextResponse.json({ error: 'Job não encontrado' }, { status: 404 })
  }

  return NextResponse.json(data)
}
