#!/usr/bin/env python3
"""
Ranker de tópicos usando GradientBoostingRegressor.
Prevê avg_view_duration_sec a partir de features do tópico.

Uso:
    uv run python ranker.py train
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Garante que a raiz do projeto está no sys.path quando rodado como script
sys.path.insert(0, str(Path(__file__).parent))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_PATH = Path(__file__).parent / "models" / "ranker.pkl"

FEATURE_NAMES = ["similarity_score", "has_numeric_claim", "day_of_week", "title_word_count"]


# ── Extração de features ───────────────────────────────────────────────────────


def _extract_features(row: dict | pd.Series) -> list[float]:
    """Extrai as 4 features de um tópico (dict ou linha de DataFrame).

    Features:
        similarity_score   (float): cosine similarity com scripts anteriores; default 0.0
        has_numeric_claim  (int):   1 se o título contém algum dígito, 0 caso contrário
        day_of_week        (int):   dia da semana de created_at (0=segunda, 6=domingo)
        title_word_count   (int):   quantidade de palavras no título
    """
    similarity_score = float(row.get("similarity_score") or 0.0)
    has_numeric_claim = 1 if re.search(r"\d", str(row.get("title", ""))) else 0
    created_at = row.get("created_at")
    if created_at is not None:
        day_of_week = int(pd.to_datetime(created_at).dayofweek)
    else:
        day_of_week = 0
    title_word_count = len(str(row.get("title", "")).split())
    return [similarity_score, has_numeric_claim, day_of_week, title_word_count]


# ── Treino ─────────────────────────────────────────────────────────────────────


def train_ranker(df: pd.DataFrame) -> Pipeline:
    """Treina o ranker com os dados de performance disponíveis.

    Args:
        df: DataFrame com colunas obrigatórias:
            - title (str)
            - similarity_score (float, pode ser NaN/None)
            - created_at (str ou datetime)
            - avg_view_duration_sec (float) — target

    Returns:
        Pipeline treinado (StandardScaler + GradientBoostingRegressor).
        O modelo é salvo em models/ranker.pkl.
    """
    # Garante que o diretório models/ existe
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Monta matriz de features
    X_rows = [_extract_features(row) for _, row in df.iterrows()]
    X = np.array(X_rows, dtype=float)
    y = df["avg_view_duration_sec"].astype(float).values

    # Pipeline: normalização + modelo
    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "gbr",
                GradientBoostingRegressor(n_estimators=100, random_state=42),
            ),
        ]
    )
    pipeline.fit(X, y)

    # Persiste o modelo
    joblib.dump(pipeline, MODEL_PATH)

    # Imprime feature importances
    gbr: GradientBoostingRegressor = pipeline.named_steps["gbr"]
    importances = gbr.feature_importances_
    print("\nFeature importances (GradientBoostingRegressor):")
    for name, imp in sorted(zip(FEATURE_NAMES, importances), key=lambda x: -x[1]):
        print(f"  {name:<25} {imp:.4f}")

    return pipeline


# ── Scoring ────────────────────────────────────────────────────────────────────


def score_topics(topics: list[dict]) -> list[tuple[dict, float]]:
    """Aplica o ranker a uma lista de tópicos e retorna ordenados por score previsto.

    Args:
        topics: lista de dicts com chaves: similarity_score, title, created_at.
                Chaves ausentes recebem valor default (0.0 / "").

    Returns:
        Lista de (topic_dict, predicted_score) ordenada por score DESC.

    Raises:
        FileNotFoundError: se models/ranker.pkl não existir.
    """
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modelo não encontrado em {MODEL_PATH}. Execute: uv run python ranker.py train")

    pipeline: Pipeline = joblib.load(MODEL_PATH)

    X_rows = [_extract_features(t) for t in topics]
    X = np.array(X_rows, dtype=float)
    scores = pipeline.predict(X).tolist()

    ranked = sorted(zip(topics, scores), key=lambda x: x[1], reverse=True)
    return [(topic, float(score)) for topic, score in ranked]


# ── Execução CLI ───────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import argparse

    import psycopg2
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Ranker de tópicos — Apogee Engine")
    parser.add_argument("command", choices=["train"], help="Comando a executar")
    args = parser.parse_args()

    if args.command == "train":
        db_url = os.environ.get("SUPABASE_DB_URL")
        if not db_url:
            print("Erro: SUPABASE_DB_URL não definido no .env")
            sys.exit(1)

        print("Conectando ao banco...")
        conn = psycopg2.connect(db_url, connect_timeout=10)

        try:
            df = pd.read_sql(
                """
                SELECT
                    t.title,
                    COALESCE(t.similarity_score, 0.0) AS similarity_score,
                    t.created_at,
                    AVG(pd.avg_view_duration_sec) AS avg_view_duration_sec
                FROM topics t
                JOIN videos v ON v.topic_id = t.id
                JOIN performance_daily pd ON pd.video_id = v.id
                WHERE pd.avg_view_duration_sec IS NOT NULL
                GROUP BY t.id, t.title, t.similarity_score, t.created_at
                """,
                conn,
            )
        finally:
            conn.close()

        print(f"Registros encontrados: {len(df)}")

        if len(df) < 10:
            print(
                f"Dados insuficientes para treino: {len(df)} registros (mínimo 10). "
                "Importe mais dados via scripts/import_metrics.py."
            )
            sys.exit(1)

        pipeline = train_ranker(df)
        print(f"\nModelo salvo em {MODEL_PATH}")
