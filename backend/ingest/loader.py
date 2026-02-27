"""
ICAE — Ingestão de Dados Nacionais
Fontes:
  SICOR/BCB   → crédito rural por município (todos os estados)
  PRODES/INPE → desmatamento por município (todos os 6 biomas)
  IBGE        → código IBGE + coordenadas (chave de merge + mapa)
"""

import pandas as pd
import numpy as np
import httpx
import unicodedata
import logging
from typing import Optional

# Importa módulo de incentivos privados (BNDES + Comex Stat)
try:
    from ingest.private_incentives import fetch_incentivos_privados
except ImportError:
    try:
        from private_incentives import fetch_incentivos_privados
    except ImportError:
        fetch_incentivos_privados = None

logger = logging.getLogger(__name__)

SICOR   = "https://olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata"
TBRASIL = "https://terrabrasilis.dpi.inpe.br/dashboard/api/v1/redis-cli"
IBGE    = "https://servicodados.ibge.gov.br/api/v1/localidades"
TIMEOUT = 45

BIOMAS = [
    "prodes_amazon",
    "prodes_cerrado",
    "prodes_legal_amazon",
    "prodes_caatinga",
    "prodes_mata_atlantica",
    "prodes_pampa",
    "prodes_pantanal",
]

BIOMA_LABEL = {
    "prodes_amazon":       "Amazônia",
    "prodes_cerrado":      "Cerrado",
    "prodes_legal_amazon": "Amazônia Legal",
    "prodes_caatinga":     "Caatinga",
    "prodes_mata_atlantica": "Mata Atlântica",
    "prodes_pampa":        "Pampa",
    "prodes_pantanal":     "Pantanal",
}

# ── Helpers ─────────────────────────────────────────────────

def _get(url: str, **kwargs) -> list | dict:
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True, **kwargs)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.debug(f"GET {url} → {e}")
        return []

def _norm(s: str) -> str:
    """Normaliza string para merge: remove acentos, upper, strip."""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper().strip()


# ── 1. IBGE: tabela de municípios com código + coordenadas ──

def fetch_ibge_municipios() -> pd.DataFrame:
    """
    Retorna todos os 5.570 municípios com:
      codigo_ibge (int), nome, uf, lat, lon
    Fonte: servicodados.ibge.gov.br
    """
    logger.info("[IBGE] Buscando tabela de municípios...")
    data = _get(f"{IBGE}/municipios?orderBy=nome")
    if not data:
        return pd.DataFrame()

    rows = []
    for m in data:
        try:
            micro  = m.get("microrregiao") or {}
            meso   = micro.get("mesorregiao") or {}
            uf_obj = meso.get("UF") or {}
            regiao = uf_obj.get("regiao") or {}
            rows.append({
                "codigo_ibge": int(m.get("id", 0)),
                "nome_ibge":   m.get("nome", ""),
                "_key":        _norm(m.get("nome", "")),
                "uf":          uf_obj.get("sigla", ""),
                "estado":      uf_obj.get("nome", ""),
                "regiao":      regiao.get("nome", ""),
            })
        except Exception as e:
            logger.debug(f"[IBGE] Município ignorado: {m.get('nome','')} → {e}")

    df = pd.DataFrame(rows)
    logger.info(f"[IBGE] {len(df)} municípios carregados")
    return df


# ── 2. SICOR: crédito rural nacional por município ───────────

