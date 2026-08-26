"""Threat graph views."""
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ThreatNode
from .serializers import ThreatNodeSerializer
from .graph_client import health_check, query_high_risk_nodes


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
