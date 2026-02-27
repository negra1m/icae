"""
ICAE — Validação Estatística
Análise de sensibilidade dos pesos, bootstrap e Monte Carlo.
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def sensitivity_analysis(
    df_normalized: pd.DataFrame,
    n_samples: int = 1000,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Análise de sensibilidade dos pesos α via perturbação aleatória.
    Para cada amostra, gera pesos aleatórios válidos (soma=1) e recalcula ICAE.
    Retorna estatísticas de variação do ranking.
    """
    from model.icae_model import ICAEModel, WeightConfig

    rng = np.random.default_rng(seed)
    base_ranks = []
    all_ranks = []

    # Ranking base (pesos iguais)
    base = ICAEModel().fit_transform(df_normalized)
    base_rank = base["icae"].rank(ascending=False)

    for _ in range(n_samples):
        # Gera pesos aleatórios com restrição de soma=1
        raw = rng.dirichlet(np.ones(4))
        w = WeightConfig(
            alpha1_desmatamento=float(raw[0]),
            alpha2_multas=float(raw[1]),
            alpha3_reincidencia=float(raw[2]),
            alpha4_embargo=float(raw[3]),
        )
        result = ICAEModel(w).fit_transform(df_normalized)
        rank = result["icae"].rank(ascending=False)
        all_ranks.append(rank.values)

    rank_matrix = np.array(all_ranks)
    rank_std = rank_matrix.std(axis=0)
    rank_mean = rank_matrix.mean(axis=0)

    return pd.DataFrame({
        "entity_id": df_normalized["entity_id"],
        "icae_base": base["icae"].values,
        "rank_base": base_rank.values,
        "rank_mean": rank_mean,
        "rank_std":  rank_std,
        "rank_cv":   rank_std / (rank_mean + 1e-6),
    })


def bootstrap_stability(
    df_raw: pd.DataFrame,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Bootstrap para estabilidade do ranking ICAE.
    Reamostra com reposição e avalia variância do score.
    """
    from model.icae_model import ICAEModel

    rng = np.random.default_rng(seed)
    model = ICAEModel()
    n = len(df_raw)
    scores = []

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sample = df_raw.iloc[idx].copy().reset_index(drop=True)
        try:
            result = model.fit_transform(sample)
            scores.append(result.set_index("entity_id")["icae"])
        except Exception:
            continue

    score_df = pd.DataFrame(scores)
    return pd.DataFrame({
        "entity_id": score_df.columns,
        "icae_mean": score_df.mean().values,
        "icae_std":  score_df.std().values,
        "icae_ci_low":  score_df.quantile(0.025).values,
        "icae_ci_high": score_df.quantile(0.975).values,
    })


def monte_carlo_robustness(
    df_raw: pd.DataFrame,
    n_simulations: int = 1000,
    noise_scale: float = 0.05,
    seed: int = 42,
) -> dict:
    """
    Simulação Monte Carlo: adiciona ruído gaussiano proporcional aos dados
    e avalia robustez do ICAE médio.
    """
    from model.icae_model import ICAEModel

    rng = np.random.default_rng(seed)
    model = ICAEModel()
    numeric_cols = ["credito", "desmatamento_antes", "desmatamento_depois",
                    "multas", "infracoes", "tempo_ativo"]

    icae_means = []

    for _ in range(n_simulations):
        perturbed = df_raw.copy()
        for col in numeric_cols:
            if col in perturbed.columns:
                noise = rng.normal(0, noise_scale * perturbed[col].std(), len(perturbed))
                perturbed[col] = (perturbed[col] + noise).clip(lower=0)
        try:
            result = model.fit_transform(perturbed)
            icae_means.append(result["icae"].mean())
        except Exception:
            continue

    arr = np.array(icae_means)
    return {
        "n_simulations": n_simulations,
        "noise_scale":   noise_scale,
        "mean":   float(arr.mean()),
        "std":    float(arr.std()),
        "ci_95_low":  float(np.percentile(arr, 2.5)),
        "ci_95_high": float(np.percentile(arr, 97.5)),
    }