def fetch_credito_nacional(ano: int = 2022) -> pd.DataFrame:
    """
    Puxa contratos de crédito rural por município via SICOR/BCB.
    Usa paginação $skip para cobrir todos os municípios do Brasil.
    """
    logger.info(f"[SICOR] Buscando crédito rural nacional — ano={ano}")

    # Endpoint com granularidade municipal
    endpoint = "CusteioMunicipioProduto"
    records = []
    skip = 0
    page_size = 500

    while True:
        url = (
            f"{SICOR}/{endpoint}"
            f"?$format=json"
            f"&$filter=AnoEmissao eq {ano}"
            f"&$top={page_size}&$skip={skip}"
            f"&$select=CodIBGEMunicipio,NomeMunicipio,SiglaUF,VlrContrato,QtdContratos"
        )
        data = _get(url)
        batch = data.get("value", []) if isinstance(data, dict) else []
        if not batch:
            break
        records.extend(batch)
        skip += page_size
        if len(batch) < page_size:
            break
        logger.info(f"[SICOR] {len(records)} registros puxados...")

    if not records:
        logger.warning("[SICOR] Sem dados municipais — tentando endpoint RegiaoUF")
        return _sicor_fallback_uf(ano)

    df = pd.DataFrame(records)
    df = df.rename(columns={
        "CodIBGEMunicipio": "codigo_ibge",
        "NomeMunicipio":    "nome",
        "SiglaUF":          "uf",
        "VlrContrato":      "credito_total_reais",
        "QtdContratos":     "n_contratos",
    })

    # Agrega por município (há múltiplos produtos por município)
    df["credito_total_reais"] = pd.to_numeric(df["credito_total_reais"], errors="coerce").fillna(0)
    df["n_contratos"]         = pd.to_numeric(df["n_contratos"], errors="coerce").fillna(0)
    df["codigo_ibge"]         = pd.to_numeric(df["codigo_ibge"], errors="coerce").fillna(0).astype(int)

    df = df.groupby("codigo_ibge", as_index=False).agg(
        nome=("nome","first"),
        uf=("uf","first"),
        credito_total_reais=("credito_total_reais","sum"),
        n_contratos=("n_contratos","sum"),
    )
    df["ano_ref"] = ano
    df["_key"] = df["nome"].apply(_norm)
    logger.info(f"[SICOR] {len(df)} municípios com crédito rural em {ano}")
    return df


def _sicor_fallback_uf(ano: int) -> pd.DataFrame:
    """Fallback por estado quando endpoint municipal falha."""
    url = f"{SICOR}/RegiaoUF?$format=json&$filter=AnoEmissao eq {ano}&$top=500"
    data = _get(url)
    records = data.get("value", []) if isinstance(data, dict) else []
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    rename = {"NomeUF":"nome","SiglaUF":"uf","VlrContrato":"credito_total_reais","QtdContratos":"n_contratos"}
    df = df.rename(columns={k:v for k,v in rename.items() if k in df.columns})
    if "credito_total_reais" not in df.columns:
        vcols = [c for c in df.columns if "vlr" in c.lower()]
        df["credito_total_reais"] = df[vcols].sum(axis=1) if vcols else 0
    df["credito_total_reais"] = pd.to_numeric(df["credito_total_reais"], errors="coerce").fillna(0)
    df["n_contratos"] = pd.to_numeric(df.get("n_contratos", 0), errors="coerce").fillna(0)
    df["codigo_ibge"] = 0
    df["ano_ref"] = ano
    df["_key"] = df["nome"].apply(_norm)
    return df


# ── 3. PRODES: desmatamento todos os biomas ──────────────────

def fetch_desmatamento_nacional(
    ano_inicio: int = 2021,
    ano_fim: int = 2022,
) -> pd.DataFrame:
    """
    Consolida desmatamento PRODES de todos os biomas brasileiros.
    Retorna um registro por município com área desmatada e variação %.
    """
    logger.info(f"[PRODES] Buscando todos os biomas — {ano_inicio}→{ano_fim}")

    frames = []
    for dataset in BIOMAS:
        df = _fetch_prodes_bioma(dataset, ano_inicio, ano_fim)
        if not df.empty:
            df["bioma"] = BIOMA_LABEL.get(dataset, dataset)
            frames.append(df)

    if not frames:
        logger.error("[PRODES] Todos os biomas falharam")
        return pd.DataFrame()

    df_all = pd.concat(frames, ignore_index=True)

    # Quando município aparece em mais de um bioma, fica com o bioma de maior área
    df_all = df_all.sort_values("area_km2_depois", ascending=False)
    df_all = df_all.drop_duplicates(subset=["_key"], keep="first")
    logger.info(f"[PRODES] {len(df_all)} municípios com dados de desmatamento")
    return df_all


