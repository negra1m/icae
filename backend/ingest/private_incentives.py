"""
ICAE — Incentivos Privados por Município
Fontes validadas e acessíveis publicamente:

1. BNDES/desembolsos-mensais   → CSV direto (sem auth, ~70MB)
   URL: dadosabertos.bndes.gov.br/dataset/102e89ec.../resource/179950b8.../download/desembolsos-mensais.csv
   Colunas confirmadas: ano;mes;uf;municipio;setor_bndes;cnae;porte;grupo_produto;valor_desembolsado
   Encoding: Windows-1252, delimitador ;

2. Comex Stat/MDIC             → API REST JSON (sem auth)
   POST https://api-comexstat.mdic.gov.br/cities
   Filtra por SH4 agropecuário: soja (1201), boi (0201/0202), milho (1005),
   madeira (4403), algodão (5201), frango (0207), suíno (0203)
   Retorna: municipio (CO_MUN), uf, valor_fob_usd, kg_liquido

Os dois cruzam por código IBGE de município.
"""

import pandas as pd
import numpy as np
import httpx
import unicodedata
import logging
from typing import Optional
from io import StringIO

logger = logging.getLogger(__name__)

# ── URLs confirmadas ──────────────────────────────────────────────────────────
BNDES_CSV = (
    "https://dadosabertos.bndes.gov.br"
    "/dataset/102e89ec-836a-4ae0-acc7-74ac2a804c1c"
    "/resource/179950b8-b504-4cc7-b0db-9c9eed99e9ba"
    "/download/desembolsos-mensais.csv"
)
COMEX_API = "https://api-comexstat.mdic.gov.br"
TIMEOUT   = 60

# SH4 de produtos agropecuários / florestais relevantes para cruzamento com desmatamento
# Fonte: Nomenclatura do Sistema Harmonizado, capítulos 01-24 (agro) e 44 (madeira)
SH4_AGRO = {
    "1201": "Soja",
    "1005": "Milho",
    "0201": "Carne bovina fresca",
    "0202": "Carne bovina congelada",
    "0207": "Carne de frango",
    "0203": "Carne suína",
    "5201": "Algodão",
    "1801": "Cacau",
    "0901": "Café",
    "4403": "Madeira bruta",
    "4407": "Madeira serrada",
    "1511": "Óleo de palma",
    "2301": "Farelo de soja",
    "1507": "Óleo de soja",
}

# Setores BNDES relevantes para agronegócio e florestal
SETORES_BNDES_AGRO = {
    "agropecuaria",
    "agricultura",
    "pecuaria",
    "florestal",
    "agroindústria",
    "agronegocio",
    "agro",
}


