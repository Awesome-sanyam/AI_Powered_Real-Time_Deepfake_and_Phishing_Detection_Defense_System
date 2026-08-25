import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/deepfake_result.dart';

final deepfakeSessionsProvider = FutureProvider<List<DeepfakeResult>>((ref) async {
  final raw = await ApiClient.instance.fetchDeepfakeSessions();
  return raw.map(DeepfakeResult.fromJson).toList();
});

final selectedDeepfakeSessionProvider = FutureProvider.family<DeepfakeResult, String>(
  (ref, sessionId) async {
    final raw = await ApiClient.instance.fetchDeepfakeSession(sessionId);
    return DeepfakeResult.fromJson(raw);
  },
);
