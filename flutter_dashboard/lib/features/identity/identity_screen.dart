import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import '../../core/constants.dart';
import 'widgets/key_vault_card.dart';

/// Identity vault screen — shows user's ECDSA public key and status.
class IdentityScreen extends ConsumerWidget {
  const IdentityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final keyFuture = ref.watch(_myKeyProvider);

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
              child: keyFuture.when(
                data: (data) => KeyVaultCard(keyData: data),
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (e, _) => Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.lock_open, color: AppColors.textSecondary, size: 56),
                      const SizedBox(height: 16),
                      Text('No identity key registered',
                          style: TextStyle(color: AppColors.textSecondary)),
                      const SizedBox(height: 8),
                      Text('Login and register your ECDSA key first',
                          style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
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
          Text('Identity Vault', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontSize: 24)),
          const SizedBox(height: 4),
          Text('ECDSA cryptographic identity — tamper-proof verdict signatures',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
        ],
      );
}

// Local provider for identity key
final _myKeyProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  return ApiClient.instance.fetchMyIdentityKey();
});
