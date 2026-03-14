"""
ICAE — Testes de Integração HTTP
Valida endpoints da API REST com TestClient (sem servidor real).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


# ── Endpoints básicos ─────────────────────────────────────────────────────────

class TestEndpointsBasicos:
    def test_root_online(self):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "online"

    def test_status_schema(self):
        r = client.get("/status")
        assert r.status_code == 200
        body = r.json()
        assert "fonte" in body
        assert "n_municipios" in body
        assert "carregando" in body
        assert isinstance(body["n_municipios"], int)
        assert body["n_municipios"] > 0

    def test_formula_campos(self):
        r = client.get("/formula")
        assert r.status_code == 200
        body = r.json()
        assert "icae" in body
        assert "risk_vector" in body
        assert "pesos_padrão" in body


# ── Ranking e filtros ─────────────────────────────────────────────────────────

class TestRanking:
    def test_ranking_retorna_lista(self):
        r = client.get("/ranking")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) > 0

    def test_ranking_top_n(self):
        r = client.get("/ranking?top=5")
        assert r.status_code == 200
        assert len(r.json()) <= 5

    def test_ranking_campos_obrigatorios(self):
        r = client.get("/ranking?top=3")
        item = r.json()[0]
        for campo in ["entity_id", "icae", "risk", "rank"]:
            assert campo in item, f"Campo '{campo}' ausente no ranking"

    def test_ranking_icae_range(self):
        r = client.get("/ranking?top=50")
        for item in r.json():
            assert 0.0 <= item["icae"] <= 1.0, f"ICAE fora de [0,1]: {item['icae']}"

    def test_ranking_filtro_uf_invalida(self):
        r = client.get("/ranking?uf=XX")
        assert r.status_code == 404

    def test_ranking_is_proxy_presente(self):
        r = client.get("/ranking?top=5")
        item = r.json()[0]
        assert "is_proxy" in item
        assert "campos_proxy" in item
        assert isinstance(item["is_proxy"], bool)


# ── Município e mapa ──────────────────────────────────────────────────────────

class TestMunicipios:
    def test_municipios_retorna_lista(self):
        r = client.get("/municipios")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_municipios_icae_medio_range(self):
        r = client.get("/municipios")
        for m in r.json():
            if "icae_medio" in m:
                assert 0.0 <= m["icae_medio"] <= 1.0

    def test_mapa_retorna_lista(self):
        r = client.get("/mapa")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_mapa_severidade_presente(self):
        r = client.get("/mapa")
        body = r.json()
        if body:
            assert "severidade" in body[0]
            assert body[0]["severidade"] in ("crítico", "alto", "moderado", "estável", "desconhecido")

    def test_mapa_is_proxy_presente(self):
        r = client.get("/mapa")
        body = r.json()
        if body:
            assert "is_proxy" in body[0]


# ── Biomas e regiões ──────────────────────────────────────────────────────────

class TestBiomasRegioes:
    def test_biomas_retorna_lista(self):
        r = client.get("/biomas")
        assert r.status_code in (200,)
        assert isinstance(r.json(), list)

    def test_regioes_retorna_lista(self):
        r = client.get("/regioes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Simulador ─────────────────────────────────────────────────────────────────

class TestSimulador:
    def test_simular_pesos_validos(self):
        r = client.post("/simular", json={
            "alpha1_desmatamento": 0.4,
            "alpha2_multas": 0.3,
            "alpha3_reincidencia": 0.2,
            "alpha4_embargo": 0.1,
            "top": 10,
        })
        assert r.status_code == 200
        body = r.json()
        assert "icae_medio" in body
        assert "ranking" in body
        assert 0.0 <= body["icae_medio"] <= 1.0

    def test_simular_pesos_invalidos(self):
        r = client.post("/simular", json={
            "alpha1_desmatamento": 0.5,
            "alpha2_multas": 0.5,
            "alpha3_reincidencia": 0.5,
            "alpha4_embargo": 0.5,
            "top": 10,
        })
        assert r.status_code == 422

    def test_simular_icae_range(self):
        r = client.post("/simular", json={
            "alpha1_desmatamento": 1.0,
            "alpha2_multas": 0.0,
            "alpha3_reincidencia": 0.0,
            "alpha4_embargo": 0.0,
            "top": 20,
        })
        assert r.status_code == 200
        for item in r.json()["ranking"]:
            assert 0.0 <= item["icae"] <= 1.0


# ── Grafo ─────────────────────────────────────────────────────────────────────

class TestGrafo:
    def test_grafo_resumo(self):
        r = client.get("/grafo")
        assert r.status_code == 200
        body = r.json()
        assert "total_nodes" in body
        assert "total_edges" in body
        assert "entity_nodes" in body
        assert body["total_nodes"] > 0

    def test_grafo_vizinhos_entidade_invalida(self):
        r = client.get("/grafo/ENTIDADE_INEXISTENTE_XYZ/vizinhos")
        assert r.status_code == 404

    def test_grafo_vizinhos_entidade_valida(self):
        # Pega a primeira entidade do ranking
        ranking = client.get("/ranking?top=1").json()
        if ranking:
            eid = ranking[0]["entity_id"]
            r = client.get(f"/grafo/{eid}/vizinhos?top=3")
            assert r.status_code == 200
            body = r.json()
            assert "entity_id" in body
            assert "vizinhos_alto_risco" in body
            assert isinstance(body["vizinhos_alto_risco"], list)


# ── Rate-limit /atualizar ─────────────────────────────────────────────────────

class TestRateLimit:
    def test_atualizar_aceita_primeira_requisicao(self):
        r = client.post("/atualizar")
        # Pode retornar 200 (iniciou) ou 200 (já carregando) — nunca 429 na primeira
        assert r.status_code == 200

    def test_atualizar_rate_limit(self):
        import time
        from api.main import _atualizar_timestamps
        # Força 3 timestamps recentes
        agora = time.time()
        _atualizar_timestamps.clear()
        _atualizar_timestamps.extend([agora, agora, agora])
        r = client.post("/atualizar")
        assert r.status_code == 429
        _atualizar_timestamps.clear()


# ── Entidade individual ───────────────────────────────────────────────────────

class TestEntidade:
    def test_entidade_existente(self):
        ranking = client.get("/ranking?top=1").json()
        if ranking:
            eid = ranking[0]["entity_id"]
            r = client.get(f"/entidade/{eid}")
            assert r.status_code == 200
            assert "icae" in r.json()

    def test_entidade_inexistente(self):
        r = client.get("/entidade/XXXX_NAO_EXISTE")
        assert r.status_code == 404
