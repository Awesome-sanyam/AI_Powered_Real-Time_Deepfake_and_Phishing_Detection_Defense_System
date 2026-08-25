import 'package:flutter/material.dart';
import '../../../core/constants.dart';
import '../../../models/phishing_report.dart';

/// Card displaying a single phishing scan result with risk level + signals.
class ScanResultCard extends StatelessWidget {
  final PhishingReport report;
  const ScanResultCard({super.key, required this.report});

  @override
  Widget build(BuildContext context) {
    final risk = RiskLevelX.fromScore(report.confidence ?? 0);
    final color = risk.color;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.35)),
        boxShadow: [BoxShadow(color: color.withOpacity(0.07), blurRadius: 12)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: color.withOpacity(0.15),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(risk.label,
                  style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                report.url.isNotEmpty ? report.url : 'Email content scan',
                style: const TextStyle(color: Colors.white, fontSize: 13),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            if (report.signedVerdict.isNotEmpty)
              Tooltip(
                message: 'ECDSA signed verdict',
                child: Icon(Icons.verified_user, color: AppColors.accentPurple, size: 16),
              ),
          ]),
          const SizedBox(height: 10),
          // Confidence bar
          Row(children: [
            Text('Confidence:', style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
            const SizedBox(width: 8),
            Expanded(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: report.confidence ?? 0,
                  backgroundColor: AppColors.border,
                  color: color,
                  minHeight: 6,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text('${((report.confidence ?? 0) * 100).toStringAsFixed(0)}%',
                style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12)),
          ]),
          if (report.signals.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6, runSpacing: 6,
              children: report.signals.map((s) => Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.surfaceVariant,
                  borderRadius: BorderRadius.circular(5),
                  border: Border.all(color: AppColors.border),
                ),
                child: Text(s, style: TextStyle(
                    color: AppColors.textSecondary, fontSize: 11)),
              )).toList(),
            ),
          ],
          if (report.explanation.isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(report.explanation,
                style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                maxLines: 2, overflow: TextOverflow.ellipsis),
          ],
        ],
      ),
    );
  }
}