def _norm(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper().strip()


# ── 1. BNDES — desembolsos mensais por município ──────────────────────────────

def fetch_bndes_municipio(
    ano: int = 2022,
    apenas_agro: bool = True,
) -> pd.DataFrame:
    """
    Baixa CSV de desembolsos mensais do BNDES e filtra por município e ano.

    O CSV tem ~70 MB. Fazemos streaming com pandas read_csv em chunks
    para não explodir a memória, filtrando só o ano desejado.

    Retorna colunas:
        municipio, uf, codigo_ibge (se disponível), setor_bndes, cnae,
        porte, bndes_valor_reais, bndes_n_operacoes, ano
    """
    logger.info(f"[BNDES] Baixando desembolsos mensais (ano={ano}, apenas_agro={apenas_agro})...")

    try:
        resp = httpx.get(BNDES_CSV, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"[BNDES] Falha ao baixar CSV: {e}")
        return pd.DataFrame()

    # Detecta encoding automaticamente (Windows-1252 ou UTF-8 conforme botão Download)
    raw = resp.content
    for enc in ("utf-8-sig", "windows-1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        logger.warning("[BNDES] Encoding não detectado")
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            StringIO(text),
            sep=";",
            decimal=",",
            dtype=str,
            low_memory=True,
        )
    except Exception as e:
        logger.warning(f"[BNDES] Erro ao parsear CSV: {e}")
        return pd.DataFrame()

    # Normaliza nomes de colunas
    df.columns = [_norm(c).lower().replace(" ", "_") for c in df.columns]
    logger.info(f"[BNDES] Colunas: {list(df.columns)}")

    # Mapeia colunas (o BNDES pode variar o nome)
    col_map = _detect_bndes_columns(df)
    if not col_map:
        logger.warning("[BNDES] Estrutura de colunas não reconhecida")
        return pd.DataFrame()

    df = df.rename(columns=col_map)

    # Filtra ano
    if "ano" in df.columns:
        df = df[df["ano"].astype(str) == str(ano)]

    if df.empty:
        logger.warning(f"[BNDES] Nenhum registro para ano={ano}")
        return pd.DataFrame()

    # Filtra setor agro se solicitado
    if apenas_agro and "setor_bndes" in df.columns:
        mask = df["setor_bndes"].fillna("").apply(
            lambda s: any(t in _norm(s).lower() for t in SETORES_BNDES_AGRO)
        )
        df = df[mask]
        logger.info(f"[BNDES] Após filtro agro: {len(df)} registros")

    # Converte valor
    df["valor"] = pd.to_numeric(
        df.get("valor", pd.Series(dtype=str)).str.replace(",", "."),
        errors="coerce"
    ).fillna(0)

    # Agrega por município
    grp_cols = [c for c in ["municipio", "uf", "codigo_ibge", "setor_bndes"] if c in df.columns]
    if "municipio" not in grp_cols:
        return pd.DataFrame()

    result = df.groupby(grp_cols, as_index=False).agg(
        bndes_valor_reais=("valor", "sum"),
        bndes_n_operacoes=("valor", "count"),
    )
    result["ano"] = ano
    result["_key"] = result["municipio"].apply(_norm)
    result["fonte"] = "BNDES"
    logger.info(f"[BNDES] {len(result)} municípios com desembolsos BNDES agro em {ano}")
    return result


def _detect_bndes_columns(df: pd.DataFrame) -> dict:
    """Detecta o mapeamento de colunas independentemente do nome exato."""
    cols = list(df.columns)
    result = {}
    for c in cols:
        cl = c.lower()
        if "municipio" in cl or "município" in cl:
            result[c] = "municipio"
        elif cl in ("uf", "sg_uf", "sigla_uf", "estado"):
            result[c] = "uf"
        elif "ibge" in cl or "cod_mun" in cl or "co_mun" in cl:
            result[c] = "codigo_ibge"
        elif "setor" in cl and "bndes" in cl:
            result[c] = "setor_bndes"
        elif "cnae" in cl:
            result[c] = "cnae"
        elif "porte" in cl:
            result[c] = "porte"
        elif "valor" in cl or "desembolso" in cl:
            result[c] = "valor"
        elif c == "ano" or cl == "ano":
            result[c] = "ano"
        elif cl in ("mes", "mês"):
            result[c] = "mes"
    return result


# ── 2. Comex Stat — exportações agro por município ───────────────────────────

def fetch_comex_municipio(
    ano: int = 2022,
    sh4_codes: Optional[list] = None,
) -> pd.DataFrame:
    """
    Puxa exportações por município via API do Comex Stat/MDIC.
    Filtra pelos SH4 de produtos agropecuários.

    API: POST https://api-comexstat.mdic.gov.br/cities
    Body: {
      "flow": "export",
      "monthStart": "01",
      "monthEnd": "12",
      "yearStart": "2022",
      "yearEnd": "2022",
      "details": ["city", "state"],
      "filters": [{"filter": "sh4", "values": ["1201", "1005", ...]}]
    }

    Retorna: municipio, uf, codigo_ibge, sh4, produto, comex_valor_usd, comex_kg
    """
    if sh4_codes is None:
        sh4_codes = list(SH4_AGRO.keys())

    logger.info(f"[COMEX] Buscando exportações agro por município — ano={ano}")

    payload = {
        "flow": "export",
        "monthStart": "01",
        "monthEnd": "12",
        "yearStart": str(ano),
        "yearEnd": str(ano),
        "details": ["city", "state"],
        "filters": [{"filter": "sh4", "values": sh4_codes}],
        "metrics": ["metricFOB", "metricKG"],
    }

    try:
        resp = httpx.post(
            f"{COMEX_API}/cities",
            json=payload,
            timeout=TIMEOUT,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[COMEX] Falha na API: {e}")
        return pd.DataFrame()

    records = data.get("data", data) if isinstance(data, dict) else data
    if not records:
        logger.warning("[COMEX] Resposta vazia")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    logger.info(f"[COMEX] Colunas recebidas: {list(df.columns)}")

    # Mapeia colunas da API Comex Stat
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "city" in cl or "municipio" in cl or cl == "no_mun":
            col_map[c] = "municipio"
        elif "state" in cl or cl in ("sg_uf_mun", "uf"):
            col_map[c] = "uf"
        elif cl in ("co_mun", "co_municipio", "id_city"):
            col_map[c] = "codigo_ibge"
        elif "fob" in cl or "valor" in cl:
            col_map[c] = "comex_valor_usd"
        elif "kg" in cl or "peso" in cl:
            col_map[c] = "comex_kg"
        elif cl in ("sh4", "co_sh4", "no_sh4"):
            col_map[c] = "sh4"

    df = df.rename(columns=col_map)

    # Converte métricas
    for mc in ["comex_valor_usd", "comex_kg"]:
        if mc in df.columns:
            df[mc] = pd.to_numeric(df[mc], errors="coerce").fillna(0)

    # Agrega por município (consolida todos os produtos)
    grp = [c for c in ["municipio", "uf", "codigo_ibge"] if c in df.columns]
    if not grp:
        return pd.DataFrame()

    result = df.groupby(grp, as_index=False).agg(
        comex_valor_usd=("comex_valor_usd", "sum") if "comex_valor_usd" in df.columns else ("municipio", "count"),
        comex_kg_total=("comex_kg", "sum") if "comex_kg" in df.columns else ("municipio", "count"),
        comex_n_produtos=("sh4", "nunique") if "sh4" in df.columns else ("municipio", "count"),
    )

    # Produto principal (maior valor)
    if "sh4" in df.columns and "comex_valor_usd" in df.columns:
        top = df.sort_values("comex_valor_usd", ascending=False).drop_duplicates(grp)
        top["produto_principal"] = top["sh4"].map(SH4_AGRO).fillna(top.get("sh4", ""))
        result = result.merge(top[grp + ["produto_principal"]], on=grp, how="left")

    result["ano"] = ano
    result["_key"] = result["municipio"].apply(_norm)
    result["fonte"] = "ComexStat"
    logger.info(f"[COMEX] {len(result)} municípios com exportações agro em {ano}")
    return result


# ── 3. Pipeline consolidado ───────────────────────────────────────────────────

def fetch_incentivos_privados(
    ano: int = 2022,
    apenas_agro: bool = True,
) -> pd.DataFrame:
    """
    Consolida BNDES + Comex Stat num único DataFrame por município.

    Colunas de saída:
        municipio, uf, _key, codigo_ibge
        bndes_valor_reais, bndes_n_operacoes  (BNDES agro)
        comex_valor_usd, comex_kg_total        (exportações agro)
        comex_n_produtos, produto_principal
        incentivo_privado_total_reais          (BNDES + comex em BRL estimado)
        ano
    """
    logger.info(f"[INCENTIVOS_PRIVADOS] Iniciando — ano={ano}")

    df_bndes = fetch_bndes_municipio(ano=ano, apenas_agro=apenas_agro)
    df_comex = fetch_comex_municipio(ano=ano)

    # Taxa de câmbio estimada: se não tiver API, usa referência histórica
    # (BRL/USD médio 2022 ≈ 5.16)
    USD_BRL = 5.16

    if df_bndes.empty and df_comex.empty:
        logger.warning("[INCENTIVOS_PRIVADOS] Ambas as fontes falharam → dados demo")
        return _gerar_demo(ano)

    # Merge BNDES + Comex
    key_cols = ["_key", "municipio", "uf"]

    if not df_bndes.empty and not df_comex.empty:
        # Tenta merge por codigo_ibge se disponível
        if "codigo_ibge" in df_bndes.columns and "codigo_ibge" in df_comex.columns:
            df = df_bndes.merge(df_comex, on="codigo_ibge", how="outer", suffixes=("_b", "_c"))
        else:
            df = df_bndes.merge(df_comex, on="_key", how="outer", suffixes=("_b", "_c"))

        # Consolida colunas duplicadas após outer merge
        for col in ["municipio", "uf", "_key"]:
            cb, cc = f"{col}_b", f"{col}_c"
            if cb in df.columns and cc in df.columns:
                df[col] = df[cb].fillna(df[cc])
                df.drop(columns=[cb, cc], inplace=True, errors="ignore")

    elif not df_bndes.empty:
        df = df_bndes
        for c in ["comex_valor_usd", "comex_kg_total", "comex_n_produtos", "produto_principal"]:
            df[c] = 0
    else:
        df = df_comex
        for c in ["bndes_valor_reais", "bndes_n_operacoes"]:
            df[c] = 0

    # Garante colunas numéricas
    for c in ["bndes_valor_reais", "comex_valor_usd"]:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Total em BRL estimado
    df["incentivo_privado_total_reais"] = (
        df["bndes_valor_reais"] + df["comex_valor_usd"] * USD_BRL
    ).round(2)

    df["ano"] = ano

    # Garante _key
    if "_key" not in df.columns and "municipio" in df.columns:
        df["_key"] = df["municipio"].apply(_norm)

    keep = [c for c in [
        "municipio", "uf", "codigo_ibge", "_key",
        "bndes_valor_reais", "bndes_n_operacoes",
        "comex_valor_usd", "comex_kg_total", "comex_n_produtos", "produto_principal",
        "incentivo_privado_total_reais", "ano",
    ] if c in df.columns]

    result = df[keep].drop_duplicates(subset=["_key"]).reset_index(drop=True)
    logger.info(f"[INCENTIVOS_PRIVADOS] {len(result)} municípios — total BRL: R${result['incentivo_privado_total_reais'].sum()/1e9:.1f}B")
    return result


def _gerar_demo(ano: int = 2022) -> pd.DataFrame:
    """Dados demonstrativos para quando as APIs falham."""
    rng = np.random.default_rng(42)
    muns = [
        ("Sorriso","MT"),("Sinop","MT"),("Nova Mutum","MT"),("Sapezal","MT"),
        ("Rondonópolis","MT"),("Primavera do Leste","MT"),("Campo Novo do Parecis","MT"),
        ("Barreiras","BA"),("Luís Eduardo Magalhães","BA"),("São Desidério","BA"),
        ("Rio Verde","GO"),("Jataí","GO"),("Mineiros","GO"),("Chapadão do Sul","MS"),
        ("Sete Lagoas","MG"),("Uberaba","MG"),("Uberlândia","MG"),
        ("Cascavel","PR"),("Maringá","PR"),("Ponta Grossa","PR"),
        ("Altamira","PA"),("Novo Progresso","PA"),("São Félix do Xingu","PA"),
        ("Marabá","PA"),("Itaituba","PA"),
    ]
    n = len(muns)
    nomes, ufs = zip(*muns)
    PROD = list(SH4_AGRO.values())
    return pd.DataFrame({
        "municipio":                  list(nomes),
        "uf":                         list(ufs),
        "_key":                       [_norm(m) for m in nomes],
        "codigo_ibge":                rng.integers(1100000, 5300000, n),
        "bndes_valor_reais":          rng.uniform(5e6, 500e6, n).round(2),
        "bndes_n_operacoes":          rng.integers(2, 80, n).astype(int),
        "comex_valor_usd":            rng.uniform(1e6, 200e6, n).round(2),
        "comex_kg_total":             rng.uniform(1e6, 500e6, n).round(0),
        "comex_n_produtos":           rng.integers(1, 8, n).astype(int),
        "produto_principal":          [PROD[i % len(PROD)] for i in range(n)],
        "incentivo_privado_total_reais": rng.uniform(10e6, 1e9, n).round(2),
        "ano":                        ano,
    })
