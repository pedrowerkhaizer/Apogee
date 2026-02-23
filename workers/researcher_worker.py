"""workers/researcher_worker.py — RQ job wrapper para Researcher."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from agents.researcher import research_topic
from models import Claim


def run(topic_id: UUID) -> list[dict]:
    """Job RQ: executa research_topic e retorna claims como dicts serializáveis."""
    claims: list[Claim] = research_topic(topic_id)
    return [c.model_dump() for c in claims]
