# Provas Matemáticas — ICAE

> Documento de verificação formal das propriedades dos índices.
> Cada prova parte das definições do modelo e demonstra as garantias anunciadas.

---

## 1. Normalização Min-Max → saída em [0, 1]

**Definição:**
```
X_norm_i = (X_i − min(X)) / (max(X) − min(X))
```

**Prova:**

Seja `m = min(X)` e `M = max(X)`, com `M > m` (caso não-degenerado).

Por definição de mínimo e máximo:
```
m ≤ X_i ≤ M  para todo i
```

Subtraindo `m`:
```
0 ≤ X_i − m ≤ M − m
```

Como `M − m > 0`, dividindo por `M − m` (operação que preserva a ordem):
```
0 ≤ (X_i − m) / (M − m) ≤ 1
```

Portanto: **`X_norm_i ∈ [0, 1]` para todo `i`.**

**Casos extremos:**
- `X_i = m` → `X_norm_i = 0` (mínimo absoluto)
- `X_i = M` → `X_norm_i = 1` (máximo absoluto)

**Caso degenerado (`M = m`, série constante):**
Por convenção do modelo (`icae_model.py:64`), retorna 0 para todos.
Interpretação: sem variação entre municípios, nenhum é mais arriscado que o outro → risco relativo zero. ∎

---

## 2. ΔD_i (Variação de Desmatamento) → saída em [0, +∞)

**Definição:**
```
ΔD_i = max( (D_depois_i − D_antes_i) / (D_antes_i + ε) , 0 )
```
com `ε = 1×10⁻⁶`.

**Prova de não-negatividade:**

O operador `max(·, 0)` garante por construção que `ΔD_i ≥ 0`. ∎

**Prova de que reduções de desmatamento valem 0 (não recompensam):**

Se `D_depois_i < D_antes_i`, então `D_depois_i − D_antes_i < 0`.
A fração é negativa. O `max(·, 0)` clipeia em 0.
Portanto municípios que reduziram desmatamento não têm vantagem no índice de risco — a assimetria é intencional: o índice penaliza piora, não premia melhora. ∎

**Prova de que `ε` evita divisão por zero:**

O denominador é sempre `D_antes_i + ε ≥ ε = 10⁻⁶ > 0`.
Mesmo com `D_antes_i = 0` (município sem histórico de desmatamento), o cálculo é definido. ∎

**Nota:** Após normalização Min-Max, `ΔD_norm_i ∈ [0, 1]` (pela Prova 1).

---

## 3. R_i (Índice de Reincidência) → saída em [0, +∞)

**Definição:**
```
R_i = infracoes_i / (tempo_ativo_i + ε)
```

**Prova de não-negatividade:**

`infracoes_i ≥ 0` (contagem de autuações, nunca negativa).
`tempo_ativo_i + ε ≥ ε > 0`.
Portanto `R_i ≥ 0`. ∎

**Prova de que normaliza por tempo (sem viés contra operações antigas):**

Seja produtor A com 10 infrações em 10 meses: `R_A = 10/10 = 1.0`
Seja produtor B com 10 infrações em 120 meses: `R_B = 10/120 ≈ 0.083`

Sem normalização por tempo, ambos teriam `infracoes = 10` — o mesmo score.
Com `R_i`, o produtor com mais tempo de atividade recebe score menor para o mesmo número de infrações absolutas. ∎

**Nota:** Após normalização Min-Max, `R_norm_i ∈ [0, 1]` (pela Prova 1).

---

## 4. Risk_i (Vetor de Risco Ambiental) → saída em [0, 1]

**Definição:**
```
Risk_i = α1·ΔD_norm_i + α2·M_norm_i + α3·R_norm_i + α4·Em_i
```

com restrições:
- `αk ≥ 0` para todo `k`
- `α1 + α2 + α3 + α4 = 1`
- `ΔD_norm_i, M_norm_i, R_norm_i ∈ [0, 1]` (pela Prova 1)
- `Em_i ∈ {0, 1}` ⊂ [0, 1] (binário)

