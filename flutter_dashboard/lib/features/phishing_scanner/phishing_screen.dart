import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/constants.dart';
import '../../providers/phishing_provider.dart';
import 'widgets/scan_result_card.dart';

/// Phishing scanner screen — paste email/URL and trigger scan.
class PhishingScreen extends ConsumerStatefulWidget {
  const PhishingScreen({super.key});

  @override
  ConsumerState<PhishingScreen> createState() => _PhishingScreenState();
}

class _PhishingScreenState extends ConsumerState<PhishingScreen> {
  final _controller = TextEditingController();
  final _urlController = TextEditingController();
  bool _isScanning = false;

  @override
  void dispose() {
    _controller.dispose();
    _urlController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scans = ref.watch(phishingScansProvider);

    return Scaffold(
      backgroundColor: AppColors.background,
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Row(
          children: [
            // Input panel (left 45%)
            Expanded(
              flex: 45,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Phishing Scanner',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 24)),
                  const SizedBox(height: 4),
                  Text('Paste email content or suspicious URL for LLM + heuristic analysis',
                      style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                  const SizedBox(height: 24),
                  _inputField('Suspicious URL', _urlController, Icons.link, maxLines: 1),
                  const SizedBox(height: 12),
                  Expanded(child: _inputField('Email Content / Message Body',
                      _controller, Icons.email, maxLines: null)),
                  const SizedBox(height: 16),
                  _scanButton(),
                ],
              ),
            ),
            const SizedBox(width: 24),
            // Results panel (right 55%)
            Expanded(
              flex: 55,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Scan Results',
                      style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  Expanded(
                    child: scans.when(
                      data: (list) => list.isEmpty
                          ? Center(child: Text('No scans yet',
                              style: TextStyle(color: AppColors.textSecondary)))
                          : ListView.separated(
                              itemCount: list.length,
                              separatorBuilder: (_, __) => const SizedBox(height: 12),
                              itemBuilder: (_, i) => ScanResultCard(report: list[i]),
                            ),
                      loading: () => const Center(child: CircularProgressIndicator()),
                      error: (e, _) => Text('$e',
                          style: TextStyle(color: AppColors.accentRed)),
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

  Widget _inputField(String hint, TextEditingController ctrl, IconData icon,
      {int? maxLines}) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.border),
      ),
      child: TextField(
        controller: ctrl,
        maxLines: maxLines,
        style: const TextStyle(color: Colors.white, fontSize: 14),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: TextStyle(color: AppColors.textSecondary),
          prefixIcon: Icon(icon, color: AppColors.textSecondary, size: 18),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.all(16),
        ),
      ),
    );
  }

  Widget _scanButton() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: _isScanning ? null : _scan,
        icon: _isScanning
            ? const SizedBox(width: 16, height: 16,
                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
            : const Icon(Icons.search),
        label: Text(_isScanning ? 'Analysing…' : 'Analyse Threat'),
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
      ),
    );
  }

  Future<void> _scan() async {
    if (_controller.text.trim().isEmpty && _urlController.text.trim().isEmpty) return;
    setState(() => _isScanning = true);
    try {
      // Trigger async scan — result will appear in phishingScansProvider
      ref.invalidate(phishingScansProvider);
    } finally {
      setState(() => _isScanning = false);
    }
  }
}
