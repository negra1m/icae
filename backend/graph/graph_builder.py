"""
ICAE — Módulo de Grafo
Constrói grafo relacional de entidades para análises indiretas.

Nós: Propriedade, Município, Produtor, Crédito, Multa, Área
Arestas: Recebeu, Possui, Está em, Foi autuado por
"""

import networkx as nx
import pandas as pd
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Tipos de nó
NODE_ENTITY   = "Entidade"
NODE_MUNICIPIO= "Municipio"
NODE_CREDITO  = "Credito"
NODE_MULTA    = "Multa"

# Tipos de aresta
EDGE_RECEBEU  = "recebeu"
EDGE_ESTA_EM  = "esta_em"
EDGE_AUTUADO  = "foi_autuado"
EDGE_SIMILAR  = "similar_icae"


def build_graph(df_icae: pd.DataFrame) -> nx.DiGraph:
    """
    Constrói grafo dirigido a partir dos dados ICAE calculados.

    Nós:
        - Entidades (propriedades/municípios)
        - Municípios
        - Créditos individuais
        - Multas individuais

    Arestas:
        - Entidade → Município (está_em)
        - Entidade → Crédito (recebeu)
        - Entidade → Multa (foi_autuado)
    """
    G = nx.DiGraph()

    # Adiciona entidades
    for _, row in df_icae.iterrows():
        eid = row["entity_id"]
        G.add_node(
            eid,
            type=NODE_ENTITY,
            icae=float(row.get("icae", 0)),
            risk=float(row.get("risk", 0)),
            credito_norm=float(row.get("credito_norm", 0)),
            label=str(row.get("nome", eid)),
        )

        # Nó município
        municipio = row.get("municipio")
        if pd.notna(municipio):
            mun_id = f"MUN_{municipio}"
            if not G.has_node(mun_id):
                G.add_node(mun_id, type=NODE_MUNICIPIO, label=municipio)
            G.add_edge(eid, mun_id, type=EDGE_ESTA_EM)

        # Nó crédito
        credito = row.get("credito", 0)
        if pd.notna(credito) and credito > 0:
            cred_id = f"CRED_{eid}"
            G.add_node(cred_id, type=NODE_CREDITO, valor=float(credito))
            G.add_edge(eid, cred_id, type=EDGE_RECEBEU, valor=float(credito))

        # Nó multa
        multas = row.get("multas", 0)
        if pd.notna(multas) and multas > 0:
            multa_id = f"MULTA_{eid}"
            G.add_node(multa_id, type=NODE_MULTA, valor=float(multas))
            G.add_edge(eid, multa_id, type=EDGE_AUTUADO, valor=float(multas))

    logger.info(
        f"Grafo construído: {G.number_of_nodes()} nós, "
        f"{G.number_of_edges()} arestas"
    )
    return G


def add_similarity_edges(
    G: nx.DiGraph,
    df_icae: pd.DataFrame,
    threshold: float = 0.05,
) -> nx.DiGraph:
    """
    Adiciona arestas de similaridade entre entidades com ICAE próximo.
    Útil para identificar clusters de comportamento.
    """
    entities = [(row["entity_id"], row["icae"])
                for _, row in df_icae.iterrows()
                if "icae" in df_icae.columns]

    added = 0
    for i, (id1, icae1) in enumerate(entities):
        for id2, icae2 in entities[i+1:]:
            if abs(icae1 - icae2) <= threshold:
                G.add_edge(id1, id2, type=EDGE_SIMILAR,
                           icae_diff=abs(icae1 - icae2))
                added += 1

    logger.info(f"Adicionadas {added} arestas de similaridade (threshold={threshold})")
    return G


def graph_summary(G: nx.DiGraph) -> dict:
    """Retorna métricas descritivas do grafo."""
    entity_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == NODE_ENTITY]
    return {
        "total_nodes":     G.number_of_nodes(),
        "total_edges":     G.number_of_edges(),
        "entity_nodes":    len(entity_nodes),
        "municipio_nodes": sum(1 for _, d in G.nodes(data=True) if d.get("type") == NODE_MUNICIPIO),
        "credito_nodes":   sum(1 for _, d in G.nodes(data=True) if d.get("type") == NODE_CREDITO),
        "multa_nodes":     sum(1 for _, d in G.nodes(data=True) if d.get("type") == NODE_MULTA),
        "density":         nx.density(G),
        "weakly_connected_components": nx.number_weakly_connected_components(G),
    }


def top_risk_neighbors(G: nx.DiGraph, entity_id: str, n: int = 5) -> list[dict]:
    """
    Retorna os N vizinhos de entidade_id com maior risco ambiental.
    Útil para análise de contágio de risco no grafo.
    """
    neighbors = list(G.predecessors(entity_id)) + list(G.successors(entity_id))
    entity_neighbors = [
        {"entity_id": nb, **G.nodes[nb]}
        for nb in neighbors
        if G.nodes[nb].get("type") == NODE_ENTITY
    ]
    return sorted(entity_neighbors, key=lambda x: x.get("risk", 0), reverse=True)[:n]


def municipio_aggregated_icae(G: nx.DiGraph) -> pd.DataFrame:
    """
    Agrega ICAE médio por município via grafo.
    """
    records = []
    for node, data in G.nodes(data=True):
        if data.get("type") == NODE_MUNICIPIO:
            # Predecessores são as entidades que estão no município
            entities_in = [
                G.nodes[pred]
                for pred in G.predecessors(node)
                if G.nodes[pred].get("type") == NODE_ENTITY
            ]
            if entities_in:
                icae_values = [e["icae"] for e in entities_in if "icae" in e]
                risk_values = [e["risk"] for e in entities_in if "risk" in e]
                records.append({
                    "municipio": data["label"],
                    "n_entidades": len(entities_in),
                    "icae_medio": float(np.mean(icae_values)) if icae_values else None,
                    "risk_medio": float(np.mean(risk_values)) if risk_values else None,
                })

    import numpy as np
    return pd.DataFrame(records).sort_values("icae_medio")
