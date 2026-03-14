"""
ICAE — Módulo de Modelo
Implementa normalização, cálculo do Risk Vector e do Índice ICAE.

Fórmulas públicas e auditáveis:
    X_norm = (X - min(X)) / (max(X) - min(X))
    Risk_i  = α1·ΔD_i + α2·M_i + α3·R_i + α4·Em_i
    ICAE_i  = (1 − Risk_i) · (1 − Cr_i)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class WeightConfig:
    """
    Pesos do vetor de risco ambiental.
    Todos os pesos são públicos e auditáveis.
    Restrição: α1 + α2 + α3 + α4 = 1, αk ≥ 0
    """
    alpha1_desmatamento: float = 0.25
    alpha2_multas:       float = 0.25
    alpha3_reincidencia: float = 0.25
    alpha4_embargo:      float = 0.25

    def __post_init__(self):
        alphas = [
            self.alpha1_desmatamento,
            self.alpha2_multas,
            self.alpha3_reincidencia,
            self.alpha4_embargo,
        ]
        if any(a < 0 for a in alphas):
            raise ValueError("Todos os pesos αk devem ser ≥ 0.")
        total = sum(alphas)
        if not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(f"Soma dos pesos deve ser 1.0, obtido: {total:.6f}")

    def as_dict(self) -> dict:
        return {
            "alpha1_desmatamento": self.alpha1_desmatamento,
            "alpha2_multas":       self.alpha2_multas,
            "alpha3_reincidencia": self.alpha3_reincidencia,
            "alpha4_embargo":      self.alpha4_embargo,
        }


def min_max_normalize(series: pd.Series) -> pd.Series:
    """
    Normalização Min-Max:
        X_norm = (X - min(X)) / (max(X) - min(X))
    Garante: 0 ≤ X_norm ≤ 1
    Se max == min, retorna 0 para todos (série constante).
    """
    mn, mx = series.min(), series.max()
    if np.isclose(mn, mx):
        logger.warning(f"Série '{series.name}' é constante ({mn}). Normalizada para 0.")
        return pd.Series(np.zeros(len(series)), index=series.index, name=series.name)
    return (series - mn) / (mx - mn)


def compute_delta_desmatamento(
    before: pd.Series, after: pd.Series
) -> pd.Series:
    """
    Variação percentual de desmatamento pós-incentivo (Regra 1 — Temporalidade).
    ΔD_i = (after_i - before_i) / (before_i + ε)
    Valores negativos (redução) são clipados em 0 (não recompensa, apenas penaliza).
    """
    epsilon = 1e-6
    delta = (after - before) / (before + epsilon)
    return delta.clip(lower=0)  # só penaliza aumento


def compute_reincidencia(
    infracoes: pd.Series, tempo_ativo: pd.Series
) -> pd.Series:
    """
    Índice de Reincidência (Regra 3):
        R_i = infracoes_i / tempo_ativo_i
    Evita viés contra propriedades mais antigas.
    """
    epsilon = 1e-6
    return infracoes / (tempo_ativo + epsilon)


class ICAEModel:
    """
    Calculador do Índice de Coerência Ambiental Econômica.

    Parâmetros configuráveis via WeightConfig.
    Todos os passos intermediários são preservados para auditoria.
    """

    def __init__(self, weights: Optional[WeightConfig] = None):
        self.weights = weights or WeightConfig()
        logger.info(f"ICAEModel inicializado com pesos: {self.weights.as_dict()}")

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Executa todo o pipeline de cálculo sobre o DataFrame.
        Retorna DataFrame com colunas intermediárias e ICAE final.
        Dados brutos não são modificados.
        """
        result = df.copy()

        # --- Passo 1: Derivar variáveis ---
        result["_delta_desmat_raw"] = compute_delta_desmatamento(
            df["desmatamento_antes"], df["desmatamento_depois"]
        )
        result["_reincidencia_raw"] = compute_reincidencia(
            df["infracoes"], df["tempo_ativo"]
        )

        # --- Passo 2: Normalizar (Min-Max) ---
        result["delta_desmat_norm"] = min_max_normalize(result["_delta_desmat_raw"])
        result["multas_norm"]       = min_max_normalize(df["multas"])
        result["reincidencia_norm"] = min_max_normalize(result["_reincidencia_raw"])
        result["embargo_norm"]      = df["embargo"].clip(0, 1)  # já binário
        result["credito_norm"]      = min_max_normalize(df["credito"])

        # --- Passo 3: Vetor de Risco Ambiental ---
        w = self.weights
        result["risk"] = (
            w.alpha1_desmatamento * result["delta_desmat_norm"] +
            w.alpha2_multas       * result["multas_norm"] +
            w.alpha3_reincidencia * result["reincidencia_norm"] +
            w.alpha4_embargo      * result["embargo_norm"]
        )

        # --- Passo 4: ICAE ---
        result["icae"] = (1 - result["risk"]) * (1 - result["credito_norm"])

        # Garantia matemática: ICAE ∈ [0, 1]
        # (assert desativado com python -O; usar raise explícito — vide PROVAS_MATEMATICAS §5)
        if not result["icae"].between(0, 1).all():
            violacoes = result[~result["icae"].between(0, 1)][["entity_id", "icae"]]
            raise ValueError(
                f"Violação matemática: ICAE fora de [0,1] em {len(violacoes)} linha(s).\n"
                f"{violacoes.to_string()}"
            )

        logger.info(
            f"ICAE calculado. Média={result['icae'].mean():.4f} "
            f"Std={result['icae'].std():.4f} "
            f"Min={result['icae'].min():.4f} "
            f"Max={result['icae'].max():.4f}"
        )

        return result

    def describe_formula(self) -> str:
        """Retorna descrição textual da fórmula usada (transparência)."""
        w = self.weights
        return (
            "=== FÓRMULA ICAE ===\n"
            f"Risk_i = {w.alpha1_desmatamento}·ΔD_i "
            f"+ {w.alpha2_multas}·M_i "
            f"+ {w.alpha3_reincidencia}·R_i "
            f"+ {w.alpha4_embargo}·Em_i\n"
            "ICAE_i = (1 − Risk_i) · (1 − Cr_i)\n"
            "Onde todos os valores estão normalizados em [0,1].\n"
            f"Pesos: {w.as_dict()}"
        )
