"""
Threat Graph — Neo4j Client
============================
Manages the py2neo connection to Neo4j and provides Cypher query helpers.
All methods degrade gracefully when Neo4j is offline.

Design principles:
  - No hard startup failure — Neo4j being offline does not crash Django
  - health_check() returns structured dict for /api/graph/health/ endpoint
  - All public methods return typed Python objects (never raw py2neo types)

Author: Sanyam Gehlot
"""
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


# ── Connection factory ─────────────────────────────────────────────────────────

def _get_graph() -> "Graph | None":
    """
    Return a connected py2neo Graph instance, or None if unavailable.
    Connection errors are caught and logged — never propagated to callers.
    """
    if not _PY2NEO_AVAILABLE:
        return None

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "neo4j_password")

    try:
        graph = Graph(uri, auth=(user, password))
        # Force connection validation (py2neo is lazy)
        graph.run("RETURN 1")
        return graph
    except Exception as exc:
        logger.error(f"Neo4j connection failed ({uri}): {exc}")
        return None


# ── Health check ───────────────────────────────────────────────────────────────

def health_check() -> dict:
    """
    Test Neo4j connectivity and return a structured status dict.

    Returns:
        {
            "status":  "ok" | "offline",
            "uri":     str,
            "version": str | None,    # Neo4j server version if reachable
            "error":   str | None,    # error message if offline
        }
    """
    if not _PY2NEO_AVAILABLE:
        return {
            "status": "offline",
            "uri": "N/A",
            "version": None,
            "error": "py2neo not installed",
        }

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "neo4j_password")

    try:
        graph = Graph(uri, auth=(user, password))
        result = graph.run("CALL dbms.components() YIELD name, versions RETURN name, versions").data()
        version = result[0]["versions"][0] if result else "unknown"
        return {
            "status": "ok",
            "uri": uri,
            "version": version,
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "offline",
            "uri": uri,
            "version": None,
            "error": str(exc),
        }


# ── Node operations ────────────────────────────────────────────────────────────

def upsert_threat_node(
    node_type: str,
    label: str,
    risk_score: float,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """
    Create or update a threat entity node in Neo4j.

    Args:
        node_type:  Node label category e.g. "ip", "domain", "email".
        label:      The entity value e.g. "192.168.1.1".
        risk_score: Threat score [0.0, 1.0].
        metadata:   Optional extra properties merged onto the node.

    Returns:
        Neo4j element ID as string, or None if operation failed.
    """
    graph = _get_graph()
    if graph is None:
        logger.warning("Neo4j unavailable — skipping node upsert for %s:%s", node_type, label)
        return None

    try:
        neo_label = node_type.capitalize()
        node = Node(neo_label, label=label, risk_score=risk_score, **(metadata or {}))
        graph.merge(node, neo_label, "label")
        logger.debug("Upserted %s node: %s (risk=%.2f)", neo_label, label, risk_score)
        return str(node.identity)
    except Exception as exc:
        logger.error("Neo4j upsert error for %s:%s — %s", node_type, label, exc)
        return None


def create_relationship(
    from_label: str,
    from_type: str,
    rel_type: str,
    to_label: str,
    to_type: str,
    properties: dict[str, Any] | None = None,
) -> bool:
    """
    Create a directed relationship between two existing nodes.

    Args:
        from_label: Label property value of the source node.
        from_type:  Node type of the source.
        rel_type:   Relationship type string e.g. "SENT", "TARGETS".
        to_label:   Label property value of the target node.
        to_type:    Node type of the target.
        properties: Optional properties on the relationship.

    Returns:
        True on success, False on failure or unavailability.
    """
    graph = _get_graph()
    if graph is None:
        return False

    try:
        from_node = graph.nodes.match(from_type.capitalize(), label=from_label).first()
        to_node = graph.nodes.match(to_type.capitalize(), label=to_label).first()
        if from_node is None or to_node is None:
            logger.warning(
                "Relationship skipped — node not found: %s(%s) or %s(%s)",
                from_type, from_label, to_type, to_label,
            )
            return False
        rel = Relationship(from_node, rel_type, to_node, **(properties or {}))
        graph.merge(rel)
        logger.debug("Created %s -[%s]-> %s", from_label, rel_type, to_label)
        return True
    except Exception as exc:
        logger.error("Neo4j relationship error: %s", exc)
        return False


def query_high_risk_nodes(threshold: float = 0.7, limit: int = 50) -> list[dict]:
    """
    Return all nodes with risk_score >= threshold, ordered descending.

    Args:
        threshold: Minimum risk score [0.0, 1.0].
        limit:     Maximum number of results.

    Returns:
        List of dicts, each representing one node's properties.
        Empty list if Neo4j is offline.
    """
    graph = _get_graph()
    if graph is None:
        return []

    try:
        cursor = graph.run(
            "MATCH (n) WHERE n.risk_score >= $threshold "
            "RETURN n ORDER BY n.risk_score DESC LIMIT $limit",
            threshold=threshold,
            limit=limit,
        )
        return [dict(record["n"]) for record in cursor]
    except Exception as exc:
        logger.error("Neo4j query error: %s", exc)
        return []


def write_scan_result_to_graph(
    session_id: str,
    entity_label: str,
    entity_type: str,
    risk_score: float,
    rel_type: str = "FLAGGED_BY",
) -> None:
    """
    Convenience function: upsert entity node → upsert session node
    → create FLAGGED_BY relationship.

    Used by Celery tasks after AI verdict is received.
    """
    upsert_threat_node(entity_type, entity_label, risk_score)
    upsert_threat_node("session", session_id, risk_score)
    create_relationship(
        from_label=entity_label,
        from_type=entity_type,
        rel_type=rel_type,
        to_label=session_id,
        to_type="session",
    )
