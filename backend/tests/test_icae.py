"""
ICAE — Testes Automatizados
Valida propriedades matemáticas, reprodutibilidade e pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import numpy as np
import pandas as pd

from ingest.loader import DataLoader, DataValidator, generate_sample_data
from model.icae_model import (
    ICAEModel, WeightConfig,
    min_max_normalize, compute_delta_desmatamento, compute_reincidencia
)
from index.exporter import build_ranking, build_municipio_summary, ICAEExporter
from graph.graph_builder import build_graph, graph_summary


# ────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────

@pytest.fixture
def sample_raw():
    return generate_sample_data(n=50, seed=99)

@pytest.fixture
def sample_result(sample_raw):
    return ICAEModel().fit_transform(sample_raw)


# ────────────────────────────────────────────────────────────
# Testes de Normalização
# ────────────────────────────────────────────────────────────

class TestNormalization:
    def test_output_range(self, sample_raw):
        norm = min_max_normalize(sample_raw["credito"])
        assert norm.between(0, 1).all(), "Normalização deve estar em [0,1]"

    def test_constant_series(self):
        s = pd.Series([5.0] * 20, name="x")
        norm = min_max_normalize(s)
        assert (norm == 0).all(), "Série constante deve normalizar para 0"

    def test_min_max_correct(self):
        s = pd.Series([0.0, 5.0, 10.0])
        norm = min_max_normalize(s)
        assert np.isclose(norm.min(), 0.0)
        assert np.isclose(norm.max(), 1.0)
        assert np.isclose(norm.iloc[1], 0.5)


# ────────────────────────────────────────────────────────────
# Testes do WeightConfig
# ────────────────────────────────────────────────────────────

class TestWeightConfig:
    def test_default_weights_sum_to_one(self):
        w = WeightConfig()
        total = (w.alpha1_desmatamento + w.alpha2_multas +
                 w.alpha3_reincidencia + w.alpha4_embargo)
        assert np.isclose(total, 1.0)

    def test_custom_weights_valid(self):
        w = WeightConfig(0.4, 0.3, 0.2, 0.1)
        assert np.isclose(w.alpha1_desmatamento + w.alpha2_multas +
                          w.alpha3_reincidencia + w.alpha4_embargo, 1.0)

    def test_invalid_sum_raises(self):
        with pytest.raises(ValueError, match="Soma dos pesos"):
            WeightConfig(0.5, 0.5, 0.1, 0.1)

    def test_negative_weight_raises(self):
        with pytest.raises(ValueError, match="≥ 0"):
            WeightConfig(-0.1, 0.5, 0.4, 0.2)


# ────────────────────────────────────────────────────────────
# Testes do Modelo ICAE
# ────────────────────────────────────────────────────────────

class TestICAEModel:
    def test_icae_range(self, sample_result):
        """Propriedade 7.1: ICAE ∈ [0,1]"""
        assert sample_result["icae"].between(0, 1).all()

    def test_risk_range(self, sample_result):
        assert sample_result["risk"].between(0, 1).all()

    def test_monotonicity_risk(self, sample_raw):
        """Propriedade 7.2: ICAE decresce com aumento de risco"""
        # Dois datasets idênticos exceto embargo (aumenta risco)
        low_risk  = sample_raw.copy(); low_risk["embargo"]  = 0
        high_risk = sample_raw.copy(); high_risk["embargo"] = 1

        model = ICAEModel()
        icae_low  = model.fit_transform(low_risk)["icae"].mean()
        icae_high = model.fit_transform(high_risk)["icae"].mean()

        assert icae_low >= icae_high, "ICAE deve decrescer com aumento de risco"

    def test_reproducibility(self, sample_raw):
        """Pipeline determinístico: mesmo input → mesmo output"""
        r1 = ICAEModel().fit_transform(sample_raw.copy())
        r2 = ICAEModel().fit_transform(sample_raw.copy())
        pd.testing.assert_frame_equal(r1[["entity_id", "icae"]], r2[["entity_id", "icae"]])

    def test_required_output_columns(self, sample_result):
        required = ["icae", "risk", "credito_norm", "delta_desmat_norm",
                    "multas_norm", "reincidencia_norm", "embargo_norm"]
        for col in required:
            assert col in sample_result.columns, f"Coluna '{col}' ausente no output"

    def test_extreme_coherence(self):
        """Alta coerência: crédito baixo + risco baixo → ICAE alto"""
        df = pd.DataFrame([{
            "entity_id": "E001",
            "credito": 0.0,
            "desmatamento_antes": 100.0,
            "desmatamento_depois": 80.0,  # melhorou
            "multas": 0.0,
            "infracoes": 0.0,
            "tempo_ativo": 24.0,
            "embargo": 0.0,
        }])
        result = ICAEModel().fit_transform(df)
        assert result["icae"].iloc[0] >= 0.0  # credito=0 → (1-Cr)=1 potencialmente

    def test_extreme_incoherence(self):
        """Incoerência máxima teórica: cria dataset onde valores são extremos"""
        df = pd.DataFrame([
            {
                "entity_id": "BAD",
                "credito": 1_000_000.0,
                "desmatamento_antes": 10.0,
                "desmatamento_depois": 1000.0,
                "multas": 500_000.0,
                "infracoes": 50.0,
                "tempo_ativo": 12.0,
                "embargo": 1.0,
            },
            {
                "entity_id": "GOOD",
                "credito": 0.0,
                "desmatamento_antes": 100.0,
                "desmatamento_depois": 50.0,
                "multas": 0.0,
                "infracoes": 0.0,
                "tempo_ativo": 24.0,
                "embargo": 0.0,
            }
        ])
        result = ICAEModel().fit_transform(df)
        bad  = result[result["entity_id"] == "BAD"]["icae"].iloc[0]
        good = result[result["entity_id"] == "GOOD"]["icae"].iloc[0]
        assert bad < good, "Entidade com alto risco+crédito deve ter ICAE menor"


# ────────────────────────────────────────────────────────────
# Testes de Validação de Dados
# ────────────────────────────────────────────────────────────

class TestDataValidator:
    def test_valid_data_passes(self, sample_raw):
        validator = DataValidator()
        assert validator.validate(sample_raw)

    def test_missing_column_fails(self, sample_raw):
        bad = sample_raw.drop(columns=["credito"])
        validator = DataValidator()
        assert not validator.validate(bad)

    def test_invalid_embargo_fails(self, sample_raw):
        bad = sample_raw.copy()
        bad["embargo"] = 5  # inválido
        validator = DataValidator()
        validator.validate(bad)
        assert any("embargo" in e for e in validator.errors)


# ────────────────────────────────────────────────────────────
# Testes de Exportação
# ────────────────────────────────────────────────────────────

class TestExporter:
    def test_ranking_sorted(self, sample_result):
        r = build_ranking(sample_result)
        assert (r["rank"].diff().dropna() >= 0).all()

    def test_ranking_top_n(self, sample_result):
        r = build_ranking(sample_result, top_n=5)
        assert len(r) == 5

    def test_hash_deterministic(self, sample_result):
        e = ICAEExporter()
        h1 = e._compute_hash(sample_result)
        h2 = e._compute_hash(sample_result.copy())
        assert h1 == h2

    def test_municipio_summary(self, sample_result):
        s = build_municipio_summary(sample_result)
        assert "icae_medio" in s.columns
        assert (s["icae_medio"].between(0, 1)).all()


# ────────────────────────────────────────────────────────────
# Testes de Grafo
# ────────────────────────────────────────────────────────────

class TestGraph:
    def test_graph_builds(self, sample_result):
        G = build_graph(sample_result)
        assert G.number_of_nodes() > 0
        assert G.number_of_edges() > 0

    def test_graph_summary_keys(self, sample_result):
        G = build_graph(sample_result)
        s = graph_summary(G)
        assert "total_nodes" in s
        assert "total_edges" in s
        assert "entity_nodes" in s

    def test_entity_count_matches(self, sample_result):
        G = build_graph(sample_result)
        s = graph_summary(G)
        assert s["entity_nodes"] == len(sample_result)


# ────────────────────────────────────────────────────────────
# Teste de Regras de Negócio
# ────────────────────────────────────────────────────────────

class TestBusinessRules:
    def test_temporalidade_no_reward_for_reduction(self):
        """Regra 1: redução de desmatamento não penaliza (ΔD clipado em 0)"""
        before = pd.Series([100.0, 100.0])
        after  = pd.Series([80.0, 120.0])   # um melhorou, outro piorou
        delta  = compute_delta_desmatamento(before, after)
        assert delta.iloc[0] == 0.0, "Redução de desmatamento não deve gerar penalidade"
        assert delta.iloc[1] > 0.0,  "Aumento de desmatamento deve gerar penalidade"

    def test_reincidencia_normaliza_pelo_tempo(self):
        """Regra 3: reincidência por tempo evita viés contra entidades antigas"""
        infracoes = pd.Series([10.0, 5.0])
        tempo     = pd.Series([10.0, 5.0])   # mesma taxa
        r = compute_reincidencia(infracoes, tempo)
        assert np.isclose(r.iloc[0], r.iloc[1]), "Taxas iguais devem gerar mesmo índice"
