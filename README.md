# ICAE — Índice de Coerência Ambiental Econômica
**Versão 2.0 — Cobertura Nacional**

Cruza crédito rural público (SICOR/BCB) com desmatamento (PRODES/INPE)
em todos os 6 biomas brasileiros, por município.

---

## Índices Matemáticos

### 1. Normalização Min-Max

Todas as variáveis de entrada são normalizadas para o intervalo [0, 1] antes do cálculo:

```
X_norm = (X − min(X)) / (max(X) − min(X))
```

Garante comparabilidade entre variáveis de escalas diferentes (R$, km², contagens).
Se a série for constante (`max = min`), todos os valores são definidos como 0.

---

### 2. Variação de Desmatamento — ΔD_i

Mede o aumento percentual de desmatamento no município `i` após o recebimento de crédito rural:

```
ΔD_i = (desmat_depois_i − desmat_antes_i) / (desmat_antes_i + ε)
ΔD_i = max(ΔD_i, 0)    ← só penaliza aumento; reduções valem 0
```

- `ε = 1×10⁻⁶` evita divisão por zero
- Valores negativos (município que reduziu desmatamento) são clipados em 0 — o índice não recompensa, apenas penaliza piora

---

### 3. Índice de Reincidência — R_i

Normaliza o número de infrações pelo tempo de atividade do produtor, evitando viés contra propriedades mais antigas:

```
R_i = infracoes_i / (tempo_ativo_i + ε)
```

- `infracoes` → contagem de autuações ambientais (proxy: `delta_km2 / 10`, cap em 50)
- `tempo_ativo` → meses de operação (padrão: 36 meses)

---

### 4. Vetor de Risco Ambiental — Risk_i

Combinação linear ponderada dos quatro componentes de risco:

```
Risk_i = α1·ΔD_i + α2·M_i + α3·R_i + α4·Em_i
```

| Componente | Símbolo | Peso padrão | Descrição |
|-----------|---------|-------------|-----------|
| Variação de desmatamento | ΔD_i | α1 = 0,25 | Δ% de área desmatada pós-incentivo |
| Multas ambientais | M_i | α2 = 0,25 | Valor normalizado de multas (proxy: `delta_km2 × 1000`) |
| Reincidência | R_i | α3 = 0,25 | Infrações por mês de atividade |
| Embargo | Em_i | α4 = 0,25 | Binário: 1 se `delta_km2 / desmat_antes > 30%` |

**Restrição obrigatória:** `α1 + α2 + α3 + α4 = 1`, com `αk ≥ 0`

Resultado: `Risk_i ∈ [0, 1]` — quanto maior, pior o desempenho ambiental.

---

### 5. ICAE — Índice Final

```
ICAE_i = (1 − Risk_i) · (1 − Cr_i)
```

- `Cr_i` → crédito rural normalizado (Min-Max sobre todos os municípios)
- `Risk_i` → vetor de risco calculado acima

| Valor | Interpretação |
|-------|--------------|
| ICAE = 1 | Máxima coerência: alto risco ambiental implica baixo crédito |
| ICAE = 0 | Incoerência máxima: alto crédito público para município de alto risco |

A multiplicação garante que **ICAE só é alto quando ambos os fatores são baixos**: risco ambiental baixo E crédito proporcionalmente baixo ao risco.

**Garantia matemática:** `ICAE_i ∈ [0, 1]` para todo `i`.

---

### Proxies ativos (até integração com IBAMA/SINAFLOR)

Como não existe API pública de multas e embargos individuais, as variáveis M, Em e R são estimadas a partir do delta de desmatamento PRODES:

```
M_i   = delta_km2_i × 1.000          (proxy de valor de multa em R$)
R_i   = (delta_km2_i / 10), cap 50   (proxy de contagem de infrações)
Em_i  = 1  se  delta_km2_i / desmat_antes_i > 0,30
         0  caso contrário
```

---

## Fontes de dados

| Fonte | O que fornece | Endpoint |
|-------|--------------|----------|
| SICOR/BCB | Crédito rural por município (5.570 municípios) | `olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata` |
| PRODES/INPE via TerraBrasilis | Desmatamento anual por município — 6 biomas | `terrabrasilis.dpi.inpe.br/dashboard/api/v1/redis-cli` |
| IBGE Localidades | Código IBGE, nome, UF, coordenadas | `servicodados.ibge.gov.br/api/v1/localidades/municipios` |

---

## Iniciar

```bash
docker compose up --build
```

- Dashboard: http://localhost:3000
- API docs: http://localhost:8000/docs

---

## Estrutura

```
backend/
  ingest/loader.py      ← ETL: SICOR + PRODES + IBGE (nacional)
  model/icae_model.py   ← fórmulas ΔD, R, Risk e ICAE
  index/exporter.py     ← ranking e exportação
  api/main.py           ← REST API (FastAPI)
frontend/
  src/App.jsx           ← dashboard React com mapa do Brasil
```

---

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
| `POST /simular` | Recalcula com pesos customizados (α1…α4) |

---

## Limitações conhecidas

- **Multas/embargo individuais**: proxy via delta de desmatamento até integração com IBAMA/SINAFLOR (não há API pública disponível)
- **Biomas novos** (Pampa, Pantanal, Caatinga, Mata Atlântica): PRODES só tem série histórica desde 2022 para esses biomas
- **Carga inicial**: ~2–5 minutos para puxar dados de todos os biomas; enquanto isso a API serve dados demo

---

## Princípios

1. Todo cálculo é reproduzível
2. Toda fórmula é pública
3. Todo score é auditável
4. Nenhum peso pode ser oculto
5. Dados brutos nunca são alterados

---

## Licença

AGPL-3.0 — código aberto, auditável, reproduzível.
