"""Threat graph Neo4j client — Cypher query helpers."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    from py2neo import Graph, Node, Relationship
    _PY2NEO_AVAILABLE = True
except ImportError:
    _PY2NEO_AVAILABLE = False
    logger.warning("py2neo not installed — Neo4j graph features disabled")


def _get_graph() -> "Graph | None":  # noqa: F821
    if not _PY2NEO_AVAILABLE:
        return None
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "neo4j_password")
    try:
        return Graph(uri, auth=(user, password))
    except Exception as exc:
        logger.error(f"Neo4j connection failed: {exc}")
        return None


def upsert_threat_node(
    node_type: str,
    label: str,
    risk_score: float,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """
    Create or update a threat node in Neo4j.

    Returns:
        The Neo4j element ID string, or None if unavailable.
    """
    graph = _get_graph()
    if graph is None:
        logger.warning("Neo4j unavailable — skipping node upsert")
        return None

    try:
        node = Node(
            node_type.capitalize(),
            label=label,
            risk_score=risk_score,
            **(metadata or {}),
        )
        graph.merge(node, node_type.capitalize(), "label")
        return str(node.identity)
    except Exception as exc:
        logger.error(f"Neo4j upsert error: {exc}")
        return None


def create_relationship(
    from_label: str,
    from_type: str,
    rel_type: str,
    to_label: str,
    to_type: str,
) -> bool:
    """Create a directed relationship between two nodes. Returns True on success."""
    graph = _get_graph()
    if graph is None:
        return False
    try:
        from_node = graph.nodes.match(from_type.capitalize(), label=from_label).first()
        to_node = graph.nodes.match(to_type.capitalize(), label=to_label).first()
        if from_node and to_node:
            rel = Relationship(from_node, rel_type, to_node)
            graph.merge(rel)
            return True
    except Exception as exc:
        logger.error(f"Neo4j relationship error: {exc}")
    return False


def query_high_risk_nodes(threshold: float = 0.7, limit: int = 50) -> list[dict]:
    """Return all nodes with risk_score >= threshold."""
    graph = _get_graph()
    if graph is None:
        return []
    try:
        results = graph.run(
            "MATCH (n) WHERE n.risk_score >= $threshold RETURN n LIMIT $limit",
            threshold=threshold, limit=limit,
        )
        return [dict(record["n"]) for record in results]
    except Exception as exc:
        logger.error(f"Neo4j query error: {exc}")
        return []
