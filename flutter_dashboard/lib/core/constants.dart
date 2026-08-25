import 'package:flutter/material.dart';

/// App-wide constants — URLs, colours, thresholds.
abstract class AppConstants {
  static const String backendBaseUrl = 'http://localhost:8000';
  static const String aiEngineBaseUrl = 'http://localhost:8001';
  static const String wsDeepfakeUrl = 'ws://localhost:8000/ws/deepfake/';
  static const String wsAlertsUrl = 'ws://localhost:8000/ws/alerts/';

  // Detection thresholds (match backend defaults)
  static const double deepfakeThreshold = 0.55;
  static const double phishingHighRisk = 0.7;
  static const double phishingMediumRisk = 0.4;
}

/// Centralised colour palette — dark SOC aesthetic.
abstract class AppColors {
  static const Color background = Color(0xFF0D1117);
  static const Color surface = Color(0xFF161B22);
  static const Color surfaceVariant = Color(0xFF1C2128);
  static const Color accent = Color(0xFF58A6FF);         // blue
  static const Color accentGreen = Color(0xFF3FB950);    // safe/real
  static const Color accentRed = Color(0xFFF85149);      // threat/fake
  static const Color accentYellow = Color(0xFFD29922);   // warning
  static const Color accentPurple = Color(0xFFBC8CFF);   // identity/ECDSA
  static const Color textPrimary = Color(0xFFE6EDF3);
  static const Color textSecondary = Color(0xFF8B949E);
  static const Color border = Color(0xFF30363D);
}

/// Risk level enum with associated colour and label.
enum RiskLevel { low, medium, high, critical }

extension RiskLevelX on RiskLevel {
  Color get color => switch (this) {
        RiskLevel.low => AppColors.accentGreen,
        RiskLevel.medium => AppColors.accentYellow,
        RiskLevel.high => AppColors.accentRed,
        RiskLevel.critical => const Color(0xFFFF0000),
      };

  String get label => switch (this) {
        RiskLevel.low => 'LOW',
        RiskLevel.medium => 'MEDIUM',
        RiskLevel.high => 'HIGH',
        RiskLevel.critical => 'CRITICAL',
      };

  static RiskLevel fromScore(double score) {
    if (score < 0.3) return RiskLevel.low;
    if (score < 0.6) return RiskLevel.medium;
    if (score < 0.85) return RiskLevel.high;
    return RiskLevel.critical;
  }
}
