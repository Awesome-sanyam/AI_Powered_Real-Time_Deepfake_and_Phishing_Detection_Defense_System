import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../providers/deepfake_provider.dart';
import 'widgets/video_stream_view.dart';
import 'widgets/analysis_overlay.dart';

/// Deepfake live monitor screen — camera feed + real-time analysis overlay.
class DeepfakeScreen extends ConsumerWidget {
  const DeepfakeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessions = ref.watch(deepfakeSessionsProvider);

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
              child: Row(
                children: [
                  // Live camera + stream view (left 60%)
                  const Expanded(flex: 6, child: VideoStreamView()),
                  const SizedBox(width: 16),
                  // Analysis overlay panel (right 40%)
                  Expanded(
                    flex: 4,
                    child: Column(
                      children: [
                        const AnalysisOverlay(),
                        const SizedBox(height: 16),
                        Expanded(child: _sessionHistory(sessions)),
                      ],
                    ),
                  ),
                ],
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
          Text('Deepfake Monitor',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 24)),
          const SizedBox(height: 4),
          Text('Cross-modal video/audio analysis — MobileNetV2 · MediaPipe · Librosa',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
        ],
      );

  Widget _sessionHistory(AsyncValue sessions) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Scan History',
                style: const TextStyle(color: Colors.white,
                    fontWeight: FontWeight.w600, fontSize: 14)),
            const SizedBox(height: 12),
            Expanded(
              child: sessions.when(
                data: (data) {
                  final list = data as List;
                  if (list.isEmpty) {
                    return Center(child: Text('No scans yet',
                        style: TextStyle(color: AppColors.textSecondary)));
                  }
                  return ListView.separated(
                    itemCount: list.length,
                    separatorBuilder: (_, __) =>
                        Divider(color: AppColors.border, height: 1),
                    itemBuilder: (ctx, i) {
                      final s = list[i];
                      final isFake = s.isDeepfake;
                      return ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                          isFake == true ? Icons.warning_amber : Icons.check_circle,
                          color: isFake == true ? AppColors.accentRed : AppColors.accentGreen,
                          size: 18,
                        ),
                        title: Text(s.sessionId.substring(0, 8),
                            style: const TextStyle(color: Colors.white, fontSize: 13)),
                        subtitle: Text(
                          isFake == true
                              ? 'DEEPFAKE (${(s.confidence! * 100).toStringAsFixed(0)}%)'
                              : 'REAL',
                          style: TextStyle(
                            color: isFake == true ? AppColors.accentRed : AppColors.accentGreen,
                            fontSize: 11,
                          ),
                        ),
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Text('$e',
                    style: TextStyle(color: AppColors.accentRed)),
              ),
            ),
          ],
        ),
      );
}
