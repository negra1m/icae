"""
ICAE — API REST Nacional
Fontes: SICOR/BCB + PRODES/INPE (todos biomas) + IBGE
"""
import sys, os, time, asyncio, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import pandas as pd
import logging

from ingest.loader import fetch_dados_reais, fetch_ibge_municipios, generate_sample_data
from ingest.private_incentives import fetch_incentivos_privados, SH4_AGRO
from model.icae_model import ICAEModel, WeightConfig
from index.exporter import build_ranking, build_municipio_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ICAE", version="2.0.0", license_info={"name":"AGPL-3.0"})
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_cache: dict = {
    "df": None, "fonte": "demo",
    "ultima_atualizacao": None,
    "carregando": False, "erro": None,
}
_ibge_cache: Optional[pd.DataFrame] = None

def _carregar():
    global _ibge_cache
    _cache["carregando"] = True
    _cache["erro"] = None
    try:
        raw = fetch_dados_reais(ano_credito=2022, ano_desmat_inicio=2021, ano_desmat_fim=2022, top_municipios=300)
        _cache["df"] = ICAEModel().fit_transform(raw)
        _cache["fonte"] = "real" if "delta_km2" in raw.columns and raw["delta_km2"].sum() > 0 else "demo"
        _cache["ultima_atualizacao"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _cache["erro"] = None
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Falha ao carregar dados reais:\n{tb}")
        _cache["erro"] = f"{type(e).__name__}: {e} | {tb.splitlines()[-2] if tb else ''}"
        if _cache["df"] is None:
            _cache["df"] = ICAEModel().fit_transform(generate_sample_data(200))
            _cache["fonte"] = "demo"
            _cache["ultima_atualizacao"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    finally:
        _cache["carregando"] = False


@app.on_event("startup")
async def startup():
    _cache["df"] = ICAEModel().fit_transform(generate_sample_data(200))
    _cache["fonte"] = "demo"
    _cache["ultima_atualizacao"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _carregar)
    loop.run_in_executor(None, _carregar_privados, 2022)


def get_df() -> pd.DataFrame:
    return _cache["df"] if _cache["df"] is not None else ICAEModel().fit_transform(generate_sample_data(200))


class WeightInput(BaseModel):
    alpha1_desmatamento: float = Field(0.25, ge=0)
    alpha2_multas:       float = Field(0.25, ge=0)
    alpha3_reincidencia: float = Field(0.25, ge=0)
    alpha4_embargo:      float = Field(0.25, ge=0)
    top:                 int   = Field(50,  ge=1, le=500)


# ── Endpoints ───────────────────────────────────────────────

@app.get("/")
def root():
    return {"status":"online","versao":"2.0.0","fonte":_cache["fonte"],"carregando":_cache["carregando"]}


@app.get("/status")
def status():
    df = get_df()
    return {
        "fonte": _cache["fonte"],
        "n_municipios": len(df),
        "ultima_atualizacao": _cache["ultima_atualizacao"],
        "carregando": _cache["carregando"],
        "erro": _cache["erro"],
        "biomas": df["bioma"].value_counts().to_dict() if "bioma" in df.columns else {},
        "regioes": df["regiao"].value_counts().to_dict() if "regiao" in df.columns else {},
    }


@app.post("/atualizar")
def atualizar(bt: BackgroundTasks):
    if _cache["carregando"]:
        return {"mensagem":"Já está carregando. Use /status para acompanhar."}
    bt.add_task(_carregar)
    return {"mensagem":"Recarga iniciada. Use /status para acompanhar."}


@app.get("/formula")
def formula():
    return {
        "normalização": "X_norm = (X - min(X)) / (max(X) - min(X))",
        "risk_vector":  "Risk_i = α1·ΔD_i + α2·M_i + α3·R_i + α4·Em_i",
        "icae":         "ICAE_i = (1 − Risk_i) · (1 − Cr_i)",
        "pesos_padrão": WeightConfig().as_dict(),
        "intervalo":    "[0, 1]",
        "interpretação": {"0":"Incoerência máxima","1":"Coerência máxima"},
        "fontes": {
            "crédito":     "SICOR/BCB — todos os municípios do Brasil",
            "desmatamento":"PRODES/INPE via TerraBrasilis — 6 biomas nacionais",
            "geocódigos":  "IBGE API de localidades",
        },
    }


@app.get("/ranking")
def ranking(
    top:      int            = Query(50, ge=1, le=500),
    uf:       Optional[str]  = Query(None),
    bioma:    Optional[str]  = Query(None),
    regiao:   Optional[str]  = Query(None),
    municipio:Optional[str]  = Query(None),
):
    df = get_df()
    if uf:
        df = df[df["uf"].str.upper() == uf.upper()]
    if bioma:
        df = df[df.get("bioma", pd.Series()).str.lower().str.contains(bioma.lower(), na=False)]
    if regiao:
        df = df[df.get("regiao", pd.Series()).str.lower().str.contains(regiao.lower(), na=False)]
    if municipio:
        df = df[df["municipio"].str.lower().str.contains(municipio.lower(), na=False)]
    if df.empty:
        raise HTTPException(404, "Nenhum resultado com esses filtros.")
    r = build_ranking(df, top_n=top)
    cols = [c for c in ["entity_id","nome","municipio","uf","bioma","regiao","icae","risk","credito_norm","rank"] if c in r.columns]
    return r[cols].to_dict("records")


@app.get("/municipios")
def municipios(
    uf:     Optional[str] = Query(None),
    bioma:  Optional[str] = Query(None),
    regiao: Optional[str] = Query(None),
):
    df = get_df()
    if uf:    df = df[df["uf"].str.upper() == uf.upper()]
    if bioma: df = df[df.get("bioma", pd.Series()).str.lower().str.contains(bioma.lower(), na=False)]
    if regiao:df = df[df.get("regiao", pd.Series()).str.lower().str.contains(regiao.lower(), na=False)]

    summary = build_municipio_summary(df)

    # Adiciona crédito e desmatamento brutos para o gráfico de bolhas e mapa
    if "credito" in df.columns:
        agg = df.groupby("municipio").agg(
            credito_total=("credito","sum"),
            desmat_antes=("desmatamento_antes","mean"),
            desmat_depois=("desmatamento_depois","mean"),
            delta_km2_total=("delta_km2","sum") if "delta_km2" in df.columns else ("desmatamento_depois","mean"),
            delta_pct_medio=("delta_pct","mean") if "delta_pct" in df.columns else ("desmatamento_depois","mean"),
            bioma=("bioma","first") if "bioma" in df.columns else ("municipio","first"),
            uf=("uf","first"),
            regiao=("regiao","first") if "regiao" in df.columns else ("uf","first"),
        ).reset_index()
        summary = summary.merge(agg, on="municipio", how="left")

    return summary.to_dict("records")


@app.get("/mapa")
def mapa(bioma: Optional[str] = Query(None)):
    """
    Retorna dados para o mapa choropleth do Brasil.
    Inclui: municipio, uf, bioma, delta_km2, delta_pct, icae, credito_total
    """
    df = get_df()
    if bioma:
        df = df[df.get("bioma", pd.Series()).str.lower().str.contains(bioma.lower(), na=False)]

    cols_raw = ["entity_id","municipio","uf","icae","risk"]
    for c in ["bioma","regiao","delta_km2","delta_pct","credito","desmatamento_antes","desmatamento_depois"]:
        if c in df.columns:
            cols_raw.append(c)

    result = df[cols_raw].copy()
    result["icae_pct"] = (result["icae"] * 100).round(1)

    # Classifica severidade do desmatamento
    if "delta_km2" in result.columns:
        q75 = result["delta_km2"].quantile(0.75)
        q90 = result["delta_km2"].quantile(0.90)
        def classify(v):
            if v >= q90: return "crítico"
            if v >= q75: return "alto"
            if v >  0:   return "moderado"
            return "estável"
        result["severidade"] = result["delta_km2"].apply(classify)
    else:
        result["severidade"] = "desconhecido"

    return result.to_dict("records")


@app.get("/biomas")
def biomas():
    """Lista os biomas presentes nos dados e estatísticas por bioma."""
    df = get_df()
    if "bioma" not in df.columns:
        return []
    return df.groupby("bioma").agg(
        n_municipios=("municipio","count"),
        icae_medio=("icae","mean"),
        delta_km2_total=("delta_km2","sum") if "delta_km2" in df.columns else ("icae","count"),
        credito_total=("credito","sum") if "credito" in df.columns else ("icae","count"),
    ).reset_index().round(3).to_dict("records")


@app.get("/regioes")
def regioes():
    """Estatísticas por região do Brasil."""
    df = get_df()
    if "regiao" not in df.columns:
        return []
    return df.groupby("regiao").agg(
        n_municipios=("municipio","count"),
        icae_medio=("icae","mean"),
        delta_km2_total=("delta_km2","sum") if "delta_km2" in df.columns else ("icae","count"),
        credito_total=("credito","sum") if "credito" in df.columns else ("icae","count"),
    ).reset_index().round(3).to_dict("records")


@app.get("/entidade/{entity_id}")
def get_entity(entity_id: str):
    df = get_df()
    row = df[df["entity_id"] == entity_id]
    if row.empty:
        raise HTTPException(404, "Não encontrado.")
    return {k:(float(v) if isinstance(v,(int,float)) else v) for k,v in row.iloc[0].items()}


@app.post("/simular")
def simular(body: WeightInput):
    try:
        w = WeightConfig(
            alpha1_desmatamento=body.alpha1_desmatamento,
            alpha2_multas=body.alpha2_multas,
            alpha3_reincidencia=body.alpha3_reincidencia,
            alpha4_embargo=body.alpha4_embargo,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    result = ICAEModel(w).fit_transform(get_df().copy())
    rank = build_ranking(result, top_n=body.top)
    cols = [c for c in ["entity_id","nome","municipio","uf","bioma","icae","risk","rank"] if c in rank.columns]
    return {
        "pesos":      w.as_dict(),
        "icae_medio": float(result["icae"].mean()),
        "icae_std":   float(result["icae"].std()),
        "ranking":    rank[cols].to_dict("records"),
        "fonte":      _cache["fonte"],
    }


# ── Cache de incentivos privados ─────────────────────────────────────────────
_priv_cache: dict = {
    "df": None, "ano": None, "carregando": False, "erro": None
}

def _carregar_privados(ano: int = 2022):
    _priv_cache["carregando"] = True
    _priv_cache["erro"] = None
    try:
        df = fetch_incentivos_privados(ano=ano)
        _priv_cache["df"]  = df
        _priv_cache["ano"] = ano
    except Exception as e:
        _priv_cache["erro"] = str(e)
        _priv_cache["df"]   = None
    finally:
        _priv_cache["carregando"] = False


@app.get("/incentivos-privados")
def incentivos_privados(
    ano:    int            = Query(2022, ge=2010, le=2024),
    uf:     Optional[str]  = Query(None),
    top:    int            = Query(50, ge=1, le=500),
    ordenar_por: str       = Query("incentivo_privado_total_reais",
                                   description="incentivo_privado_total_reais | bndes_valor_reais | comex_valor_usd"),
    bt: BackgroundTasks = None,
):
    """
    Desembolsos BNDES agronegócio + exportações Comex Stat por município.

    Fontes:
    - BNDES/desembolsos-mensais: CSV público (dadosabertos.bndes.gov.br)
    - Comex Stat/MDIC: API REST pública (api-comexstat.mdic.gov.br/cities)

    Nota: BNDES é *semipúblico* (banco estatal) — incluído como "incentivo privado"
    porque opera via mercado financeiro, diferente do crédito rural do Pronaf/SICOR.
    """
    if _priv_cache["df"] is None or _priv_cache["ano"] != ano:
        if not _priv_cache["carregando"]:
            if bt:
                bt.add_task(_carregar_privados, ano)
            else:
                _carregar_privados(ano)

    df = _priv_cache["df"]
    if df is None:
        # Ainda carregando — retorna dados demo para não travar o frontend
        from ingest.private_incentives import _gerar_demo
        df = _gerar_demo(ano)

    if uf:
        df = df[df["uf"].str.upper() == uf.upper()]

    if ordenar_por in df.columns:
        df = df.nlargest(top, ordenar_por)
    else:
        df = df.head(top)

    return df.fillna("").to_dict("records")


@app.post("/incentivos-privados/atualizar")
def atualizar_privados(ano: int = Query(2022), bt: BackgroundTasks = None):
    if _priv_cache["carregando"]:
        return {"mensagem": "Já carregando. Use /incentivos-privados para acompanhar."}
    if bt:
        bt.add_task(_carregar_privados, ano)
    else:
        _carregar_privados(ano)
    return {"mensagem": f"Recarga iniciada para ano={ano}. Dados ficam disponíveis em /incentivos-privados"}


@app.get("/incentivos-privados/produtos")
def produtos_agro():
    """Lista os produtos agropecuários monitorados via Comex Stat (SH4)."""
    return [{"sh4": k, "produto": v} for k, v in SH4_AGRO.items()]


@app.get("/incentivos-privados/ranking-cruzado")
def ranking_cruzado(
    top: int = Query(30, ge=1, le=200),
    uf:  Optional[str] = Query(None),
):
    """
    Cruza crédito público (SICOR) + BNDES + exportações com desmatamento.
    Retorna municípios ordenados pelo maior fluxo financeiro total combinado
    com maior desmatamento — os casos mais críticos de incoerência.
    """
    df_pub  = get_df()
    df_priv = _priv_cache["df"]

    if df_priv is None:
        raise HTTPException(503, "Incentivos privados ainda não carregados. Use /incentivos-privados/atualizar")

    # Merge
    if "_key" in df_pub.columns and "_key" in df_priv.columns:
        df = df_pub.merge(
            df_priv[["_key","bndes_valor_reais","comex_valor_usd","incentivo_privado_total_reais","produto_principal"]],
            on="_key", how="left"
        )
    else:
        df = df_pub.copy()
        for c in ["bndes_valor_reais","comex_valor_usd","incentivo_privado_total_reais","produto_principal"]:
            df[c] = 0

    for c in ["bndes_valor_reais","comex_valor_usd","incentivo_privado_total_reais"]:
        df[c] = pd.to_numeric(df.get(c, 0), errors="coerce").fillna(0)

    if uf:
        df = df[df["uf"].str.upper() == uf.upper()]

    # Score composto: fluxo financeiro total × risco ambiental
    df["fluxo_total"] = df["credito"].fillna(0) + df["incentivo_privado_total_reais"].fillna(0)
    df["incoerencia_score"] = df["fluxo_total"] * df["risk"].fillna(0)
    df["delta_km2"]         = pd.to_numeric(df.get("delta_km2", 0), errors="coerce").fillna(0)

    df = df.nlargest(top, "incoerencia_score")

    cols = [c for c in [
        "municipio","uf","bioma","icae","risk","delta_km2",
        "credito","bndes_valor_reais","comex_valor_usd",
        "incentivo_privado_total_reais","fluxo_total","incoerencia_score",
        "produto_principal",
    ] if c in df.columns]

    return df[cols].fillna(0).to_dict("records")
