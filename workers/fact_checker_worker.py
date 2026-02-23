"""workers/fact_checker_worker.py — RQ job wrapper para FactChecker."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from agents.fact_checker import check_script
from models import FactCheckResult


def run(video_id: UUID) -> dict:
    """Job RQ: executa check_script e retorna FactCheckResult como dict serializável."""
    result: FactCheckResult = check_script(video_id)
    return result.model_dump()
