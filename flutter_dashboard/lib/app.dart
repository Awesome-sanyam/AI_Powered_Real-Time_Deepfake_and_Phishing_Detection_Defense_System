import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'core/constants.dart';
import 'features/dashboard/dashboard_screen.dart';
import 'features/deepfake_monitor/deepfake_screen.dart';
import 'features/phishing_scanner/phishing_screen.dart';
import 'features/threat_graph/graph_screen.dart';
import 'features/identity/identity_screen.dart';

/// Root application widget — defines theme, routing, and global scaffold.
class DefenceApp extends StatelessWidget {
  const DefenceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'AI Defence SOC Dashboard',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      routerConfig: _router,
    );
  }
}

// ── Router ────────────────────────────────────────────────────────────────────

final GoRouter _router = GoRouter(
  initialLocation: '/',
  routes: [
    ShellRoute(
      builder: (context, state, child) => _AppShell(child: child),
      routes: [
        GoRoute(path: '/', builder: (c, s) => const DashboardScreen()),
        GoRoute(path: '/deepfake', builder: (c, s) => const DeepfakeScreen()),
        GoRoute(path: '/phishing', builder: (c, s) => const PhishingScreen()),
        GoRoute(path: '/graph', builder: (c, s) => const GraphScreen()),
        GoRoute(path: '/identity', builder: (c, s) => const IdentityScreen()),
      ],
    ),
  ],
);

// ── App Shell (persistent side nav) ──────────────────────────────────────────

class _AppShell extends StatelessWidget {
  final Widget child;
  const _AppShell({required this.child});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Row(
        children: [
          _SideNav(),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _SideNav extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final location = GoRouterState.of(context).uri.toString();

    return Container(
      width: 220,
      color: AppColors.surface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 48),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Text(
              '🛡️ AI Defence',
              style: TextStyle(
                color: AppColors.accent,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                fontFamily: 'Inter',
              ),
            ),
          ),
          const SizedBox(height: 32),
          _NavItem(icon: Icons.dashboard, label: 'Dashboard', route: '/', currentRoute: location),
          _NavItem(icon: Icons.videocam, label: 'Deepfake Monitor', route: '/deepfake', currentRoute: location),
          _NavItem(icon: Icons.phishing, label: 'Phishing Scanner', route: '/phishing', currentRoute: location),
          _NavItem(icon: Icons.hub, label: 'Threat Graph', route: '/graph', currentRoute: location),
          _NavItem(icon: Icons.security, label: 'Identity Vault', route: '/identity', currentRoute: location),
        ],
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final String route;
  final String currentRoute;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.route,
    required this.currentRoute,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = currentRoute == route;
    return InkWell(
      onTap: () => context.go(route),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: isActive ? AppColors.accent.withOpacity(0.15) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: isActive ? Border.all(color: AppColors.accent.withOpacity(0.4)) : null,
        ),
        child: Row(
          children: [
            Icon(icon, color: isActive ? AppColors.accent : AppColors.textSecondary, size: 20),
            const SizedBox(width: 12),
            Text(
              label,
              style: TextStyle(
                color: isActive ? AppColors.accent : AppColors.textSecondary,
                fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                fontFamily: 'Inter',
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Theme ─────────────────────────────────────────────────────────────────────

ThemeData _buildTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.dark(
      primary: AppColors.accent,
      surface: AppColors.surface,
      background: AppColors.background,
    ),
    fontFamily: 'Inter',
    scaffoldBackgroundColor: AppColors.background,
    cardTheme: CardTheme(
      color: AppColors.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    textTheme: const TextTheme(
      titleLarge: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
      titleMedium: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
      bodyMedium: TextStyle(color: Color(0xFFB0B8C1)),
    ),
  );
}
