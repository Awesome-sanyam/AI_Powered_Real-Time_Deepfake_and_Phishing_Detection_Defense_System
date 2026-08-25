import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../providers/threat_graph_provider.dart';
import 'widgets/neo4j_graph_view.dart';

/// Threat graph screen — visualises Neo4j entities and relationships.
class GraphScreen extends ConsumerWidget {
  const GraphScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final nodes = ref.watch(threatNodesProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _header(context),
            const SizedBox(height: 24),
            Expanded(
              child: nodes.when(
                data: (list) => Neo4jGraphView(nodes: list),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.cloud_off, color: AppColors.accentRed, size: 48),
                      const SizedBox(height: 16),
                      Text('Neo4j offline or no data',
                          style: TextStyle(color: AppColors.textSecondary)),
                      const SizedBox(height: 8),
                      Text('$e',
                          style: TextStyle(color: AppColors.accentRed, fontSize: 12)),
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _header(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Threat Graph', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 24)),
          const SizedBox(height: 4),
          Text('Neo4j entity-relationship map of attack campaigns',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
        ],
      );
}
