import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'

export async function POST(req: NextRequest) {
  try {
    const { videoId, agent } = await req.json()
    const apogee = process.env.APOGEE_PATH!

    if (!videoId || !agent) {
      return NextResponse.json({ error: 'videoId e agent são obrigatórios' }, { status: 400 })
    }

    const script = `
import sys, os
sys.path.insert(0, '${apogee}')
from dotenv import load_dotenv
load_dotenv('${apogee}/.env')

if '${agent}' == 'researcher':
    from agents.researcher import research_topic
    import psycopg2
    conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
    cur = conn.cursor()
    cur.execute("SELECT topic_id FROM videos WHERE id = %s", ('${videoId}',))
    row = cur.fetchone()
    if row:
        research_topic(row[0])
    conn.close()
elif '${agent}' == 'scriptwriter':
    from agents.scriptwriter import write_script
    import psycopg2
    conn = psycopg2.connect(os.environ['SUPABASE_DB_URL'])
    cur = conn.cursor()
    cur.execute("SELECT topic_id FROM videos WHERE id = %s", ('${videoId}',))
    row = cur.fetchone()
    if row:
        write_script(row[0])
    conn.close()
elif '${agent}' == 'fact_checker':
    from agents.fact_checker import check_script
    check_script('${videoId}')
elif '${agent}' == 'tts':
    from agents.tts import generate_audio
    generate_audio('${videoId}')
elif '${agent}' == 'render':
    from agents.render import render_video
    render_video('${videoId}')
`

    const child = spawn('uv', ['run', 'python', '-c', script], {
      cwd:      apogee,
      detached: true,
      stdio:    'ignore',
    })
    child.unref()

    return NextResponse.json({ status: 'started', videoId, agent })
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
