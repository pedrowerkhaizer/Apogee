import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import { randomUUID } from 'crypto'
import { redis } from '@/lib/redis'

export async function POST(req: NextRequest) {
  try {
    const body     = await req.json().catch(() => ({}))
    const jobId    = randomUUID()
    const apogee   = process.env.APOGEE_PATH!
    const channelId = body.channelId ?? process.env.APOGEE_CHANNEL_ID

    // Registra job no Redis antes de spawnar
    await redis.hmset(`apogee:job:${jobId}`, {
      status:    'started',
      startedAt: new Date().toISOString(),
      channelId: channelId ?? '',
    })
    await redis.expire(`apogee:job:${jobId}`, 3600)

    // Spawna pipeline.py de forma desacoplada
    const child = spawn(
      'uv', ['run', 'python', 'pipeline.py', '--once',
        ...(channelId ? ['--channel-id', channelId] : [])
      ],
      {
        cwd:      apogee,
        detached: true,
        stdio:    'ignore',
        env:      { ...process.env, PIPELINE_JOB_ID: jobId },
      }
    )
    child.unref()

    return NextResponse.json({ jobId, status: 'started' })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
