import 'package:dio/dio.dart';
import 'constants.dart';

/// Singleton Dio REST client pre-configured for the Django backend.
class ApiClient {
  ApiClient._();
  static final ApiClient instance = ApiClient._();

  late final Dio _dio = Dio(
    BaseOptions(
      baseUrl: AppConstants.backendBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
    ),
  )..interceptors.add(_LogInterceptor());

  // ── Deepfake API ───────────────────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> fetchDeepfakeSessions() async {
    final res = await _dio.get('/api/deepfake/sessions/');
    return List<Map<String, dynamic>>.from(res.data as List);
  }

  Future<Map<String, dynamic>> fetchDeepfakeSession(String sessionId) async {
    final res = await _dio.get('/api/deepfake/sessions/$sessionId/');
    return res.data as Map<String, dynamic>;
  }

  // ── Phishing API ──────────────────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> fetchPhishingScans() async {
    final res = await _dio.get('/api/phishing/scans/');
    return List<Map<String, dynamic>>.from(res.data as List);
  }

  Future<Map<String, dynamic>> submitPhishingScan({
    required String content,
    String? url,
  }) async {
    final res = await _dio.post('/api/phishing/scans/', data: {
      'content': content,
      if (url != null) 'url': url,
    });
    return res.data as Map<String, dynamic>;
  }

  // ── Threat Graph API ──────────────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> fetchThreatNodes() async {
    final res = await _dio.get('/api/graph/nodes/');
    return List<Map<String, dynamic>>.from(res.data as List);
  }

  Future<Map<String, dynamic>> fetchHighRiskNodes({double threshold = 0.7}) async {
    final res = await _dio.get(
      '/api/graph/high-risk/',
      queryParameters: {'threshold': threshold},
    );
    return res.data as Map<String, dynamic>;
  }

  // ── Identity API ──────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> fetchMyIdentityKey() async {
    final res = await _dio.get('/api/identity/me/');
    return res.data as Map<String, dynamic>;
  }
}

class _LogInterceptor extends Interceptor {
  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    // Silently pass errors through — UI handles them
    handler.next(err);
  }
}
