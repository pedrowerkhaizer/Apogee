"""workers/scriptwriter_worker.py — RQ job wrapper para Scriptwriter."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from agents.scriptwriter import write_script
from models import Script


def run(topic_id: UUID) -> dict:
    """Job RQ: executa write_script e retorna Script como dict serializável."""
    script: Script = write_script(topic_id)
    return script.model_dump()
