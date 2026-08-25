import 'package:flutter/material.dart';
import '../../../core/constants.dart';
import '../../../models/threat_node.dart';

/// Interactive threat graph visualisation backed by Neo4j data.
/// Renders nodes as positioned circles with risk-coded colours.
class Neo4jGraphView extends StatelessWidget {
  final List<ThreatNode> nodes;
  const Neo4jGraphView({super.key, required this.nodes});

  @override
  Widget build(BuildContext context) {
    if (nodes.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.hub, color: AppColors.textSecondary, size: 56),
            const SizedBox(height: 16),
            Text('No threat entities yet', style: TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 8),
            Text('Entities appear here as scans run',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
          ],
        ),
      );
    }

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          // Legend
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                const Icon(Icons.hub, color: AppColors.accent, size: 18),
                const SizedBox(width: 8),
                Text('${nodes.length} entities', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                const Spacer(),
                ...[
                  ('IP', AppColors.accentRed), ('Domain', AppColors.accentYellow),
                  ('Email', AppColors.accent), ('Session', AppColors.accentPurple),
                ].map((t) => Padding(
                  padding: const EdgeInsets.only(left: 12),
                  child: Row(children: [
                    Container(width: 10, height: 10,
                        decoration: BoxDecoration(color: t.$2, shape: BoxShape.circle)),
                    const SizedBox(width: 4),
                    Text(t.$1, style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                  ]),
                )),
              ],
            ),
          ),
          const Divider(color: AppColors.border, height: 1),
          // Node list (simplified table view — full graph widget requires custom painter)
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: nodes.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (_, i) => _NodeTile(node: nodes[i]),
            ),
          ),
        ],
      ),
    );
  }
}

class _NodeTile extends StatelessWidget {
  final ThreatNode node;
  const _NodeTile({required this.node});

  Color _colorForType(String type) => switch (type) {
        'ip' => AppColors.accentRed,
        'domain' => AppColors.accentYellow,
        'email' => AppColors.accent,
        'session' => AppColors.accentPurple,
        _ => AppColors.textSecondary,
      };

  @override
  Widget build(BuildContext context) {
    final color = _colorForType(node.nodeType);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.07),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          Container(width: 10, height: 10,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
          const SizedBox(width: 12),
          Expanded(
            child: Text(node.label,
                style: const TextStyle(color: Colors.white, fontSize: 14)),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: AppColors.surfaceVariant,
              borderRadius: BorderRadius.circular(5),
            ),
            child: Text(node.nodeType.toUpperCase(),
                style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(width: 10),
          Text('${(node.riskScore * 100).toStringAsFixed(0)}%',
              style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 13)),
        ],
      ),
    );
  }
}
