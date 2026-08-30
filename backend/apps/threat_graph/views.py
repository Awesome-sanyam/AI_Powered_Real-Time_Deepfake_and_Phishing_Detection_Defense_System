"""Threat graph views."""
from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ThreatNode
from .serializers import ThreatNodeSerializer
from .graph_client import health_check, query_high_risk_nodes, _get_graph

logger = logging.getLogger(__name__)


# ── HTML View ──────────────────────────────────────────────────────────────────

@method_decorator(login_required, name="dispatch")
class ThreatGraphPageView(View):
    """GET /threat-graph/view/ — Interactive Vis.js threat graph page."""

    template_name = "threat_graph/view.html"

    def get(self, request):
        # Quick node count from Neo4j (best-effort — falls back to 0)
        node_count = 0
        edge_count = 0
        graph = _get_graph()
        if graph is not None:
            try:
                node_count = graph.evaluate("MATCH (n) RETURN count(n)") or 0
                edge_count = graph.evaluate("MATCH ()-[r]->() RETURN count(r)") or 0
            except Exception as exc:
                logger.warning("ThreatGraphPageView Neo4j count error: %s", exc)

        high_risk_nodes = ThreatNode.objects.filter(risk_score__gte=0.7).count()

        return render(request, self.template_name, {
            "node_count":      node_count,
            "edge_count":      edge_count,
            "high_risk_nodes": high_risk_nodes,
        })




class ThreatNodeListView(generics.ListAPIView):
    """GET /api/graph/nodes/ — list all threat nodes ordered by risk."""
    queryset = ThreatNode.objects.all()
    serializer_class = ThreatNodeSerializer


class HighRiskNodesView(APIView):
    """GET /api/graph/high-risk/?threshold=0.7 — live query from Neo4j."""

    def get(self, request):
        threshold = float(request.query_params.get("threshold", 0.7))
        nodes = query_high_risk_nodes(threshold=threshold)
        return Response({"count": len(nodes), "nodes": nodes})


class GraphHealthView(APIView):
    """
    GET /api/graph/health/ — Neo4j connectivity health check.

    Returns:
        {"status": "ok"|"offline", "uri": str, "version": str|null, "error": str|null}
    """

    def get(self, request):
        status = health_check()
        http_status = 200 if status["status"] == "ok" else 503
        return Response(status, status=http_status)


class GraphDataView(APIView):
    """
    GET /api/graph/data/ — Returns Vis.js-compatible graph data from Neo4j.

    Query params:
        limit (int): max nodes/edges to return (default 200)

    Response:
        {
            "node_count": int,
            "edge_count":  int,
            "nodes": [{"id", "label", "node_type", "risk_score", "signals"}, ...],
            "edges": [{"id", "from", "to", "type"}, ...]
        }

    Gracefully returns empty graph when Neo4j is offline.
    """

    def get(self, request):
        limit = int(request.query_params.get("limit", 200))
        graph = _get_graph()
        nodes, edges = [], []

        if graph is not None:
            try:
                # Fetch all nodes
                node_cursor = graph.run(
                    "MATCH (n) RETURN id(n) AS nid, labels(n) AS labels, "
                    "n.label AS label, n.risk_score AS risk_score, "
                    "n.signals AS signals "
                    "LIMIT $limit",
                    limit=limit,
                )
                for rec in node_cursor:
                    node_type = (rec["labels"][0] if rec["labels"] else "Unknown").lower()
                    nodes.append({
                        "id":         rec["nid"],
                        "label":      rec["label"] or str(rec["nid"]),
                        "node_type":  node_type,
                        "risk_score": rec["risk_score"] or 0.0,
                        "signals":    rec["signals"] or "",
                    })

                # Fetch all relationships
                rel_cursor = graph.run(
                    "MATCH (a)-[r]->(b) RETURN id(r) AS rid, id(a) AS from_id, "
                    "id(b) AS to_id, type(r) AS rel_type "
                    "LIMIT $limit",
                    limit=limit,
                )
                for rec in rel_cursor:
                    edges.append({
                        "id":   rec["rid"],
                        "from": rec["from_id"],
                        "to":   rec["to_id"],
                        "type": rec["rel_type"],
                    })
            except Exception as exc:
                logger.warning("GraphDataView Neo4j error: %s", exc)

        return Response({
            "node_count": len(nodes),
            "edge_count":  len(edges),
            "nodes":       nodes,
            "edges":       edges,
        })