**Prova do limite inferior (`Risk_i ≥ 0`):**

Cada termo `αk · componente_k ≥ 0` pois `αk ≥ 0` e `componente_k ≥ 0`.
Soma de termos não-negativos é não-negativa. ∎

**Prova do limite superior (`Risk_i ≤ 1`):**

```
Risk_i = α1·ΔD_norm_i + α2·M_norm_i + α3·R_norm_i + α4·Em_i
       ≤ α1·1 + α2·1 + α3·1 + α4·1    (pois cada componente ≤ 1)
       = α1 + α2 + α3 + α4
       = 1                              (restrição de soma dos pesos)
```

Portanto: **`Risk_i ∈ [0, 1]` para todo `i`**. ∎

**Interpretação dos extremos:**
- `Risk_i = 0`: município com zero em todos os 4 componentes de risco
- `Risk_i = 1`: município no pior nível de todos os 4 componentes simultaneamente

---

## 5. ICAE_i → saída em [0, 1]

**Definição:**
```
ICAE_i = (1 − Risk_i) · (1 − Cr_norm_i)
```

com:
- `Risk_i ∈ [0, 1]` (pela Prova 4)
- `Cr_norm_i ∈ [0, 1]` (pela Prova 1, normalização do crédito rural)

**Prova do limite inferior (`ICAE_i ≥ 0`):**

`1 − Risk_i ≥ 0` pois `Risk_i ≤ 1`.
`1 − Cr_norm_i ≥ 0` pois `Cr_norm_i ≤ 1`.
Produto de dois fatores não-negativos é não-negativo. ∎

**Prova do limite superior (`ICAE_i ≤ 1`):**

```
ICAE_i = (1 − Risk_i) · (1 − Cr_norm_i)
       ≤ 1 · 1    (pois ambos os fatores ≤ 1)
       = 1
```
∎

Portanto: **`ICAE_i ∈ [0, 1]` para todo `i`**. ∎

---

## 6. Propriedade de Coerência — o produto garante dupla exigência

**Teorema:** ICAE é alto **somente se** risco ambiental é baixo **E** crédito recebido é proporcionalmente baixo.

**Prova:**

ICAE_i = (1 − Risk_i) · (1 − Cr_norm_i)

O produto de dois fatores só é próximo de 1 quando ambos são próximos de 1, ou seja:

- `(1 − Risk_i) ≈ 1` ↔ `Risk_i ≈ 0` (baixo risco ambiental)
- `(1 − Cr_norm_i) ≈ 1` ↔ `Cr_norm_i ≈ 0` (baixo crédito relativo)

**Caso 1 — alto risco, alto crédito (incoerência máxima):**
```
Risk_i ≈ 1, Cr_norm_i ≈ 1
ICAE_i ≈ (1−1)·(1−1) = 0·0 = 0
```

**Caso 2 — baixo risco, alto crédito (coerente, mas limitado):**
```
Risk_i ≈ 0, Cr_norm_i ≈ 1
ICAE_i ≈ (1−0)·(1−1) = 1·0 = 0
```
Municípios que recebem muito crédito público nunca atingem ICAE = 1, independentemente do risco. Isso é intencional: o índice mede incoerência do sistema de crédito, não mérito ambiental isolado.

**Caso 3 — alto risco, baixo crédito (parcialmente coerente):**
```
Risk_i ≈ 1, Cr_norm_i ≈ 0
ICAE_i ≈ (1−1)·(1−0) = 0·1 = 0
```
Município de alto risco não deveria receber crédito — se não recebeu, o índice é 0 de qualquer forma (risco já elimina o fator ambiental).

**Caso 4 — baixo risco, baixo crédito (coerência máxima):**
```
Risk_i ≈ 0, Cr_norm_i ≈ 0
ICAE_i ≈ (1−0)·(1−0) = 1·1 = 1
```

