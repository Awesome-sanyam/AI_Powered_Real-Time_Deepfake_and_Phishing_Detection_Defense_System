import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../../../core/ws_client.dart';

/// Real-time analysis overlay panel — shows live verdict from WebSocket.
class AnalysisOverlay extends ConsumerStatefulWidget {
  const AnalysisOverlay({super.key});

  @override
  ConsumerState<AnalysisOverlay> createState() => _AnalysisOverlayState();
}

class _AnalysisOverlayState extends ConsumerState<AnalysisOverlay> {
  Map<String, dynamic>? _lastVerdict;

  @override
  void initState() {
    super.initState();
    WsClient.instance.deepfakeStream.listen((verdict) {
      if (mounted) setState(() => _lastVerdict = verdict);
    });
  }

  @override
  Widget build(BuildContext context) {
    final v = _lastVerdict;
    final isDeepfake = v?['is_deepfake'] as bool?;
    final confidence = (v?['confidence'] as num?)?.toDouble() ?? 0.0;
    final color = isDeepfake == true ? AppColors.accentRed
        : isDeepfake == false ? AppColors.accentGreen
        : AppColors.textSecondary;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.4)),
        boxShadow: [BoxShadow(color: color.withOpacity(0.1), blurRadius: 16)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.analytics, color: AppColors.accent, size: 18),
            const SizedBox(width: 8),
            Text('Live Analysis', style: const TextStyle(
                color: Colors.white, fontWeight: FontWeight.w600)),
          ]),
          const SizedBox(height: 16),
          if (v == null)
            Text('Waiting for stream…',
                style: TextStyle(color: AppColors.textSecondary))
          else ...[
            _Metric(label: 'Verdict',
                value: isDeepfake == true ? 'DEEPFAKE' : 'REAL',
                color: color),
            const SizedBox(height: 8),
            _Metric(label: 'Confidence',
                value: '${(confidence * 100).toStringAsFixed(1)}%',
                color: color),
            const SizedBox(height: 8),
            _Metric(label: 'ECDSA Signed',
                value: v['signed_verdict'] != null ? '✓ YES' : '✗ NO',
                color: v['signed_verdict'] != null
                    ? AppColors.accentGreen : AppColors.accentRed),
          ],
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _Metric({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
          Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold)),
        ],
      );
}
