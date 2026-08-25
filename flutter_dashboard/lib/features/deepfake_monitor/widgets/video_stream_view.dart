import 'package:flutter/material.dart';
import '../../../core/constants.dart';

/// Placeholder for the camera/video stream view.
/// In production: integrates `camera` package + WebSocket frame sender.
class VideoStreamView extends StatelessWidget {
  const VideoStreamView({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          children: [
            // Video feed placeholder
            Container(
              color: const Color(0xFF0A0E13),
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.videocam_off, size: 64, color: AppColors.textSecondary),
                    const SizedBox(height: 16),
                    Text('Camera Feed', style: TextStyle(
                        color: AppColors.textSecondary, fontSize: 16)),
                    const SizedBox(height: 8),
                    Text('Press Start to begin live scanning',
                        style: TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                  ],
                ),
              ),
            ),
            // Controls overlay
            Positioned(
              bottom: 16, left: 16, right: 16,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _ControlButton(
                    icon: Icons.play_arrow,
                    label: 'Start',
                    color: AppColors.accentGreen,
                    onTap: () {},
                  ),
                  const SizedBox(width: 12),
                  _ControlButton(
                    icon: Icons.stop,
                    label: 'Stop',
                    color: AppColors.accentRed,
                    onTap: () {},
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ControlButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  const _ControlButton({
    required this.icon, required this.label,
    required this.color, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.15),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.5)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}
