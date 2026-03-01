import { NextRequest, NextResponse } from 'next/server'
import { writeFile, readFile, unlink } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'
import { randomUUID } from 'crypto'
import { spawn } from 'child_process'

const ALLOWED_VOICES = [
  'pt-BR-AntonioNeural',
  'pt-BR-FranciscaNeural',
  'pt-BR-ThalitaNeural',
  'pt-BR-MacerioMultilingualNeural',
]

const DEFAULT_TEXT = 'Olá! Esta é uma prévia da voz selecionada para narrar seus vídeos. Aqui você encontra conteúdo incrível todos os dias.'

export async function POST(req: NextRequest) {
  const body = await req.json()
  const text  = (body.text  as string | undefined)?.trim().slice(0, 500) || DEFAULT_TEXT
  const voice = body.voice as string | undefined

  if (!voice || !ALLOWED_VOICES.includes(voice)) {
    return NextResponse.json({ error: 'Voz inválida' }, { status: 400 })
  }

  const id     = randomUUID()
  const tmpIn  = join(tmpdir(), `tts_in_${id}.txt`)
  const tmpOut = join(tmpdir(), `tts_out_${id}.mp3`)
  const apogee = process.env.APOGEE_PATH!

  await writeFile(tmpIn, text, 'utf8')

  const pyScript = [
    'import edge_tts',
    `with open(${JSON.stringify(tmpIn)}) as f: text = f.read()`,
    `edge_tts.Communicate(text, ${JSON.stringify(voice)}).save_sync(${JSON.stringify(tmpOut)})`,
  ].join('\n')

  try {
    await new Promise<void>((resolve, reject) => {
      const proc = spawn('uv', ['run', 'python', '-c', pyScript], {
        cwd: apogee,
        stdio: 'pipe',
      })
      proc.on('close', code => (code === 0 ? resolve() : reject(new Error(`exit ${code}`))))
      proc.on('error', reject)
    })

    const audio = await readFile(tmpOut)
    return new Response(audio, {
      headers: { 'Content-Type': 'audio/mpeg' },
    })
  } finally {
    await unlink(tmpIn).catch(() => {})
    await unlink(tmpOut).catch(() => {})
  }
}
