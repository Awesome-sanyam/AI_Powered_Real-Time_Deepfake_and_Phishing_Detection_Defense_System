/// Data model for a phishing scan report.
class PhishingReport {
  final int id;
  final String sessionId;
  final bool? isPhishing;
  final double? confidence;
  final String riskLevel;
  final List<String> signals;
  final String explanation;
  final String url;
  final String signedVerdict;
  final DateTime createdAt;

  const PhishingReport({
    required this.id,
    required this.sessionId,
    required this.isPhishing,
    required this.confidence,
    required this.riskLevel,
    required this.signals,
    required this.explanation,
    required this.url,
    required this.signedVerdict,
    required this.createdAt,
  });

  factory PhishingReport.fromJson(Map<String, dynamic> j) => PhishingReport(
        id: j['id'] as int,
        sessionId: j['session_id'] as String,
        isPhishing: j['is_phishing'] as bool?,
        confidence: (j['confidence'] as num?)?.toDouble(),
        riskLevel: j['risk_level'] as String? ?? '',
        signals: List<String>.from(j['signals'] as List? ?? []),
        explanation: j['explanation'] as String? ?? '',
        url: j['url'] as String? ?? '',
        signedVerdict: j['signed_verdict'] as String? ?? '',
        createdAt: DateTime.parse(j['created_at'] as String),
      );
}
