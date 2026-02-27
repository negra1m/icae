# ICAE — Índice de Coerência Ambiental Econômica
**Versão 2.0 — Cobertura Nacional**

Cruza crédito rural público (SICOR/BCB) com desmatamento (PRODES/INPE)
em todos os 6 biomas brasileiros, por município.

## Fontes de dados reais

| Fonte | O que fornece | Endpoint |
|-------|--------------|----------|
| SICOR/BCB | Crédito rural por município (5.570 municípios) | `olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata` |
| PRODES/INPE via TerraBrasilis | Desmatamento anual por município — 6 biomas | `terrabrasilis.dpi.inpe.br/dashboard/api/v1/redis-cli` |
| IBGE Localidades | Código IBGE, nome, UF, coordenadas | `servicodados.ibge.gov.br/api/v1/localidades/municipios` |

## Iniciar

```bash
docker compose up --build
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

## Estrutura

```
backend/
  ingest/loader.py      ← ETL: SICOR + PRODES + IBGE (nacional)
  model/icae_model.py   ← fórmula ICAE
  index/exporter.py     ← ranking e exportação
  api/main.py           ← REST API (FastAPI)
frontend/
  src/App.jsx           ← dashboard React com mapa do Brasil
```

## API

| Endpoint | Descrição |
|----------|-----------|
| `GET /ranking?uf=PA&bioma=Amazônia&top=50` | Ranking filtrado |
| `GET /municipios` | Resumo por município |
| `GET /mapa` | Dados para o mapa choropleth |
| `GET /biomas` | Estatísticas por bioma |
| `GET /regioes` | Estatísticas por região |
| `GET /status` | Estado do cache e fontes |
| `POST /atualizar` | Recarrega dados reais em background |
| `POST /simular` | Recalcula com pesos customizados |

## Limitações conhecidas

- **Multas/embargo individuais**: proxy via delta de desmatamento
  até integração com IBAMA/SINAFLOR (não há API pública disponível)
- **Biomas novos** (Pampa, Pantanal, Caatinga, Mata Atlântica):
  PRODES só tem série histórica desde 2022 para esses biomas
- **Carga inicial**: ~2–5 minutos para puxar dados de todos os biomas;
  enquanto isso a API serve dados demo

## Licença

AGPL-3.0 — código aberto, auditável, reproduzível.
