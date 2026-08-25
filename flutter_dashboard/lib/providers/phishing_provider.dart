import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/api_client.dart';
import '../models/phishing_report.dart';

final phishingScansProvider = FutureProvider<List<PhishingReport>>((ref) async {
  final raw = await ApiClient.instance.fetchPhishingScans();
  return raw.map(PhishingReport.fromJson).toList();
});
