import { NextRequest, NextResponse } from 'next/server'
import { existsSync, createReadStream, statSync } from 'fs'
import { join } from 'path'

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: videoId } = await params
  const apogee = process.env.APOGEE_PATH!

  // Segurança: garantir que o videoId é um UUID válido
  if (!/^[0-9a-f-]{36}$/.test(videoId)) {
    return NextResponse.json({ error: 'ID inválido' }, { status: 400 })
  }

  const filePath = join(apogee, 'output', 'renders', `${videoId}.mp4`)

  if (!existsSync(filePath)) {
    return NextResponse.json({ error: 'Render não encontrado' }, { status: 404 })
  }

  const stat = statSync(filePath)

  // Stream do arquivo com suporte a Range (para o player HTML5)
  const range = req.headers.get('range')

  if (range) {
    const parts     = range.replace(/bytes=/, '').split('-')
    const start     = parseInt(parts[0], 10)
    const end       = parts[1] ? parseInt(parts[1], 10) : stat.size - 1
    const chunkSize = end - start + 1

    const stream = createReadStream(filePath, { start, end })
    const body   = stream as unknown as ReadableStream

    return new Response(body, {
      status:  206,
      headers: {
        'Content-Range':  `bytes ${start}-${end}/${stat.size}`,
        'Accept-Ranges':  'bytes',
        'Content-Length': String(chunkSize),
        'Content-Type':   'video/mp4',
      },
    })
  }

  const stream = createReadStream(filePath) as unknown as ReadableStream

  return new Response(stream, {
    headers: {
      'Content-Type':   'video/mp4',
      'Content-Length': String(stat.size),
      'Accept-Ranges':  'bytes',
    },
  })
}
