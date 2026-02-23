"""models.py — Contratos de dados do pipeline Apogee.

VideoSpec é a fonte da verdade passada entre todos os agentes.
Nunca use dicionários crus entre agentes — use estas classes.

Pydantic v2: use model_dump(), nunca .dict().
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ── Enums ─────────────────────────────────────────────────────────────────────


class TopicStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    published = "published"


class VideoStatus(str, Enum):
    draft = "draft"
    scripted = "scripted"
    rendered = "rendered"
    published = "published"
    failed = "failed"


class AgentStatus(str, Enum):
    success = "success"
    failed = "failed"
    retry = "retry"


# ── Claim ──────────────────────────────────────────────────────────────────────


class Claim(BaseModel):
    claim_text: str
    source_url: Optional[str] = None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    verified: bool = False


# ── ScriptBeat ─────────────────────────────────────────────────────────────────


class ScriptBeat(BaseModel):
    fact: str
    analogy: str


# ── Script ─────────────────────────────────────────────────────────────────────


class Script(BaseModel):
    hook: Annotated[str, Field(max_length=200)]
    beats: Annotated[list[ScriptBeat], Field(min_length=3, max_length=3)]
    payoff: str
    cta: Optional[str] = None
    full_text: str = ""

    @model_validator(mode="after")
    def build_full_text(self) -> Script:
        parts = [self.hook]
        for beat in self.beats:
            parts.append(beat.fact)
            parts.append(beat.analogy)
        parts.append(self.payoff)
        if self.cta:
            parts.append(self.cta)
        self.full_text = "\n\n".join(parts)
        return self


# ── FactCheckResult ────────────────────────────────────────────────────────────


class FactCheckResult(BaseModel):
    risk_score: Annotated[float, Field(ge=0.0, le=1.0)]
    issues: list[str]
    approved: bool


# ── VideoSpec ──────────────────────────────────────────────────────────────────


class VideoSpec(BaseModel):
    video_id: Optional[UUID] = None
    topic_id: UUID
    topic_title: str
    channel_id: UUID
    status: VideoStatus = VideoStatus.draft
    claims: Annotated[list[Claim], Field(min_length=1)]
    script: Script
    similarity_score: Optional[Annotated[float, Field(ge=0.0, le=1.0)]] = None
    template_score: Optional[Annotated[float, Field(ge=0.0, le=1.0)]] = None
    created_at: Optional[datetime] = None

    def to_db_rows(self) -> dict:
        """Retorna dicionário com linhas prontas para inserção no banco.

        Chaves retornadas:
            videos  — dict para a tabela videos
            scripts — dict para a tabela scripts
            claims  — list[dict] para a tabela claims
        """
        now = self.created_at or datetime.now(timezone.utc)
        vid = str(self.video_id) if self.video_id else None

        return {
            "videos": {
                "id": vid,
                "channel_id": str(self.channel_id),
                "topic_id": str(self.topic_id),
                "title": self.topic_title,
                "status": self.status.value,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
            "scripts": {
                "video_id": vid,
                "hook": self.script.hook,
                "beats": [b.model_dump() for b in self.script.beats],
                "payoff": self.script.payoff,
                "cta": self.script.cta,
                "template_score": self.template_score if self.template_score is not None else 0.0,
                "similarity_score": self.similarity_score,
                "version": 1,
            },
            "claims": [
                {
                    "video_id": vid,
                    "claim_text": c.claim_text,
                    "source_url": c.source_url,
                    "verified": c.verified,
                    "risk_score": round(1.0 - c.confidence, 6),
                }
                for c in self.claims
            ],
        }
