"""
ICAE — Dashboard Interativo (Streamlit)

Execução:
    streamlit run dashboard/app.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from ingest.loader import generate_sample_data
from model.icae_model import ICAEModel, WeightConfig
from index.exporter import build_ranking, build_municipio_summary

st.set_page_config(
    page_title="ICAE — Índice de Coerência Ambiental Econômica",
    page_icon="🌿",
    layout="wide",
)

# ─── Sidebar ────────────────────────────────────────────────

st.sidebar.title("⚙️ Configuração de Pesos")
st.sidebar.markdown("Os pesos **α** controlam a composição do Risco Ambiental. Soma deve ser 1.0.")

alpha1 = st.sidebar.slider("α1 Desmatamento", 0.0, 1.0, 0.25, 0.05)
alpha2 = st.sidebar.slider("α2 Multas", 0.0, 1.0, 0.25, 0.05)
alpha3 = st.sidebar.slider("α3 Reincidência", 0.0, 1.0, 0.25, 0.05)
alpha4 = st.sidebar.slider("α4 Embargo", 0.0, 1.0, 0.25, 0.05)

total = alpha1 + alpha2 + alpha3 + alpha4
if not np.isclose(total, 1.0, atol=0.02):
    st.sidebar.error(f"⚠️ Soma dos pesos = {total:.2f}. Deve ser 1.0.")
    st.stop()

try:
    weights = WeightConfig(
        alpha1_desmatamento=alpha1,
        alpha2_multas=alpha2,
        alpha3_reincidencia=alpha3,
        alpha4_embargo=alpha4,
    )
except ValueError as e:
    st.sidebar.error(str(e))
    st.stop()

n_entities = st.sidebar.slider("Entidades (demo)", 50, 500, 100, 50)

# ─── Dados ──────────────────────────────────────────────────

@st.cache_data
def load_data(n: int, a1: float, a2: float, a3: float, a4: float) -> pd.DataFrame:
    raw = generate_sample_data(n=n)
    w = WeightConfig(alpha1_desmatamento=a1, alpha2_multas=a2,
                     alpha3_reincidencia=a3, alpha4_embargo=a4)
    model = ICAEModel(w)
    return model.fit_transform(raw)

df = load_data(n_entities, alpha1, alpha2, alpha3, alpha4)
ranking = build_ranking(df)

# ─── Header ─────────────────────────────────────────────────

st.title("🌿 ICAE — Índice de Coerência Ambiental Econômica")
st.markdown(
    "> Mede o grau de coerência entre incentivos econômicos públicos "
    "e desempenho ambiental territorial. **Open source · Auditável · Reproduzível.**"
)

# ─── KPIs ───────────────────────────────────────────────────

col1, col2, col3, col4 = st.columns(4)
col1.metric("Entidades", len(df))
col2.metric("ICAE Médio", f"{df['icae'].mean():.3f}")
col3.metric("Risco Médio", f"{df['risk'].mean():.3f}")
embargos = int(df["embargo"].sum()) if "embargo" in df.columns else "-"
col4.metric("Embargos Ativos", embargos)

st.divider()

# ─── Fórmula ────────────────────────────────────────────────

with st.expander("📐 Fórmula do Índice (Transparência Total)", expanded=False):
    st.latex(r"X_{norm} = \frac{X - \min(X)}{\max(X) - \min(X)}")
    st.latex(
        rf"Risk_i = {alpha1}\cdot\Delta D_i + {alpha2}\cdot M_i "
        rf"+ {alpha3}\cdot R_i + {alpha4}\cdot Em_i"
    )
    st.latex(r"ICAE_i = (1 - Risk_i) \cdot (1 - Cr_i)")
    st.markdown("**Propriedades:** `0 ≤ ICAE ≤ 1` · Monótono decrescente com risco e crédito incoerente")

# ─── Distribuição do ICAE ───────────────────────────────────

st.subheader("📊 Distribuição do ICAE")

col_hist, col_scatter = st.columns(2)

with col_hist:
    fig_hist = px.histogram(
        df, x="icae", nbins=30,
        color_discrete_sequence=["#2E7D32"],
        title="Histograma do ICAE",
        labels={"icae": "ICAE"},
    )
    fig_hist.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_hist, use_container_width=True)

with col_scatter:
    fig_scatter = px.scatter(
        df, x="credito_norm", y="risk",
        color="icae", color_continuous_scale="RdYlGn",
        title="Crédito vs Risco (cor = ICAE)",
        labels={
            "credito_norm": "Crédito Normalizado",
            "risk": "Risco Ambiental",
            "icae": "ICAE",
        },
        hover_data=["entity_id", "municipio"],
    )
    fig_scatter.update_layout(height=350)
    st.plotly_chart(fig_scatter, use_container_width=True)

# ─── Ranking ────────────────────────────────────────────────

st.subheader("🏆 Ranking ICAE")

top_n = st.slider("Top N entidades", 5, 50, 20)
top = ranking.head(top_n)

fig_bar = px.bar(
    top,
    x="icae", y="entity_id",
    orientation="h",
    color="icae",
    color_continuous_scale="RdYlGn",
    title=f"Top {top_n} por ICAE",
    labels={"icae": "ICAE", "entity_id": "Entidade"},
    hover_data=["municipio", "risk"],
)
fig_bar.update_layout(height=500, yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig_bar, use_container_width=True)

# ─── Por Município ──────────────────────────────────────────

st.subheader("🗺️ ICAE por Município")

mun_df = build_municipio_summary(df)
fig_mun = px.bar(
    mun_df, x="municipio", y="icae_medio",
    color="icae_medio", color_continuous_scale="RdYlGn",
    error_y=None,
    title="ICAE Médio por Município",
    labels={"icae_medio": "ICAE Médio", "municipio": "Município"},
    hover_data=["n_entidades", "risk_medio"],
)
fig_mun.update_layout(height=350)
st.plotly_chart(fig_mun, use_container_width=True)

# ─── Tabela auditável ───────────────────────────────────────

st.subheader("🔍 Tabela Auditável")

audit_cols = ["rank", "entity_id", "nome", "municipio",
              "icae", "risk", "credito_norm",
              "delta_desmat_norm", "multas_norm", "reincidencia_norm", "embargo_norm"]
show_cols = [c for c in audit_cols if c in ranking.columns]

st.dataframe(
    ranking[show_cols].style.background_gradient(subset=["icae"], cmap="RdYlGn"),
    use_container_width=True, height=400,
)

csv = ranking[show_cols].to_csv(index=False)
st.download_button("⬇️ Exportar CSV", data=csv, file_name="icae_ranking.csv", mime="text/csv")

# ─── Footer ─────────────────────────────────────────────────

st.divider()
st.caption(
    "ICAE v1.0.0 · Licença AGPL-3.0 · "
    "Transparência não é discurso — é arquitetura."
)
