"""
ICAE — Módulo de Index
Exportação, versionamento e ranking do índice.
"""

import pandas as pd
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Colunas de auditoria sempre incluídas no export
AUDIT_COLUMNS = [
    "entity_id", "icae", "risk", "credito_norm",
    "delta_desmat_norm", "multas_norm", "reincidencia_norm", "embargo_norm",
]

# Colunas opcionais de contexto
CONTEXT_COLUMNS = ["nome", "municipio", "uf"]


class ICAEExporter:
    """
    Exporta resultados do ICAE com metadados de auditoria.
    Cada exportação é identificável por hash determinístico.
    """

    def __init__(self, weights_config: Optional[dict] = None):
        self.weights_config = weights_config or {}
        self.export_time = datetime.now(timezone.utc).isoformat()

    def _compute_hash(self, df: pd.DataFrame) -> str:
        """Hash SHA-256 do DataFrame de resultados (reprodutibilidade)."""
        csv_bytes = df[AUDIT_COLUMNS].round(8).to_csv(index=False).encode()
        return hashlib.sha256(csv_bytes).hexdigest()[:16]

    def to_csv(self, df: pd.DataFrame, path: str | Path) -> Path:
        path = Path(path)
        export_df = self._prepare_export(df)
        export_df.to_csv(path, index=False)
        logger.info(f"Exportado CSV: {path} ({len(export_df)} registros)")
        return path

    def to_json(self, df: pd.DataFrame, path: str | Path) -> Path:
        path = Path(path)
        export_df = self._prepare_export(df)
        payload = {
            "metadata": self._build_metadata(df),
            "results":  export_df.to_dict(orient="records"),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"Exportado JSON: {path}")
        return path

    def _prepare_export(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in CONTEXT_COLUMNS if c in df.columns]
        cols += [c for c in AUDIT_COLUMNS if c in df.columns]
        export = df[cols].copy()
        export["rank"] = export["icae"].rank(ascending=False, method="min").astype(int)
        export = export.sort_values("rank")
        return export

    def _build_metadata(self, df: pd.DataFrame) -> dict:
        return {
            "version":      "1.0.0",
            "timestamp":    self.export_time,
            "n_entities":   len(df),
            "weights":      self.weights_config,
            "icae_hash":    self._compute_hash(df),
            "icae_mean":    float(df["icae"].mean()) if "icae" in df.columns else None,
            "icae_std":     float(df["icae"].std()) if "icae" in df.columns else None,
        }


def build_ranking(df_icae: pd.DataFrame, top_n: Optional[int] = None) -> pd.DataFrame:
    """
    Constrói ranking ordenado do ICAE.
    top_n: se fornecido, retorna apenas as top_n entidades.
    """
    cols = [c for c in CONTEXT_COLUMNS + AUDIT_COLUMNS if c in df_icae.columns]
    ranking = df_icae[cols].copy()
    ranking["rank"] = ranking["icae"].rank(ascending=False, method="min").astype(int)
    ranking = ranking.sort_values("rank").reset_index(drop=True)

    if top_n:
        ranking = ranking.head(top_n)

    return ranking


def build_municipio_summary(df_icae: pd.DataFrame) -> pd.DataFrame:
    """Agrega estatísticas ICAE por município."""
    if "municipio" not in df_icae.columns:
        raise ValueError("Coluna 'municipio' não encontrada.")

    return (
        df_icae.groupby("municipio")
        .agg(
            n_entidades=("entity_id", "count"),
            icae_medio=("icae", "mean"),
            icae_min=("icae", "min"),
            icae_max=("icae", "max"),
            risk_medio=("risk", "mean"),
        )
        .round(4)
        .sort_values("icae_medio")
        .reset_index()
    )
