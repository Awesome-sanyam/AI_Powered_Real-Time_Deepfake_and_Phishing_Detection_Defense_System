import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/threat_node.dart';

final threatNodesProvider = FutureProvider<List<ThreatNode>>((ref) async {
  final raw = await ApiClient.instance.fetchThreatNodes();
  return raw.map(ThreatNode.fromJson).toList();
});

final highRiskNodesProvider = FutureProvider.family<List<ThreatNode>, double>(
  (ref, threshold) async {
    final res = await ApiClient.instance.fetchHighRiskNodes(threshold: threshold);
    final nodes = res['nodes'] as List? ?? [];
    return nodes.map((n) => ThreatNode.fromJson(n as Map<String, dynamic>)).toList();
  },
);
