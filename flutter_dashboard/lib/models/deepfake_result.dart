/// Data model for a deepfake scan result.
class DeepfakeResult {
  final String sessionId;
  final bool? isDeepfake;
  final double? confidence;
  final int frameCount;
  final double? processingTimeMs;
  final String signedVerdict;
  final String publicKeyPem;
  final DateTime createdAt;

  const DeepfakeResult({
    required this.sessionId,
    required this.isDeepfake,
    required this.confidence,
    required this.frameCount,
    required this.processingTimeMs,
    required this.signedVerdict,
    required this.publicKeyPem,
    required this.createdAt,
  });

  factory DeepfakeResult.fromJson(Map<String, dynamic> j) => DeepfakeResult(
        sessionId: j['session_id'] as String,
        isDeepfake: j['is_deepfake'] as bool?,
        confidence: (j['confidence'] as num?)?.toDouble(),
        frameCount: (j['frame_count'] as int?) ?? 0,
        processingTimeMs: (j['processing_time_ms'] as num?)?.toDouble(),
        signedVerdict: j['signed_verdict'] as String? ?? '',
        publicKeyPem: j['public_key_pem'] as String? ?? '',
        createdAt: DateTime.parse(j['created_at'] as String),
      );

  bool get isSigned => signedVerdict.isNotEmpty;
}
