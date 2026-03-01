import Redis from 'ioredis'

const globalForRedis = globalThis as unknown as { redis: Redis | undefined }

export const redis =
  globalForRedis.redis ??
  new Redis(process.env.REDIS_URL ?? 'redis://localhost:6379', {
    maxRetriesPerRequest: 1,
    enableReadyCheck: false,
    lazyConnect: true,
  })

if (process.env.NODE_ENV !== 'production') globalForRedis.redis = redis

/**
 * Lê o status de um job RQ diretamente do Redis.
 * Chave: rq:job:{job_id} (hash com campo 'status')
 */
export async function getRqJobStatus(jobId: string): Promise<{
  status: string | null
  description: string | null
  createdAt: string | null
}> {
  const [status, description, createdAt] = await redis.hmget(
    `rq:job:${jobId}`,
    'status',
    'description',
    'created_at'
  )
  return { status, description, createdAt }
}
