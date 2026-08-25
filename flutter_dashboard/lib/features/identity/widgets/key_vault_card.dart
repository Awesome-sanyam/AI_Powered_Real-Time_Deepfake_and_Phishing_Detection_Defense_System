import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../../core/constants.dart';

/// ECDSA key vault card — shows public key, fingerprint, and status.
class KeyVaultCard extends StatelessWidget {
  final Map<String, dynamic> keyData;
  const KeyVaultCard({super.key, required this.keyData});

  @override
  Widget build(BuildContext context) {
    final isRevoked = keyData['is_revoked'] as bool? ?? false;
    final fingerprint = keyData['fingerprint'] as String? ?? '';
    final publicKey = keyData['public_key_pem'] as String? ?? '';
    final username = keyData['username'] as String? ?? '—';
    final status = isRevoked ? 'REVOKED' : 'ACTIVE';
    final statusColor = isRevoked ? AppColors.accentRed : AppColors.accentGreen;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.accentPurple.withOpacity(0.4)),
        boxShadow: [BoxShadow(color: AppColors.accentPurple.withOpacity(0.1), blurRadius: 24)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.accentPurple.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.security, color: AppColors.accentPurple, size: 28),
            ),
            const SizedBox(width: 16),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(username, style: const TextStyle(color: Colors.white,
                  fontSize: 20, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(status, style: TextStyle(color: statusColor,
                    fontWeight: FontWeight.bold, fontSize: 12)),
              ),
            ]),
          ]),
          const SizedBox(height: 24),
          // Fingerprint
          _KeyField(label: 'Key Fingerprint (SHA-256)',
              value: _formatFingerprint(fingerprint),
              mono: true),
          const SizedBox(height: 16),
          // Public key PEM
          Expanded(
            child: _PemBox(pem: publicKey),
          ),
          const SizedBox(height: 16),
          // Copy button
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: publicKey));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Public key copied to clipboard')),
                );
              },
              icon: const Icon(Icons.copy, size: 16),
              label: const Text('Copy Public Key'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.accentPurple,
                side: BorderSide(color: AppColors.accentPurple.withOpacity(0.5)),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatFingerprint(String fp) {
    if (fp.length < 32) return fp;
    return fp.replaceAllMapped(RegExp(r'.{2}'), (m) => '${m.group(0)}:')
        .replaceAll(RegExp(r':$'), '');
  }
}

class _KeyField extends StatelessWidget {
  final String label;
  final String value;
  final bool mono;
  const _KeyField({required this.label, required this.value, this.mono = false});

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          const SizedBox(height: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: AppColors.surfaceVariant,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.border),
            ),
            child: Text(value, style: TextStyle(
                color: AppColors.accentPurple,
                fontFamily: mono ? 'monospace' : null, fontSize: 12)),
          ),
        ],
      );
}

class _PemBox extends StatelessWidget {
  final String pem;
  const _PemBox({required this.pem});

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Public Key (PEM)',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          const SizedBox(height: 6),
          Expanded(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF0A0E13),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.border),
              ),
              child: SingleChildScrollView(
                child: Text(
                  pem.isEmpty ? '— No key registered —' : pem,
                  style: const TextStyle(
                      color: Color(0xFF58A6FF), fontFamily: 'monospace', fontSize: 11),
                ),
              ),
            ),
          ),
        ],
      );
}
