import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'constants.dart';

/// WebSocket client for real-time alert and verdict streaming.
class WsClient {
  WsClient._();
  static final WsClient instance = WsClient._();

  WebSocketChannel? _alertChannel;
  WebSocketChannel? _deepfakeChannel;

  final _alertController = StreamController<Map<String, dynamic>>.broadcast();
  final _deepfakeController = StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get alertStream => _alertController.stream;
  Stream<Map<String, dynamic>> get deepfakeStream => _deepfakeController.stream;

  // ── Alert Feed ────────────────────────────────────────────────────────────

  void connectAlerts() {
    _alertChannel?.sink.close();
    _alertChannel = WebSocketChannel.connect(Uri.parse(AppConstants.wsAlertsUrl));
    _alertChannel!.stream.listen(
      (data) {
        try {
          final msg = json.decode(data as String) as Map<String, dynamic>;
          _alertController.add(msg);
        } catch (_) {}
      },
      onError: (_) {},
      cancelOnError: false,
    );
  }

  // ── Deepfake Frame Streaming ──────────────────────────────────────────────

  void connectDeepfake(String sessionId) {
    _deepfakeChannel?.sink.close();
    final url = '${AppConstants.wsDeepfakeUrl}$sessionId/';
    _deepfakeChannel = WebSocketChannel.connect(Uri.parse(url));
    _deepfakeChannel!.stream.listen(
      (data) {
        try {
          final msg = json.decode(data as String) as Map<String, dynamic>;
          _deepfakeController.add(msg);
        } catch (_) {}
      },
      onError: (_) {},
      cancelOnError: false,
    );
  }

  /// Send a JPEG frame as binary over the deepfake WebSocket.
  void sendFrame(List<int> jpegBytes) {
    _deepfakeChannel?.sink.add(jpegBytes);
  }

  void disconnectDeepfake() => _deepfakeChannel?.sink.close();
  void disconnectAlerts() => _alertChannel?.sink.close();

  void dispose() {
    _alertChannel?.sink.close();
    _deepfakeChannel?.sink.close();
    _alertController.close();
    _deepfakeController.close();
  }
}
