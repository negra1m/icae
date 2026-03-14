# Checklist ICAE — O que falta fazer

> Atualizado em: 2026-03-14
> Base: README principal, `backend/README.md`, `PROVAS_MATEMATICAS.md` e análise do código

---

## Crítico

- [ ] **Arquivo LICENSE ausente** — `backend/README.md` faz badge `[![License: AGPL-3.0]](LICENSE)` e linka `LICENSE`; o arquivo não existe. Adicionar `LICENSE` com o texto AGPL-3.0.
- [x] **Cobertura real limitada a ~200 municípios** — removido `nlargest` de `loader.py`; todos os municípios com dados chegam ao modelo.
- [x] **Municípios sem crédito rural ficam fora da análise** — merge alterado para `outer join`; `credito = 0` preenchido com `fillna(0)`.
- [x] **Municípios sem desmatamento registrado no PRODES ficam fora** — outer join + `fillna(0)` para `area_km2_antes`, `area_km2_depois`, `delta_km2`, `delta_pct`.

---

## Dados & Ingestão

- [ ] **Integração BNDES incompleta** — `backend/ingest/private_incentives.py` tem a estrutura, mas o download real do CSV do BNDES (~70 MB) e a agregação por município não estão totalmente testados/validados com dados reais.
- [ ] **Integração Comex Stat incompleta** — endpoints da API do MDIC estão esboçados mas não validados end-to-end.
- [ ] **Pipeline de incentivos privados não conectado ao fluxo principal** — `private_incentives.py` existe mas não é chamado por `pipeline.py` de forma integrada; `backend/README.md` mostra `pipeline.run()` como entrada única.
- [ ] **`pipeline.run()` aceita CSV local mas não está documentado** — `backend/README.md` mostra `pipeline.run("dados/municipios.csv")`; verificar se essa assinatura ainda existe após refatorações e documentar os campos esperados no CSV.
- [ ] **Sem persistência de dados** — tudo é in-memory; considerar cache em disco (SQLite ou Parquet) para evitar re-fetch a cada restart.
- [ ] **PRODES — biomas novos** (Pampa, Pantanal, Caatinga, Mata Atlântica) só têm série desde 2022; limitação documentada no README principal; aviso na UI via banner de sincronização.
- [x] **Validar cobertura após merge** — log `Cobertura: X/5570 municípios (Y%)` adicionado em `loader.py` após o merge final.

---

## Modelo & Provas Matemáticas

- [x] **Caso degenerado `desmatamento_antes = 0` sem teste** — adicionado `test_delta_desmat_antes_zero` em `TestProvasMatematicas`.
- [x] **Invariância por reescala não testada** — adicionados `test_invariancia_rescala` (crédito ×1000) e `test_invariancia_rescala_desmatamento` (desmat ×100).
- [x] **Monotonicidade não testada** — adicionados 4 testes: `test_monotonicidade_desmatamento`, `_multas`, `_infracoes`, `_embargo`.
- [x] **Casos extremos do ICAE sem cobertura de teste** — adicionados casos 1, 3 e 4 da §6 (`test_caso_extremo_*`).
- [x] **`αk = 0` para um componente inteiro não testado** — adicionados `test_peso_total_em_um_componente` (α1=1) e `test_peso_total_em_embargo` (α4=1, verifica `risk == embargo_norm`).
- [x] **`assert` de range dentro de `fit_transform` é frágil em produção** — substituído por `raise ValueError` explícito em `icae_model.py`; teste `test_raise_value_error_nao_assert` verifica via AST que nenhum `assert` sobre `icae` permanece.

---

## Backend / API

- [x] **Graph Analysis não exposto via API** — adicionados `GET /grafo` (métricas) e `GET /grafo/{id}/vizinhos` em `api/main.py`; grafo reconstruído automaticamente após cada recarga.
- [x] **Pasta `/docs` referenciada no `backend/README.md` não existe** — criada `backend/docs/`; `PROVAS_MATEMATICAS.md` copiado para lá.
- [x] **Streamlit dashboard não referenciado no docker-compose** — serviço `dashboard` adicionado ao `docker-compose.yml` na porta 8501.
- [x] **Sem autenticação em `POST /atualizar`** — rate-limit implementado: máx 3 requisições por minuto; retorna HTTP 429 se excedido.
- [x] **Testes de integração da API ausentes** — criado `backend/tests/test_api.py` com TestClient cobrindo todos os endpoints (ranking, mapa, grafo, simulador, rate-limit, is_proxy).

---

## Frontend

- [ ] **Mapa choropleth sem implementação real** — aba "Mapa" consome `/mapa` mas não há componente de mapa geográfico real (ex.: react-leaflet ou deck.gl com GeoJSON dos municípios); atualmente só retorna JSON. *(requer GeoJSON dos 5.570 municípios — escopo maior)*
- [x] **Tratamento de erros na UI** — banner de progresso adicionado em `App.jsx` quando `status.carregando=true`; indica sincronização em andamento e tempo estimado.
- [x] **Aba "Incentivos Privados" depende de dados incompletos** — aviso explícito adicionado na aba quando dados são demo (antes do grid de KPIs).

---

## Documentação

- [x] **README principal desatualizado na seção "Estrutura"** — seções Estrutura, API e Limitações reescritas com todos os módulos, novos endpoints e avisos de proxy.
- [x] **`backend/README.md` não linka `PROVAS_MATEMATICAS.md`** — link adicionado logo após a fórmula central.
- [x] **README não descreve como rodar os testes** — seção `## Testes` com `pytest tests/` e descrição de cobertura adicionada ao `backend/README.md`.
- [x] **Sem guia de contribuição** (`CONTRIBUTING.md`) — criado com setup, fluxo de PR, regras obrigatórias e o que é/não é aceito.

---

## Qualidade & Infraestrutura

- [x] **Proxies de multa/embargo são estimativas grosseiras** — campo `is_proxy: true` e `campos_proxy` adicionados em `/ranking`, `/municipios` e `/mapa`; README atualizado com nota sobre proxy.
- [x] **Sem CI/CD** — criado `.github/workflows/tests.yml`; roda `pytest tests/test_icae.py` e `pytest tests/test_api.py` em Python 3.11 a cada push/PR para `main`.
- [x] **Sem variáveis de ambiente documentadas** — criado `.env.example` com URLs de todas as APIs, timeouts, anos de referência e taxa de câmbio.
- [ ] **Versionamento da API** — endpoints estão em `/` sem prefixo de versão; considerar `/v1/ranking` para compatibilidade futura. *(breaking change — deixado para v3)*
