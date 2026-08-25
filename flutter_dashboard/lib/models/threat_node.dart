/// Data model for a Neo4j threat graph node.
class ThreatNode {
  final int id;
  final String neo4jId;
  final String nodeType;
  final String label;
  final double riskScore;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;

  const ThreatNode({
    required this.id,
    required this.neo4jId,
    required this.nodeType,
    required this.label,
    required this.riskScore,
    required this.metadata,
    required this.createdAt,
  });

  factory ThreatNode.fromJson(Map<String, dynamic> j) => ThreatNode(
        id: j['id'] as int,
        neo4jId: j['neo4j_id'] as String,
        nodeType: j['node_type'] as String,
        label: j['label'] as String,
        riskScore: (j['risk_score'] as num).toDouble(),
        metadata: Map<String, dynamic>.from(j['metadata'] as Map? ?? {}),
        createdAt: DateTime.parse(j['created_at'] as String),
      );
}
