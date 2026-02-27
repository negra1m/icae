"""
ICAE — Pipeline Principal
Orquestra ETL → Normalização → Cálculo → Grafo → Export.
Pipeline determinístico e reproduzível.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd
import logging
from pathlib import Path
from typing import Optional

from ingest.loader import DataLoader, generate_sample_data
from model.icae_model import ICAEModel, WeightConfig
from graph.graph_builder import build_graph, graph_summary
from index.exporter import ICAEExporter, build_ranking, build_municipio_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("icae.pipeline")


def run(
    source: str | Path | pd.DataFrame | None = None,
    weights: Optional[WeightConfig] = None,
    output_dir: str | Path = "./output",
    window_months: int = 24,
    n_demo: int = 100,
) -> pd.DataFrame:
    """
    Executa o pipeline completo do ICAE.

    Args:
        source:        CSV path, DataFrame, ou None (gera dados demo)
        weights:       WeightConfig com pesos αk (padrão: iguais)
        output_dir:    Diretório para exportação de resultados
        window_months: Janela de observação pós-incentivo em meses
        n_demo:        Tamanho do dataset demo (se source=None)

    Returns:
        DataFrame com resultados do ICAE e colunas intermediárias
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("ICAE PIPELINE — INÍCIO")
    logger.info("=" * 60)

    # ── Etapa 1: Ingestão ──────────────────────────────────────
    logger.info("[1/5] Ingestão de dados")

    if source is None:
        logger.info(f"Gerando dados sintéticos (n={n_demo})")
        raw = generate_sample_data(n=n_demo)
    elif isinstance(source, pd.DataFrame):
        loader = DataLoader(window_months=window_months)
        raw = loader.load_dataframe(source)
    else:
        loader = DataLoader(window_months=window_months)
        raw = loader.load_csv(source)

    logger.info(f"Registros carregados: {len(raw)}")

    # ── Etapa 2: Cálculo do ICAE ───────────────────────────────
    logger.info("[2/5] Calculando índice ICAE")

    model = ICAEModel(weights or WeightConfig())
    logger.info(model.describe_formula())
    df_result = model.fit_transform(raw)

    # ── Etapa 3: Grafo ─────────────────────────────────────────
    logger.info("[3/5] Construindo grafo relacional")

    G = build_graph(df_result)
    summary = graph_summary(G)
    logger.info(f"Grafo: {summary}")

    # ── Etapa 4: Exportação ────────────────────────────────────
    logger.info("[4/5] Exportando resultados")

    exporter = ICAEExporter(weights_config=(weights or WeightConfig()).as_dict())
    csv_path  = exporter.to_csv(df_result,  output_dir / "icae_resultados.csv")
    json_path = exporter.to_json(df_result, output_dir / "icae_resultados.json")

    logger.info(f"CSV exportado:  {csv_path}")
    logger.info(f"JSON exportado: {json_path}")

    # ── Etapa 5: Sumário ───────────────────────────────────────
    logger.info("[5/5] Sumário final")

    ranking = build_ranking(df_result, top_n=10)
    mun_summary = build_municipio_summary(df_result)

    logger.info("\n=== TOP 10 ENTIDADES POR ICAE ===")
    logger.info(ranking[["rank", "entity_id", "municipio", "icae", "risk"]].to_string(index=False))

    logger.info("\n=== ICAE MÉDIO POR MUNICÍPIO ===")
    logger.info(mun_summary.to_string(index=False))

    logger.info("=" * 60)
    logger.info("ICAE PIPELINE — CONCLUÍDO")
    logger.info("=" * 60)

    return df_result


if __name__ == "__main__":
    results = run(output_dir="./output")
    print(f"\nResultados disponíveis: {len(results)} entidades")
    print(f"ICAE médio: {results['icae'].mean():.4f}")
    print(f"Arquivos gerados em: ./output/")
