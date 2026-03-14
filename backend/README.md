# ICAE — Índice de Coerência Ambiental Econômica

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)

Software open source para mensurar o grau de coerência entre incentivos econômicos públicos e desempenho ambiental territorial.

## Instalação

```bash
pip install -r requirements.txt
```

## Uso rápido

```python
from icae import pipeline

results = pipeline.run("dados/municipios.csv")
print(results.head())
```

## Estrutura

```
/ingest      # ETL e validação de dados
/model       # Cálculo do índice
/graph       # Modelagem em grafo
/index       # Construção e exportação do ICAE
/api         # API REST (FastAPI)
/dashboard   # Dashboard interativo (Streamlit)
/docs        # Documentação matemática
/tests       # Testes automatizados
```

## Fórmula Central

```
Risk_i  = α1·ΔD_i + α2·M_i + α3·R_i + α4·Em_i
ICAE_i  = (1 − Risk_i) · (1 − Cr_i)
```

- `ICAE = 1` → máxima coerência
- `ICAE = 0` → incoerência máxima

As provas formais de que `ICAE ∈ [0,1]`, monotonicidade, invariância por reescala e necessidade de `Σαk = 1` estão em [docs/PROVAS_MATEMATICAS.md](docs/PROVAS_MATEMATICAS.md).

## Testes

```bash
pytest tests/
```

Cobre: normalização, WeightConfig, modelo ICAE, exportação, grafo e todas as propriedades formais das [Provas Matemáticas](docs/PROVAS_MATEMATICAS.md) (§2 caso degenerado, §6 casos extremos, §7 invariância, §8 monotonicidade, §9 pesos unitários).

## Princípios

1. Todo cálculo é reproduzível
2. Toda fórmula é pública
3. Todo score é auditável
4. Nenhum peso pode ser oculto
5. Dados brutos nunca são alterados

## Licença

AGPL-3.0 — ver [LICENSE](LICENSE)
