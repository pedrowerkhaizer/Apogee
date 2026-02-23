"""scripts/smoke_test.py — E0.4: Smoke test end-to-end com Supabase real.

Executa 6 passos sequenciais, sem mocks, e limpa tudo ao final.

Uso:
    uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

# Garante que a raiz do projeto está em sys.path quando executado como script
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from models import Claim, Script, ScriptBeat, VideoSpec

load_dotenv()

TOTAL = 6
_ids: dict[str, str] = {}  # channel_id, topic_id, video_id


def fail(step: int, err: Exception | str) -> None:
    print(f"SMOKE TEST FAILED — passo {step}: {err}")
    sys.exit(1)


def cleanup(conn: psycopg2.extensions.connection) -> None:
    """Remove dados de teste em ordem reversa de FK."""
    vid = _ids.get("video_id")
    tid = _ids.get("topic_id")
    cid = _ids.get("channel_id")
    try:
        with conn.cursor() as cur:
            if vid:
                cur.execute("DELETE FROM claims   WHERE video_id = %s", (vid,))
                cur.execute("DELETE FROM scripts  WHERE video_id = %s", (vid,))
                cur.execute("DELETE FROM renders  WHERE video_id = %s", (vid,))
                cur.execute("DELETE FROM assets   WHERE video_id = %s", (vid,))
                cur.execute("DELETE FROM videos   WHERE id       = %s", (vid,))
            if tid:
                cur.execute("DELETE FROM topics        WHERE id = %s", (tid,))
            if cid:
                cur.execute("DELETE FROM channel_config WHERE id = %s", (cid,))
        conn.commit()
    except Exception as exc:
        print(f"[cleanup] aviso: {exc}")
        conn.rollback()


def main() -> None:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("SMOKE TEST FAILED — passo 0: SUPABASE_DB_URL não definido no .env")
        sys.exit(1)

    try:
        conn = psycopg2.connect(db_url, connect_timeout=10)
    except Exception as exc:
        print(f"SMOKE TEST FAILED — passo 0: falha ao conectar ao banco: {exc}")
        sys.exit(1)

    conn.autocommit = False

    try:
        # ── [1/6] Validar VideoSpec ────────────────────────────────────────────
        print(f"[1/{TOTAL}] Validando VideoSpec com dados fake")
        try:
            spec = VideoSpec(
                topic_id=uuid4(),
                topic_title="Smoke Test: IA no pipeline Apogee",
                channel_id=uuid4(),
                claims=[
                    Claim(
                        claim_text="Python está entre as 3 linguagens mais usadas do mundo",
                        confidence=0.92,
                    )
                ],
                script=Script(
                    hook="O que nenhum dev te conta sobre automação",
                    beats=[
                        ScriptBeat(
                            fact="Repetição consome 30% do tempo de um desenvolvedor",
                            analogy="Como lavar louça todo dia na mão",
                        ),
                        ScriptBeat(
                            fact="Automação reduz erros humanos em até 80%",
                            analogy="Como trocar a esponja por uma lava-louças",
                        ),
                        ScriptBeat(
                            fact="Python domina ferramentas de automação em 2025",
                            analogy="Como ter um robô doméstico programável",
                        ),
                    ],
                    payoff="Automatize ou seja automatizado.",
                    cta="Curte se fez sentido.",
                ),
                template_score=0.20,
                similarity_score=0.10,
            )
        except Exception as exc:
            fail(1, exc)
            return

        # ── [2/6] Serializar e deserializar ───────────────────────────────────
        print(f"[2/{TOTAL}] Serializando para JSON e deserializando")
        try:
            raw = spec.model_dump_json()
            spec2 = VideoSpec.model_validate_json(raw)
            assert spec2.topic_title == spec.topic_title, "topic_title divergiu"
            assert spec2.script.hook == spec.script.hook, "hook divergiu"
            assert spec2.script.full_text == spec.script.full_text, "full_text divergiu"
            assert spec2.claims[0].confidence == spec.claims[0].confidence, "confidence divergiu"
        except Exception as exc:
            fail(2, exc)
            return

        # ── [3/6] Inserir topic ───────────────────────────────────────────────
        print(f"[3/{TOTAL}] Inserindo topic em Supabase")
        try:
            with conn.cursor() as cur:
                # channel_config necessário como FK
                cur.execute(
                    """
                    INSERT INTO channel_config
                        (channel_name, niche, tone, target_audience, language, weekly_target)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        f"Smoke Test Channel {uuid4().hex[:8]}",
                        "teste-automatizado",
                        "educativo-direto",
                        "Desenvolvedores e QA engineers",
                        "pt-BR",
                        1,
                    ),
                )
                _ids["channel_id"] = str(cur.fetchone()[0])

                cur.execute(
                    """
                    INSERT INTO topics (channel_id, title, rationale, status)
                    VALUES (%s, %s, %s, 'pending')
                    RETURNING id
                    """,
                    (
                        _ids["channel_id"],
                        spec.topic_title,
                        "Gerado pelo smoke test E0.4",
                    ),
                )
                _ids["topic_id"] = str(cur.fetchone()[0])
            conn.commit()
        except Exception as exc:
            conn.rollback()
            fail(3, exc)
            return

        # ── [4/6] Inserir video ───────────────────────────────────────────────
        print(f"[4/{TOTAL}] Inserindo video em Supabase")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO videos (channel_id, topic_id, title, status)
                    VALUES (%s, %s, %s, 'draft')
                    RETURNING id
                    """,
                    (
                        _ids["channel_id"],
                        _ids["topic_id"],
                        spec.topic_title,
                    ),
                )
                _ids["video_id"] = str(cur.fetchone()[0])
            conn.commit()
        except Exception as exc:
            conn.rollback()
            fail(4, exc)
            return

        # ── [5/6] Inserir script e claims ─────────────────────────────────────
        print(f"[5/{TOTAL}] Inserindo script e claims em Supabase")
        try:
            db_rows = spec.to_db_rows()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scripts
                        (video_id, hook, beats, payoff, cta, template_score, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        _ids["video_id"],
                        db_rows["scripts"]["hook"],
                        psycopg2.extras.Json(db_rows["scripts"]["beats"]),
                        db_rows["scripts"]["payoff"],
                        db_rows["scripts"]["cta"],
                        db_rows["scripts"]["template_score"],
                        db_rows["scripts"]["version"],
                    ),
                )
                for claim_row in db_rows["claims"]:
                    cur.execute(
                        """
                        INSERT INTO claims
                            (video_id, claim_text, source_url, verified, risk_score)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            _ids["video_id"],
                            claim_row["claim_text"],
                            claim_row["source_url"],
                            claim_row["verified"],
                            claim_row["risk_score"],
                        ),
                    )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            fail(5, exc)
            return

        # ── [6/6] Recuperar e comparar ────────────────────────────────────────
        print(f"[6/{TOTAL}] Recuperando do banco e comparando topic_title, script.hook, claims[0].confidence")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT v.title, s.hook, c.risk_score
                    FROM   videos   v
                    JOIN   scripts  s ON s.video_id = v.id
                    JOIN   claims   c ON c.video_id = v.id
                    WHERE  v.id = %s
                    LIMIT  1
                    """,
                    (_ids["video_id"],),
                )
                row = cur.fetchone()

            assert row is not None, "linha não encontrada no banco após inserção"
            db_title, db_hook, db_risk_score = row

            assert db_title == spec.topic_title, (
                f"topic_title: esperado {spec.topic_title!r}, obtido {db_title!r}"
            )
            assert db_hook == spec.script.hook, (
                f"script.hook: esperado {spec.script.hook!r}, obtido {db_hook!r}"
            )
            reconstructed = round(1.0 - float(db_risk_score), 4)
            expected = spec.claims[0].confidence
            assert abs(reconstructed - expected) < 1e-4, (
                f"claims[0].confidence: esperado {expected}, "
                f"reconstruído {reconstructed} (risk_score={db_risk_score})"
            )
        except Exception as exc:
            fail(6, exc)
            return

    finally:
        cleanup(conn)
        conn.close()

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
