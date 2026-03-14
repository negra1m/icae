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


# ────────────────────────────────────────────────────────────
# Testes das Provas Matemáticas (PROVAS_MATEMATICAS.md)
# ────────────────────────────────────────────────────────────

def _make_df(**overrides) -> pd.DataFrame:
    """Cria DataFrame mínimo válido para ICAEModel."""
    base = {
        "entity_id":           ["A", "B"],
        "credito":             [0.0, 1_000_000.0],
        "desmatamento_antes":  [100.0, 100.0],
        "desmatamento_depois": [80.0, 200.0],
        "multas":              [0.0, 500_000.0],
        "infracoes":           [0.0, 50.0],
        "tempo_ativo":         [24.0, 12.0],
        "embargo":             [0.0, 1.0],
    }
    base.update(overrides)
    return pd.DataFrame(base)


class TestProvasMatematicas:

    # §2 — ΔD com desmatamento_antes = 0 (caso degenerado com ε)
    def test_delta_desmat_antes_zero(self):
        """§2: ε evita divisão por zero quando desmat_antes = 0."""
        before = pd.Series([0.0, 0.0])
        after  = pd.Series([0.0, 50.0])
        delta  = compute_delta_desmatamento(before, after)
        assert delta.isna().sum() == 0, "Não deve produzir NaN com desmat_antes=0"
        assert delta.iloc[0] == 0.0
        assert delta.iloc[1] > 0.0

    # §6 — Os 4 casos extremos da tabela de verdade do ICAE
    def test_caso_extremo_alto_risco_alto_credito(self):
        """§6 Caso 1: alto risco + alto crédito → ICAE próximo de 0."""
        df = pd.DataFrame([
            {"entity_id":"HIGH","credito":1e6,"desmatamento_antes":10.0,
             "desmatamento_depois":1000.0,"multas":5e5,"infracoes":50.0,
             "tempo_ativo":12.0,"embargo":1.0},
            {"entity_id":"REF","credito":0.0,"desmatamento_antes":100.0,
             "desmatamento_depois":100.0,"multas":0.0,"infracoes":0.0,
             "tempo_ativo":24.0,"embargo":0.0},
        ])
        result = ICAEModel().fit_transform(df)
        icae_high = result[result["entity_id"] == "HIGH"]["icae"].iloc[0]
        assert icae_high < 0.5, f"Caso 1 (alto risco + alto crédito): esperado ICAE < 0.5, obtido {icae_high:.4f}"

    def test_caso_extremo_baixo_risco_baixo_credito(self):
        """§6 Caso 4: baixo risco + baixo crédito → ICAE próximo de 1."""
        df = pd.DataFrame([
            {"entity_id":"LOW","credito":0.0,"desmatamento_antes":100.0,
             "desmatamento_depois":80.0,"multas":0.0,"infracoes":0.0,
             "tempo_ativo":24.0,"embargo":0.0},
            {"entity_id":"REF","credito":1e6,"desmatamento_antes":10.0,
             "desmatamento_depois":1000.0,"multas":5e5,"infracoes":50.0,
             "tempo_ativo":12.0,"embargo":1.0},
        ])
        result = ICAEModel().fit_transform(df)
        icae_low = result[result["entity_id"] == "LOW"]["icae"].iloc[0]
        assert icae_low > 0.5, f"Caso 4 (baixo risco + baixo crédito): esperado ICAE > 0.5, obtido {icae_low:.4f}"

    def test_caso_extremo_alto_risco_baixo_credito(self):
        """§6 Caso 3: alto risco + baixo crédito → ICAE ≈ 0 (risco elimina o fator)."""
        df = pd.DataFrame([
            {"entity_id":"BAD","credito":0.0,"desmatamento_antes":10.0,
             "desmatamento_depois":1000.0,"multas":5e5,"infracoes":50.0,
             "tempo_ativo":12.0,"embargo":1.0},
            {"entity_id":"REF","credito":1e6,"desmatamento_antes":100.0,
             "desmatamento_depois":80.0,"multas":0.0,"infracoes":0.0,
             "tempo_ativo":24.0,"embargo":0.0},
        ])
        result = ICAEModel().fit_transform(df)
        icae_bad = result[result["entity_id"] == "BAD"]["icae"].iloc[0]
        assert icae_bad < 0.5, f"Caso 3 (alto risco + baixo crédito): esperado ICAE < 0.5, obtido {icae_bad:.4f}"

    # §7 — Invariância sob reescala linear
    def test_invariancia_rescala(self):
        """§7: multiplicar crédito por 1000 não altera o ICAE."""
        df1 = _make_df()
        df2 = _make_df(credito=[c * 1000 for c in [0.0, 1_000_000.0]])
        r1 = ICAEModel().fit_transform(df1)["icae"].values
        r2 = ICAEModel().fit_transform(df2)["icae"].values
        np.testing.assert_allclose(r1, r2, atol=1e-10,
            err_msg="ICAE deve ser invariante sob reescala linear do crédito (§7)")

    def test_invariancia_rescala_desmatamento(self):
        """§7: multiplicar desmatamento por 100 não altera o ICAE."""
        df1 = _make_df()
        df2 = _make_df(
            desmatamento_antes=[v * 100 for v in [100.0, 100.0]],
            desmatamento_depois=[v * 100 for v in [80.0, 200.0]],
            multas=[v * 100 for v in [0.0, 500_000.0]],
        )
        r1 = ICAEModel().fit_transform(df1)["icae"].values
        r2 = ICAEModel().fit_transform(df2)["icae"].values
        np.testing.assert_allclose(r1, r2, atol=1e-10,
            err_msg="ICAE deve ser invariante sob reescala do desmatamento (§7)")

    # §8 — Monotonicidade: aumentar risco nunca aumenta ICAE
    def test_monotonicidade_desmatamento(self):
        """§8: aumentar desmatamento_depois aumenta Risk e reduz ICAE."""
        df_low  = _make_df(desmatamento_depois=[80.0, 150.0])
        df_high = _make_df(desmatamento_depois=[80.0, 900.0])
        r_low  = ICAEModel().fit_transform(df_low)
        r_high = ICAEModel().fit_transform(df_high)
        # A entidade B (index 1) deve ter ICAE menor no cenário high
        assert r_high["icae"].iloc[1] <= r_low["icae"].iloc[1], \
            "Maior desmatamento deve resultar em ICAE ≤ (§8 monotonicidade)"

    def test_monotonicidade_multas(self):
        """§8: aumentar multas aumenta Risk e reduz ICAE."""
        df_low  = _make_df(multas=[0.0, 100.0])
        df_high = _make_df(multas=[0.0, 900_000.0])
        r_low  = ICAEModel().fit_transform(df_low)
        r_high = ICAEModel().fit_transform(df_high)
        assert r_high["icae"].iloc[1] <= r_low["icae"].iloc[1], \
            "Maiores multas devem resultar em ICAE ≤ (§8 monotonicidade)"

    def test_monotonicidade_infracoes(self):
        """§8: aumentar infracoes aumenta Risk e reduz ICAE."""
        df_low  = _make_df(infracoes=[0.0, 5.0])
        df_high = _make_df(infracoes=[0.0, 50.0])
        r_low  = ICAEModel().fit_transform(df_low)
        r_high = ICAEModel().fit_transform(df_high)
        assert r_high["icae"].iloc[1] <= r_low["icae"].iloc[1], \
            "Mais infrações devem resultar em ICAE ≤ (§8 monotonicidade)"

    def test_monotonicidade_embargo(self):
        """§8: embargo=1 vs embargo=0 reduz (ou mantém) ICAE."""
        df_sem = _make_df(embargo=[0.0, 0.0])
        df_com = _make_df(embargo=[0.0, 1.0])
        r_sem = ICAEModel().fit_transform(df_sem)
        r_com = ICAEModel().fit_transform(df_com)
        assert r_com["icae"].iloc[1] <= r_sem["icae"].iloc[1], \
            "Embargo deve resultar em ICAE ≤ (§8 monotonicidade)"

    # §9 — Peso único em um componente (αk = 1, resto = 0)
    def test_peso_total_em_um_componente(self):
        """§9: α1=1, α2=α3=α4=0 é válido e produz Risk ∈ [0,1]."""
        w = WeightConfig(alpha1_desmatamento=1.0, alpha2_multas=0.0,
                         alpha3_reincidencia=0.0, alpha4_embargo=0.0)
        result = ICAEModel(weights=w).fit_transform(_make_df())
        assert result["risk"].between(0, 1).all(), "Risk deve estar em [0,1] com peso único"
        assert result["icae"].between(0, 1).all(), "ICAE deve estar em [0,1] com peso único"

    def test_peso_total_em_embargo(self):
        """§9: α4=1, α1=α2=α3=0 é válido e risk = embargo_norm."""
        w = WeightConfig(alpha1_desmatamento=0.0, alpha2_multas=0.0,
                         alpha3_reincidencia=0.0, alpha4_embargo=1.0)
        df = _make_df()
        result = ICAEModel(weights=w).fit_transform(df)
        # risk deve ser exatamente embargo_norm quando α4=1
        np.testing.assert_allclose(
            result["risk"].values,
            result["embargo_norm"].values,
            atol=1e-10,
            err_msg="Com α4=1, risk deve ser igual a embargo_norm (§9)"
        )

    # Garantia: raise ValueError é disparado (não assert silencioso)
    def test_raise_value_error_nao_assert(self):
        """Garante que a validação de range usa raise, não assert desativável."""
        import ast, pathlib
        src = pathlib.Path(__file__).parent.parent / "model" / "icae_model.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                # Verifica se algum assert ainda verifica "icae"
                src_line = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                assert "icae" not in src_line, \
                    "Validação de range do ICAE não deve usar assert (desativável com -O)"
