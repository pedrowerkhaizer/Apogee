"""workers/topic_miner_worker.py — RQ job wrapper para TopicMiner."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from agents.topic_miner import mine_topics


def run(channel_id: UUID) -> list[dict]:
    """Job RQ: executa mine_topics e retorna lista de tópicos criados."""
    return mine_topics(channel_id)
