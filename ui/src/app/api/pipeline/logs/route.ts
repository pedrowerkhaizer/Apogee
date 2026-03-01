import { NextRequest } from 'next/server'
import { createReadStream, statSync, existsSync } from 'fs'
import { join } from 'path'
import { createInterface } from 'readline'

function getLogFilePath(): string {
  const date     = new Date().toISOString().slice(0, 10)
  const apogee   = process.env.APOGEE_PATH!
  return join(apogee, 'artifacts', 'logs', `pipeline_${date}.log`)
}

export async function GET(req: NextRequest) {
  const logFile = getLogFilePath()

  const encoder = new TextEncoder()
  let closed    = false

  const stream = new ReadableStream({
    async start(controller) {
      function send(data: string) {
        if (!closed) {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ line: data })}\n\n`))
        }
      }

      // Envia as últimas 50 linhas do arquivo existente
      if (existsSync(logFile)) {
        try {
          const rl = createInterface({
            input: createReadStream(logFile),
            crlfDelay: Infinity,
          })
          const lines: string[] = []
          for await (const line of rl) lines.push(line)
          lines.slice(-50).forEach(send)
        } catch {}
      }

      // Poll a cada 2s para novas linhas (file watching)
      let lastSize = existsSync(logFile) ? statSync(logFile).size : 0

      const interval = setInterval(() => {
        if (closed) { clearInterval(interval); return }
        if (!existsSync(logFile)) return

        const currentSize = statSync(logFile).size
        if (currentSize <= lastSize) return

        const rs = createReadStream(logFile, { start: lastSize })
        const rl = createInterface({ input: rs, crlfDelay: Infinity })
        rl.on('line', send)
        rl.on('close', () => { lastSize = currentSize })
      }, 2000)

      req.signal.addEventListener('abort', () => {
        closed = true
        clearInterval(interval)
        try { controller.close() } catch {}
      })
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type':  'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection':    'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}