Apenas municípios com **ambos** baixo risco e baixo crédito atingem ICAE próximo de 1. ∎

**Consequência importante:** A fórmula multiplicativa é mais restritiva que uma soma ponderada. Uma soma permitiria que alto desempenho em uma dimensão compensasse falha na outra. O produto não permite. Isso é uma escolha de design deliberada.

---

## 7. Invariância sob reescala dos dados brutos

**Teorema:** ICAE é invariante sob transformações lineares positivas das variáveis de entrada.

**Prova:**

Seja `X' = a·X + b` com `a > 0`. Então:

```
min(X') = a·min(X) + b
max(X') = a·max(X) + b

X'_norm = (X'_i − min(X')) / (max(X') − min(X'))
        = (a·X_i + b − a·min(X) − b) / (a·max(X) + b − a·min(X) − b)
        = a·(X_i − min(X)) / a·(max(X) − min(X))
        = (X_i − min(X)) / (max(X) − min(X))
        = X_norm
```

A normalização Min-Max cancela qualquer transformação linear positiva.
Portanto, o ICAE é o mesmo se crédito está em R$, milhares de R$ ou qualquer outra escala linear. ∎

---

## 8. Monotonicidade do Risco

**Teorema:** Para pesos fixos, `Risk_i` é monotonicamente crescente em cada componente isolado.

**Prova:**

Fixando todos os outros municípios (o que fixa `min` e `max` da normalização) e aumentando apenas `ΔD_j` para algum `j`:

```
∂Risk_j / ∂ΔD_norm_j = α1 ≥ 0
```

Como `α1 ≥ 0`, `Risk_j` não decresce quando `ΔD_norm_j` aumenta.
O mesmo vale para `M_norm`, `R_norm` e `Em` com seus respectivos pesos. ∎

**Corolário:** `ICAE_j` é monotonicamente decrescente em cada componente de risco:
```
∂ICAE_j / ∂Risk_j = −(1 − Cr_norm_j) ≤ 0
```
Pois `1 − Cr_norm_j ≥ 0`. ∎

---

## 9. Verificação dos pesos: unicidade da soma

**Teorema:** A restrição `α1 + α2 + α3 + α4 = 1` é necessária para que `Risk_i ∈ [0,1]`.

**Prova (contrapositiva):**

Se `Σαk = s ≠ 1`, então com todos os componentes = 1:
```
Risk_i = s·1 = s
```

Se `s > 1`, então `Risk_i` poderia exceder 1, tornando `(1 − Risk_i) < 0` e potencialmente `ICAE_i < 0`.
Se `s < 1`, então mesmo no pior caso ambiental `Risk_i < 1`, e o índice nunca atingiria o valor máximo de incoerência.

Portanto, `Σαk = 1` é condição necessária para que o range `[0,1]` seja preservado. ∎

**Implementação:** `WeightConfig.__post_init__` verifica isso em runtime via `np.isclose(total, 1.0, atol=1e-6)` e levanta `ValueError` se violado (`icae_model.py:42-43`).

---

## Resumo das Garantias

| Propriedade | Garantia | Prova |
|---|---|---|
| `X_norm ∈ [0,1]` | Min-Max preserva range | §1 |
| `ΔD_i ≥ 0` | clip(lower=0) | §2 |
| `R_i ≥ 0` | infracoes/tempo ≥ 0 | §3 |
| `Risk_i ∈ [0,1]` | combinação convexa de termos ∈ [0,1] | §4 |
| `ICAE_i ∈ [0,1]` | produto de fatores ∈ [0,1] | §5 |
| ICAE alto ↔ baixo risco E baixo crédito | propriedade multiplicativa | §6 |
| Invariância por escala | cancelamento na normalização | §7 |
| Risco monotônico nos componentes | derivada ≥ 0 | §8 |
| Necessidade de Σαk = 1 | condição de range | §9 |
