# Contribuindo com o ICAE

Obrigado pelo interesse. O ICAE é software livre (AGPL-3.0) — toda contribuição deve preservar os cinco princípios do projeto: reprodutibilidade, transparência, auditabilidade, pesos públicos e dados brutos intactos.

## Pré-requisitos

- Python 3.10+
- Node 20+ (frontend)
- Docker + Docker Compose (para rodar o stack completo)

## Setup local

```bash
# Backend
cd backend
pip install -r requirements.txt
pytest tests/          # todos os testes devem passar

# Frontend
cd frontend
npm install
npm run dev            # http://localhost:3000

# Stack completo
docker compose up --build
```

## Fluxo de contribuição

1. Abra uma **issue** descrevendo o problema ou melhoria antes de começar
2. Faça um fork e crie um branch: `git checkout -b feat/minha-melhoria`
3. Escreva código e **testes** — PRs sem testes não são aceitos
4. Garanta que `pytest backend/tests/` passa completamente
5. Abra um Pull Request com descrição clara do que muda e por quê

## Regras obrigatórias

| Regra | Motivo |
|-------|--------|
| Toda fórmula nova deve ter prova formal em `backend/docs/PROVAS_MATEMATICAS.md` | Princípio de auditabilidade |
| Pesos `αk` nunca podem ser fixados em código sem exposição via API | Princípio de transparência |
| Dados brutos de SICOR/PRODES/IBGE nunca são modificados | Princípio de reprodutibilidade |
| Campos calculados por proxy devem ter `is_proxy: true` na resposta da API | Distinguir estimativa de dado real |
| Sem `assert` em código de produção — usar `raise ValueError` | `assert` é desativado com `python -O` |

## O que aceito como contribuição

- Integração com APIs reais de multas/embargo (IBAMA, SINAFLOR)
- Melhoria na cobertura de municípios (merge strategies)
- Novos endpoints de análise no grafo relacional
- Mapa choropleth real com GeoJSON dos municípios
- Melhorias de performance no ETL nacional

## O que não aceito

- Mudanças nos pesos padrão sem evidência empírica justificada
- Remoção de colunas intermediárias de auditoria
- Dependências proprietárias ou que exijam autenticação privada
- Código que oculte ou ofusque qualquer parte do cálculo

## Dúvidas

Abra uma issue com a tag `pergunta`.
