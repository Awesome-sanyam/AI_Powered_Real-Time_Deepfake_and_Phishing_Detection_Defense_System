import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../../../core/constants.dart';
import '../../../core/ws_client.dart';

/// Live alert feed — subscribes to WebSocket alerts and renders them in a scrollable list.
class LiveAlertFeed extends StatefulWidget {
  const LiveAlertFeed({super.key});

  @override
  State<LiveAlertFeed> createState() => _LiveAlertFeedState();
}

class _LiveAlertFeedState extends State<LiveAlertFeed> {
  final List<Map<String, dynamic>> _alerts = [];
  late StreamSubscription<Map<String, dynamic>> _sub;
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WsClient.instance.connectAlerts();
    _sub = WsClient.instance.alertStream.listen((alert) {
      if (mounted) {
        setState(() => _alerts.insert(0, alert));
        // Cap list at 100 entries
        if (_alerts.length > 100) _alerts.removeLast();
      }
    });
  }

  @override
  void dispose() {
    _sub.cancel();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.bolt, color: AppColors.accentYellow, size: 18),
            const SizedBox(width: 8),
            Text('Live Alert Feed',
                style: Theme.of(context).textTheme.titleMedium),
            const Spacer(),
            Text('${_alerts.length} events',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
          ],
        ),
        const SizedBox(height: 12),
        Expanded(
          child: _alerts.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.wifi_off, color: AppColors.textSecondary, size: 40),
                      const SizedBox(height: 12),
                      Text('Waiting for alerts…',
                          style: TextStyle(color: AppColors.textSecondary)),
                    ],
                  ),
                )
              : ListView.separated(
                  controller: _scrollController,
                  itemCount: _alerts.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) => _AlertTile(alert: _alerts[i]),
                ),
        ),
      ],
    );
  }
}

class _AlertTile extends StatelessWidget {
  final Map<String, dynamic> alert;
  const _AlertTile({required this.alert});

  @override
  Widget build(BuildContext context) {
    final type = alert['type'] as String? ?? 'info';
    final color = switch (type) {
      'deepfake' => AppColors.accentRed,
      'phishing' => AppColors.accentYellow,
      'identity' => AppColors.accentPurple,
      _ => AppColors.accent,
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          Container(width: 4, height: 40,
              decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(alert['title'] as String? ?? 'Alert',
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                const SizedBox(height: 2),
                Text(alert['message'] as String? ?? '',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
              ],
            ),
          ),
          Text(alert['timestamp'] as String? ?? '',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 11)),
        ],
      ),
    );
  }
}
