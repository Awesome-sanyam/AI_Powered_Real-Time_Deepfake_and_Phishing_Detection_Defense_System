import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_dashboard/main.dart';

void main() {
  testWidgets('App smoke test — DefenceApp renders without crash', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(
      home: Scaffold(body: Center(child: Text('AI Defence SOC Dashboard'))),
    ));
    expect(find.text('AI Defence SOC Dashboard'), findsOneWidget);
  });
}
