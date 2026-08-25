import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../providers/deepfake_provider.dart';
import '../../providers/phishing_provider.dart';
import 'widgets/threat_summary_card.dart';
import 'widgets/live_alert_feed.dart';

/// Main SOC dashboard — shows threat summary stats + live alert feed.
class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final deepfakeSessions = ref.watch(deepfakeSessionsProvider);
    final phishingScans = ref.watch(phishingScansProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _header(context),
            const SizedBox(height: 24),
            // Summary cards row
            Row(
              children: [
                Expanded(
                  child: ThreatSummaryCard(
                    title: 'Deepfake Scans',
                    icon: Icons.videocam,
                    color: AppColors.accentRed,
                    value: deepfakeSessions.when(
                      data: (d) => d.length.toString(),
                      loading: () => '—',
                      error: (_, __) => 'Err',
                    ),
                    subtitle: deepfakeSessions.when(
                      data: (d) {
                        final fakes = d.where((s) => s.isDeepfake == true).length;
                        return '$fakes detected as fake';
                      },
                      loading: () => 'Loading…',
                      error: (_, __) => 'Backend offline',
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: ThreatSummaryCard(
                    title: 'Phishing Scans',
                    icon: Icons.phishing,
                    color: AppColors.accentYellow,
                    value: phishingScans.when(
                      data: (d) => d.length.toString(),
                      loading: () => '—',
                      error: (_, __) => 'Err',
                    ),
                    subtitle: phishingScans.when(
                      data: (d) {
                        final threats = d.where((s) => s.isPhishing == true).length;
                        return '$threats phishing detected';
                      },
                      loading: () => 'Loading…',
                      error: (_, __) => 'Backend offline',
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: ThreatSummaryCard(
                    title: 'System Status',
                    icon: Icons.check_circle,
                    color: AppColors.accentGreen,
                    value: 'ONLINE',
                    subtitle: 'All services active',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            // Live alert feed
            const Expanded(child: LiveAlertFeed()),
          ],
        ),
      ),
    );
  }

  Widget _header(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('SOC Dashboard',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 28)),
            const SizedBox(height: 4),
            Text('Real-time GenAI threat monitoring',
                style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.accentGreen.withOpacity(0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.accentGreen.withOpacity(0.4)),
          ),
          child: Row(
            children: [
              Container(width: 8, height: 8,
                  decoration: BoxDecoration(color: AppColors.accentGreen, shape: BoxShape.circle)),
              const SizedBox(width: 8),
              Text('LIVE', style: TextStyle(color: AppColors.accentGreen,
                  fontWeight: FontWeight.bold, fontSize: 12)),
            ],
          ),
        ),
      ],
    );
  }
}