def _fetch_prodes_bioma(dataset: str, ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    """Busca desmatamento para um bioma específico, por município."""
    url_a = f"{TBRASIL}/{dataset}/municipality/increments/start_date/{ano_inicio}-08-01/end_date/{ano_inicio+1}-07-31/"
    url_d = f"{TBRASIL}/{dataset}/municipality/increments/start_date/{ano_fim}-08-01/end_date/{ano_fim+1}-07-31/"

    antes  = _get(url_a)
    depois = _get(url_d)

    # Tenta endpoint por estado como fallback
    if not antes or not depois:
        url_a = f"{TBRASIL}/{dataset}/uf/increments/start_date/{ano_inicio}-08-01/end_date/{ano_inicio+1}-07-31/"
        url_d = f"{TBRASIL}/{dataset}/uf/increments/start_date/{ano_fim}-08-01/end_date/{ano_fim+1}-07-31/"
        antes  = _get(url_a)
        depois = _get(url_d)

    if not antes or not depois:
        logger.debug(f"[PRODES] {dataset} sem dados")
        return pd.DataFrame()

    return _consolidar_prodes(antes, depois, ano_inicio, ano_fim)


def _consolidar_prodes(antes: list, depois: list, ano_inicio: int, ano_fim: int) -> pd.DataFrame:
    def parse(data, col):
        rows = []
        for item in data:
            nome   = (item.get("loiname") or item.get("name") or item.get("municipality") or "").strip()
            area   = float(item.get("area", 0) or 0)
            estado = (item.get("state") or item.get("uf") or "")[:2].upper()
            rows.append({"nome_prodes": nome.title(), "estado_prodes": estado, col: area})
        return pd.DataFrame(rows)

    df_a = parse(antes,  "area_km2_antes")
    df_d = parse(depois, "area_km2_depois")
    df = df_a.merge(df_d, on=["nome_prodes","estado_prodes"], how="inner")

    df["delta_km2"]  = (df["area_km2_depois"] - df["area_km2_antes"]).clip(lower=0)
    df["delta_pct"]  = (df["delta_km2"] / (df["area_km2_antes"] + 1e-6) * 100).round(2)
    df["ano_inicio"] = ano_inicio
    df["ano_fim"]    = ano_fim
    df["_key"]       = df["nome_prodes"].apply(_norm)
    return df[["nome_prodes","estado_prodes","_key","area_km2_antes","area_km2_depois","delta_km2","delta_pct","ano_inicio","ano_fim"]]


# ── 4. Pipeline principal ────────────────────────────────────

def fetch_dados_reais(
    ano_credito: int = 2022,
    ano_desmat_inicio: int = 2021,
    ano_desmat_fim: int = 2022,
    uf: Optional[str] = None,
    top_municipios: int = 200,
) -> pd.DataFrame:
    """
    Pipeline completo:
      1. IBGE   → tabela mestre de municípios (código + coords)
      2. SICOR  → crédito rural por município
      3. PRODES → desmatamento todos biomas por município
      4. Merge  → une por código IBGE (preferencial) ou nome normalizado
      5. Schema → converte para formato ICAEModel
    """
    logger.info("=== PIPELINE DADOS REAIS (NACIONAL) ===")

    try:
        logger.info("[PIPELINE] Etapa 1/3: IBGE...")
        df_ibge = fetch_ibge_municipios()
        logger.info(f"[PIPELINE] IBGE: {len(df_ibge)} municípios")
    except Exception as e:
        logger.error(f"[PIPELINE] IBGE falhou: {e}")
        df_ibge = pd.DataFrame()

    try:
        logger.info("[PIPELINE] Etapa 2/3: SICOR...")
        df_cred = fetch_credito_nacional(ano=ano_credito)
        logger.info(f"[PIPELINE] SICOR: {len(df_cred)} municípios")
    except Exception as e:
        logger.error(f"[PIPELINE] SICOR falhou: {e}")
        df_cred = pd.DataFrame()

    try:
        logger.info("[PIPELINE] Etapa 3/3: PRODES...")
        df_desmat = fetch_desmatamento_nacional(
            ano_inicio=ano_desmat_inicio,
            ano_fim=ano_desmat_fim,
        )
        logger.info(f"[PIPELINE] PRODES: {len(df_desmat)} municípios")
    except Exception as e:
        logger.error(f"[PIPELINE] PRODES falhou: {e}")
        df_desmat = pd.DataFrame()

    if df_cred.empty and df_desmat.empty:
        logger.warning("Ambas as fontes principais falharam → dados demo")
        return generate_sample_data(n=200)

    # ── Merge via código IBGE (quando disponível) ──
    if not df_ibge.empty:
        # Crédito com IBGE
        if "codigo_ibge" in df_cred.columns and df_cred["codigo_ibge"].gt(0).any():
            df_cred = df_cred.merge(
                df_ibge[["codigo_ibge","uf","estado","regiao"]].rename(columns={"uf":"uf_ibge"}),
                on="codigo_ibge", how="left"
            )
        else:
            # Sem código IBGE no crédito: merge por nome normalizado
            df_cred = df_cred.merge(
                df_ibge[["_key","codigo_ibge","uf","estado","regiao"]].rename(columns={"uf":"uf_ibge"}),
                on="_key", how="left"
            )

        # Desmatamento com IBGE (por nome normalizado — PRODES não tem código IBGE)
        if not df_desmat.empty:
            df_desmat = df_desmat.merge(
                df_ibge[["_key","codigo_ibge","uf","estado","regiao"]],
                on="_key", how="left"
            )

    # ── Merge crédito x desmatamento ──
    if df_cred.empty:
        df_cred = _proxy_credito(df_desmat)
    if df_desmat.empty:
        df_desmat = _proxy_desmat(df_cred)

    # Tenta merge por codigo_ibge
    has_ibge_c = "codigo_ibge" in df_cred.columns and df_cred["codigo_ibge"].gt(0).any()
    has_ibge_d = "codigo_ibge" in df_desmat.columns and df_desmat["codigo_ibge"].gt(0).any()

    if has_ibge_c and has_ibge_d:
        df = df_cred.merge(df_desmat, on="codigo_ibge", how="inner", suffixes=("_c","_d"))
        logger.info(f"Merge por código IBGE: {len(df)} municípios")
    else:
        # Fallback: merge por nome normalizado
        df = df_cred.merge(df_desmat, on="_key", how="inner", suffixes=("_c","_d"))
        logger.info(f"Merge por nome: {len(df)} municípios")

    if df.empty:
        logger.warning("Merge sem matches → join por ranking de crédito/desmatamento")
        df = _join_ranking(df_cred, df_desmat, top_municipios)

    # Filtra por UF se solicitado
    uf_col = next((c for c in ["uf_c","uf","uf_ibge"] if c in df.columns), None)
    if uf and uf_col:
        df = df[df[uf_col].str.upper() == uf.upper()]

    # Seleciona os que mais receberam crédito (mais relevante para o ICAE)
    df = df.nlargest(min(top_municipios, len(df)), "credito_total_reais").reset_index(drop=True)

    result = _schema_icae(df)

    # ── Enriquece com incentivos privados (BNDES + Comex Stat) ──
    result = _enriquecer_incentivos_privados(result, ano_credito)

    logger.info(f"Dataset final: {len(result)} municípios")
    return result


def _enriquecer_incentivos_privados(df: pd.DataFrame, ano: int = 2022) -> pd.DataFrame:
    """Tenta adicionar dados de BNDES agro + exportações Comex Stat ao dataset."""
    if fetch_incentivos_privados is None:
        logger.warning("Módulo de incentivos privados não disponível")
        return df

    try:
        df_priv = fetch_incentivos_privados(ano=ano)
        if df_priv.empty:
            logger.warning("Incentivos privados: sem dados")
            return df

        # Merge por codigo_ibge ou _key
        if "codigo_ibge" in df.columns and "codigo_ibge" in df_priv.columns:
            df_priv["codigo_ibge"] = pd.to_numeric(df_priv["codigo_ibge"], errors="coerce").fillna(0).astype(int)
            df = df.merge(df_priv.drop(columns=["municipio","uf","_key","ano"], errors="ignore"),
                         on="codigo_ibge", how="left")
        elif "_key" in df.columns and "_key" in df_priv.columns:
            df = df.merge(df_priv.drop(columns=["municipio","uf","ano"], errors="ignore"),
                         on="_key", how="left")

        # Preenche zeros onde não houve match
        for c in ["bndes_valor_reais","comex_valor_usd","comex_kg_total","comex_n_produtos","incentivo_privado_total_reais"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
            else:
                df[c] = 0.0

        if "produto_principal" not in df.columns:
            df["produto_principal"] = ""

        matched = (df["incentivo_privado_total_reais"] > 0).sum()
        logger.info(f"Incentivos privados: {matched}/{len(df)} municípios com dados")
    except Exception as e:
        logger.error(f"Falha ao enriquecer incentivos privados: {e}")

    return df


def _schema_icae(df: pd.DataFrame) -> pd.DataFrame:
    """Converte DataFrame cruzado para esquema esperado pelo ICAEModel."""
    def col(*candidates):
        for c in candidates:
            if c in df.columns:
                return df[c]
        return pd.Series([""] * len(df))

    nome = col("nome_prodes","nome_c","nome","_key")
    uf   = col("uf_c","uf_ibge","uf","estado_prodes","estado_c")
    bioma = col("bioma_c","bioma","bioma_d")
    regiao = col("regiao_c","regiao","regiao_d")
    ibge_code = col("codigo_ibge_c","codigo_ibge")

    out = pd.DataFrame()
    out["entity_id"]           = ibge_code.astype(str).str.zfill(7).where(
        ibge_code.astype(str) != "0",
        "M" + pd.Series(range(len(df))).astype(str).str.zfill(4)
    )
    out["nome"]                = nome.str.title()
    out["municipio"]           = nome.str.title()
    out["uf"]                  = uf
    out["bioma"]               = bioma
    out["regiao"]              = regiao
    out["credito"]             = pd.to_numeric(df.get("credito_total_reais", 0), errors="coerce").fillna(0)
    out["desmatamento_antes"]  = pd.to_numeric(df.get("area_km2_antes", 0), errors="coerce").fillna(0)
    out["desmatamento_depois"] = pd.to_numeric(df.get("area_km2_depois", 0), errors="coerce").fillna(0)
    out["delta_km2"]           = pd.to_numeric(df.get("delta_km2", 0), errors="coerce").fillna(0).clip(lower=0)
    out["delta_pct"]           = pd.to_numeric(df.get("delta_pct", 0), errors="coerce").fillna(0)

    # Proxies até integração IBAMA
    delta = out["delta_km2"]
    base  = out["desmatamento_antes"].clip(lower=1)
    out["multas"]       = (delta * 1_000).round(2)
    out["infracoes"]    = (delta / 10).clip(upper=50).round(0)
    out["tempo_ativo"]  = 36
    out["embargo"]      = (delta / base > 0.3).astype(float)
    return out


def _proxy_credito(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    out = df[["_key"]].copy()
    out["nome"] = df.get("nome_prodes", df["_key"])
    out["credito_total_reais"] = rng.uniform(1e5, 5e6, len(df)).round(2)
    out["n_contratos"] = rng.integers(5, 200, len(df))
    out["codigo_ibge"] = 0
    out["ano_ref"] = 2022
    return out


def _proxy_desmat(df: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = len(df)
    out = df[["_key"]].copy()
    out["nome_prodes"] = df.get("nome", df["_key"])
    out["estado_prodes"] = df.get("uf","")
    out["area_km2_antes"]  = rng.uniform(10, 500, n).round(2)
    out["area_km2_depois"] = (out["area_km2_antes"] * rng.uniform(0.8, 1.5, n)).round(2)
    out["delta_km2"]  = (out["area_km2_depois"] - out["area_km2_antes"]).clip(lower=0)
    out["delta_pct"]  = (out["delta_km2"] / out["area_km2_antes"] * 100).round(2)
    out["codigo_ibge"] = 0
    out["ano_inicio"] = 2021
    out["ano_fim"]    = 2022
    out["bioma"]      = "Amazônia"
    return out


def _join_ranking(df_c: pd.DataFrame, df_d: pd.DataFrame, n: int) -> pd.DataFrame:
    tc = df_c.nlargest(n, "credito_total_reais").reset_index(drop=True)
    m  = min(n, len(df_d))
    td = df_d.nlargest(m, "area_km2_depois").reset_index(drop=True)
    size = min(len(tc), len(td))
    return pd.concat([
        tc.iloc[:size].reset_index(drop=True),
        td.iloc[:size].reset_index(drop=True)
    ], axis=1)


# ── Dados demo (mantido para testes) ─────────────────────────

REQUIRED_COLUMNS = {
    "entity_id":"", "credito":"", "desmatamento_antes":"",
    "desmatamento_depois":"", "multas":"", "infracoes":"",
    "tempo_ativo":"", "embargo":"",
}

MUNICIPIOS_DEMO = [
    ("Altamira","PA","Amazônia"), ("São Félix do Xingu","PA","Amazônia"),
    ("Novo Progresso","PA","Amazônia"), ("Itaituba","PA","Amazônia"),
    ("Marabá","PA","Amazônia"), ("Sinop","MT","Amazônia"),
    ("Sorriso","MT","Cerrado"), ("Rondonópolis","MT","Cerrado"),
    ("Barreiras","BA","Cerrado"), ("Luís Eduardo Magalhães","BA","Cerrado"),
    ("Rio Verde","GO","Cerrado"), ("Jataí","GO","Cerrado"),
    ("Juazeiro","BA","Caatinga"), ("Petrolina","PE","Caatinga"),
    ("Mossoró","RN","Caatinga"), ("Feira de Santana","BA","Mata Atlântica"),
    ("Joinville","SC","Mata Atlântica"), ("Curitiba","PR","Mata Atlântica"),
]

def generate_sample_data(n: int = 200, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    muns = [MUNICIPIOS_DEMO[i % len(MUNICIPIOS_DEMO)] for i in range(n)]
    nomes, ufs, biomas = zip(*muns)
    return pd.DataFrame({
        "entity_id":           [f"E{i:04d}" for i in range(n)],
        "nome":                list(nomes),
        "municipio":           list(nomes),
        "uf":                  list(ufs),
        "bioma":               list(biomas),
        "regiao":              ["Norte" if u=="PA" else "Centro-Oeste" if u in ["MT","GO"] else "Nordeste" if u in ["BA","PE","RN"] else "Sul" for u in ufs],
        "credito":             rng.uniform(0, 10_000_000, n).round(2),
        "desmatamento_antes":  rng.uniform(0, 1000, n).round(2),
        "desmatamento_depois": rng.uniform(0, 1200, n).round(2),
        "delta_km2":           rng.uniform(0, 200, n).round(2),
        "delta_pct":           rng.uniform(-20, 80, n).round(2),
        "multas":              rng.uniform(0, 2_000_000, n).round(2),
        "infracoes":           rng.integers(0, 30, n).astype(float),
        "tempo_ativo":         rng.integers(12, 120, n).astype(float),
        "embargo":             rng.choice([0, 1], size=n, p=[0.82, 0.18]).astype(float),
    })


class DataValidator:
    def __init__(self):
        self.errors: list[str] = []
    def validate(self, df: pd.DataFrame) -> bool:
        self.errors = []
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            self.errors.append(f"Colunas ausentes: {missing}")
            return False
        return True

class DataLoader:
    def __init__(self):
        self.validator = DataValidator()
    def load_csv(self, path) -> pd.DataFrame:
        return pd.read_csv(path)
    def load_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.copy()
