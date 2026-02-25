"""
Prepara assets de áudio para o Remotion Studio:
  - Copia mp3s de output/audio/{video_id}/ → remotion/public/audio/{video_id}/
  - Escreve remotion/public/input_props.json com o storyboard do vídeo
  - Imprime o comando de preview

Uso:
    uv run scripts/prepare_remotion.py --video-id 390318b4-df7a-42b7-a78a-1c7dcc319ea2
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REMOTION_PUBLIC = ROOT / "remotion" / "public"


def main():
    parser = argparse.ArgumentParser(description="Prepara assets Remotion para preview")
    parser.add_argument("--video-id", required=True, help="UUID do vídeo")
    args = parser.parse_args()

    video_id = args.video_id

    # Verifica storyboard
    storyboard_path = ROOT / "output" / "storyboards" / f"{video_id}.json"
    if not storyboard_path.exists():
        print(f"ERRO: storyboard não encontrado em {storyboard_path}", file=sys.stderr)
        sys.exit(1)

    # Verifica pasta de áudio
    audio_src = ROOT / "output" / "audio" / video_id
    if not audio_src.exists():
        print(f"ERRO: pasta de áudio não encontrada em {audio_src}", file=sys.stderr)
        sys.exit(1)

    # Cria destino
    audio_dst = REMOTION_PUBLIC / "audio" / video_id
    audio_dst.mkdir(parents=True, exist_ok=True)

    # Copia mp3s
    mp3_files = list(audio_src.glob("*.mp3"))
    if not mp3_files:
        print(f"ERRO: nenhum .mp3 encontrado em {audio_src}", file=sys.stderr)
        sys.exit(1)

    for mp3 in mp3_files:
        shutil.copy2(mp3, audio_dst / mp3.name)

    print(f"✓ {len(mp3_files)} arquivo(s) copiado(s) → {audio_dst}")

    # Escreve input_props.json no formato esperado pelo Remotion (--props / calculateMetadata)
    # Shape: { storyboard: {...}, showTimer: true }
    storyboard = json.loads(storyboard_path.read_text())
    input_props = {"storyboard": storyboard, "showTimer": True}
    input_props_path = REMOTION_PUBLIC / "input_props.json"
    input_props_path.write_text(json.dumps(input_props, ensure_ascii=False, indent=2))
    print(f"✓ input_props.json escrito → {input_props_path}")

    print()
    print("Para abrir o preview:")
    print("  cd remotion && npx remotion preview")
    print()
    print(f"  http://localhost:3000")


if __name__ == "__main__":
    main()
