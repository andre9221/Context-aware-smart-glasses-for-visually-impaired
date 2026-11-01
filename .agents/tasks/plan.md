# Implementation Plan — Smart Glasses Full UI Rebuild

## Codebase Findings

**Web dashboard** (`dashboard/`): Three files — `index.html`, `style.css`, `app.js`. Already has a dark glassmorphism design system with exactly the CSS variables needed (`--bg-space: #070a12`, `--accent-cyan: #00f2fe`, `--accent-blue: #4facfe`, Outfit + JetBrains Mono fonts, `.glass-card` with `backdrop-filter: blur(14px)`). Currently wired for two roles only (Researcher + Caregiver). The Researcher telemetry dashboard (radar, haptic visualiser, hazard table, analytics charts, SSE stream) must be preserved verbatim and shown only when the Researcher role logs in.

**Flutter app** (`lib/`): `pubspec.yaml` already declares `fl_chart: ^0.65.0`, `provider: ^6.0.5`, `google_fonts: ^6.1.0`, `geolocator: ^10.1.0`. `main.dart` registers `AppState` (login/logout with role string) and `GlassesBleService` as providers, and defines routes `/`, `/patient`, `/caregiver`, `/doctor`. `AppColors` exposes `accentBlue`, `accentViolet`, `accentPink`, `success`, `warning`, `danger`, `textMuted`, `textSecondary`. `GlassCard` accepts `padding`, `borderRadius`, `borderColor`, `blurSigma`. `AmbientBackground` takes a single `child`. `GlassesBleService` has `state`, `batteryPercent`, `scanAndConnect()`, `disconnect()`, `setSensitivity()`. `_LiveMapCard` (stateful, AnimationController-based pulsing marker, `_GridPainter`) already exists in `caregiver_dashboard.dart`. `_MobilityChart` (fl_chart BarChart) already exists in `doctor_dashboard.dart`.

**Do not modify**: `lib/main.dart`, `lib/theme/app_theme.dart`, `lib/widgets/`, `lib/services/`, `dashboard/server.py`, any Python files.

---

## Key Implementation Decisions

1. **Single-page multi-dashboard web app with JS view-switching.** Login determines which dashboard `<section>` is shown/hidden. The existing Researcher telemetry section stays intact — its HTML, CSS, and JS are not touched, just hidden/shown. This avoids breaking the live SSE stream while adding three new role views.

2. **Role tabs extend from 2 to 4.** The existing `role-tabs` grid changes from `grid-template-columns: 1fr 1fr` to `repeat(4, 1fr)` on larger screens and wraps on mobile. Tab IDs become `tabDoctor`, `tabCaregiver`, `tabPatient`, `tabResearcher`.

3. **New dashboard sections are plain HTML inside `<section id="doctorDashboard">`, `<section id="caregiverDashboard">`, `<section id="patientDashboard">` elements.** Each uses the existing `.glass-card`, `.card-header`, `.dashboard-grid`, `.stat-box` CSS classes plus a small set of new utility classes added to `style.css`. No new CSS files.

4. **Mock data in `app.js`.** All patient/appointment/medication data is hardcoded JS objects — no new backend API. The existing SSE stream from `server.py` is used only for the Researcher role, exactly as today.

5. **Medication reminder notification uses `setTimeout` (5 seconds after login).** It shows a `div.med-reminder-banner` prepended to the patient dashboard and also adds an item to the notification panel. No Service Worker needed for this demo.

6. **Notification bell is placed in the shared `.status-header`.** A bell icon with an unread-count badge is added to the header `.telemetry-badges` area. Clicking it toggles a `.notification-panel` slide-in drawer (CSS `transform: translateX`). Content depends on the active role.

7. **Flutter: expand each screen in-place.** The three `_dashboard.dart` files are rewritten (not new files) — each gets new private widget classes appended below the existing ones. `_LiveMapCard` and `_MobilityChart` are kept identical; only new sections are added around them.

8. **Critical Zone card in `caregiver_dashboard.dart` uses a second `AnimationController` in a new `_CriticalZoneCard` StatefulWidget.** The pulsing red border is driven by a dedicated `AnimationController` that only runs when `riskLevel == 'CRITICAL'`, matching the spec's "card pulses red when CRITICAL" requirement. Mock data drives the initial state; when live telemetry connects it would be updated via `GlassesBleService`.

9. **Medication toggle in `patient_dashboard.dart` uses `StatefulWidget _MedicationCard`.** Each med item carries a local `bool _taken` state toggled by a `Switch`, with color badge green/amber/red computed from taken status + scheduled time. The `SnackBar` reminder fires via `Future.delayed(Duration(seconds: 3))` in `initState` of `_PatientDashboardState`, which already is a `StatefulWidget`.

10. **Chart.js mobility bar chart** in the Doctor Dashboard web section uses a `<canvas id="mobilityChart">` with 7-day mock data matching the Flutter chart's values. History tabs (This Week / Last Month) are plain CSS `.tab-btn` buttons that swap which dataset the chart renders.

---

## Implementation Plan

- [ ] 1. **Extend `dashboard/style.css` — new utility classes only.**
      Add styles for the four new dashboard sections without touching existing rules: `.role-tabs` becomes 4-column (media-query fallback to 2×2 on mobile), `.dashboard-section` (hide/show helper), `.vitals-grid` (3-column stat grid), `.history-tabs` + `.tab-btn` (active underline), `.appointments-list` + `.appt-item`, `.reports-list` + `.report-card`, `.ai-summary-card` (gradient border), `.map-mock` (CustomPaint-style grid via CSS background-image repeating-linear-gradient), `.risk-bar-track` + `.risk-bar-fill`, `.critical-card.critical` (pulsing red border animation `@keyframes pulse-critical-border`), `.med-list` + `.med-item` + `.med-toggle`, `.med-reminder-banner` (amber stripe at top of patient section), `.notif-bell-btn` + `.notif-badge` + `.notification-panel` (slide-in from right, `transform: translateX(100%)` hidden / `translateX(0)` shown), `.quick-actions-row`.
      Files: `dashboard/style.css`
      Verify: Open `dashboard/index.html` in a browser. Login as doctor — no layout breakage. All existing Researcher/Caregiver sections still render correctly.

- [ ] 2. **Rebuild `dashboard/index.html` — add 4 role tabs and three new dashboard sections.**
      - Update the `.role-tabs` div to 4 buttons: Doctor (`tabDoctor`, `data-role="doctor"`), Caregiver (`tabCaregiver`, `data-role="caregiver"`), Patient (`tabPatient`, `data-role="patient"`), Researcher (`tabResearcher`, `data-role="researcher"`).
      - Add quick-login buttons for doctor and patient alongside existing researcher/caregiver buttons.
      - Add `<section id="doctorDashboard" class="dashboard-section" style="display:none">` containing:
        - Patient Preview Card: avatar placeholder `<div class="avatar-placeholder">`, name/ID/age/condition/glasses model/device battery/last sync.
        - Patient Data Panel: `.vitals-grid` with 6 stat boxes (Heart Rate, SpO2, Steps Today, Falls Today, Avg Walk Speed, BLE Signal).
        - Previous Data/History: two `.tab-btn` buttons (This Week / Last Month), `<canvas id="mobilityChart">`, table `#sessionHistoryTable` with 10 mock rows.
        - Patient Appointments: `#appointmentsList` ul, `+ Schedule` button stub.
        - Previous Reports & Prescriptions: `#reportsList` card list with date/type/summary/Download button.
        - AI Summary: `.ai-summary-card` with mock summary text.
      - Add `<section id="caregiverDashboard" class="dashboard-section" style="display:none">` containing the existing Caregiver sections that are currently inside the main grid: live GPS map (`<canvas id="mapCanvas">`), user reports list `#reportsList`, critical zone card `#criticalZoneCard`, quick actions row. The existing map/alert content from the old caregiver session is moved here; the Caregiver role no longer falls through to the old Researcher grid.
      - Add `<section id="patientDashboard" class="dashboard-section" style="display:none">` containing:
        - My Details card: name/age/diagnosis/doctor/emergency contact/device ID/app version.
        - Data Sync Status: BLE card, last sync time, `<progress id="syncProgressBar">`, Sync Now button, WiFi glasses status.
        - My Reports: table/list of last 5 sessions.
        - Appointments: list with Confirm/View buttons.
        - Medication Reminders: `#medList` with 3 med items each having a checkbox toggle + badge.
        - Med reminder banner `#medReminderBanner` (hidden initially).
      - Add notification bell `<button id="notifBell">🔔 <span id="notifCount">3</span></button>` inside `.telemetry-badges` header area.
      - Add `<div id="notifPanel" class="notification-panel glass-card">` with close button and `<ul id="notifList">`.
      - Wrap the existing Researcher dashboard grid in `<section id="researcherDashboard" class="dashboard-section">`.
      Files: `dashboard/index.html`
      Verify: Open in browser, inspect DOM — all four `dashboard-section` elements exist, role tabs render as a row of 4.

- [ ] 3. **Rewrite `dashboard/app.js` — extend authentication + wire all new dashboard sections.**
      Preserve every existing function intact (`drawRadar`, `handleTelemetryEvent`, `triggerNodePulse`, `appendTableRow`, `updateCharts`, `connectTelemetryStream`, export buttons, session timer). Add/change:

      **Auth credentials map** — extend the credentials object to include all four roles:
      ```
      doctor   / Doctor2026!    → { name:'Dr. Sarah Chen', role:'Doctor', avatar:'🩺', dash:'doctor' }
      caregiver/ Caregiver2026! → { name:'Primary Caregiver', role:'Caregiver', avatar:'👨‍👩‍👧', dash:'caregiver' }
      patient  / Patient2026!   → { name:'John Doe', role:'Patient', avatar:'🧑', dash:'patient' }
      researcher/Glasses2026!   → { name:'Lead Researcher', role:'Researcher', avatar:'🔬', dash:'researcher' }
      ```
      Quick-login buttons `#btnQuickDoctor` and `#btnQuickPatient` added.

      **Dashboard visibility** — `showDashboard(role)` function: hides all `.dashboard-section` elements, then shows the one matching the role (`doctor`→`#doctorDashboard`, etc.). The Caregiver role now shows `#caregiverDashboard` instead of the old shared grid, but `connectTelemetryStream()` still runs for all roles (the SSE stream data is used by Critical Zone Detection for caregiver).

      **Role tabs** — 4-button tab switching using `data-role` attribute.

      **Doctor Dashboard JS**: Mock data constants for vitals, sessions, appointments, reports. `initDoctorDashboard()` populates DOM. `mobilityChart` Chart.js bar chart with `type:'bar'`, cyan→blue gradient bars, 7-day labels, `This Week`/`Last Month` tab buttons that call `chart.data.datasets[0].data = weekData` or `monthData` then `chart.update()`.

      **Caregiver Dashboard JS**: `mapCanvas` drawn with `_GridPainter`-style repeating grid + road lines (`beginPath` horizontal/vertical lines at 28px spacing with `rgba(255,255,255,0.05)`) + `requestAnimationFrame` pulsing blue marker dot (ring expanding animation). Mock reports list rendered into `#userReportsList`. `initCriticalZoneCard()` reads `currentObstacle` and `eventsHistory` from the existing telemetry state to compute `riskScore` (0–100 based on obstacle distance and count of recent events) and sets `#criticalZoneCard` class to `critical` when score > 70, adding the `pulse-critical-border` CSS animation.

      **Patient Dashboard JS**: `initPatientDashboard()` populates my-details, sync status (mock 85% sync progress bar), last 5 sessions table, appointments list with Confirm/View buttons. Medication list: 3 meds (`Metformin 500mg / 8:00 AM`, `Aspirin 75mg / 1:00 PM`, `Atorvastatin 10mg / 9:00 PM`), each with a checkbox that toggles a taken badge green/amber. `setTimeout(() => showMedReminderBanner('Aspirin 75mg'), 5000)` fires 5 seconds after login.

      **Notification bell**: `#notifBell` click toggles `#notifPanel` slide-in (`classList.toggle('open')`). Unread count decrements to 0 when panel opened. `initNotifPanel(role)` populates `#notifList` with role-appropriate items (med reminders + appointment + battery alert for patient; location alert + caregiver check-in for caregiver; appointment + lab result for doctor).

      Files: `dashboard/app.js`
      Verify: Open browser. Login as each of the 4 roles — correct dashboard section appears. Doctor shows vitals + chart. Caregiver map animates. Patient med banner appears after 5 seconds. Researcher radar/haptic/stream all still function. Logout returns to login screen.

- [ ] 4. **Expand `lib/screens/doctor_dashboard.dart` — add 5 new sections.**
      The file is a complete rewrite of the section below `DoctorDashboard.build()` (the widget class itself is unchanged). New private widget classes to append:

      - `_PatientPreviewCard` — StatelessWidget, GlassCard containing: CircleAvatar (48 radius, `AppColors.accentBlue` bg, person icon), name/ID/age/condition in a Column, a Row with glasses model text + battery % `Text`, last sync time `Text` in `AppColors.textMuted`.
      - `_VitalsRow` — Row of 3 + Row of 3 (or Wrap with 6 items), each a `_VitalBox` with icon, label, value string, color. Values: HR 72 bpm (success), SpO2 98% (accentBlue), Steps 4,231 (accentViolet), Falls 0 (success), Avg Speed 1.2 m/s (accentBlue), BLE Signal −68 dBm (warning).
      - `_HistorySection` — StatefulWidget with `_tabIndex` (0=This Week, 1=Last Month). Two tab buttons in a Row (styled with `Container` + `BoxDecoration` border-bottom line), below them the existing `_MobilityChart` (reused), below that a `DataTable` / ListView of 10 mock session rows (date, duration, events, distance).
      - `_AppointmentsCard` — GlassCard with ListView of 3 `ListTile`s (date/time, type, status chip `Container(color: AppColors.success.withOpacity(0.15))`), plus `ElevatedButton` "+ Schedule" stub at the bottom.
      - `_ReportsCard` — GlassCard wrapping `ExpansionTile`-based list of 4 mock reports. Each `ExpansionTile` title is `Row(date + type badge)`, expanded content shows summary text + `TextButton("Download")`.
      - `_AiSummaryCard` — GlassCard with `Container(decoration: BoxDecoration(gradient: LinearGradient([AppColors.accentBlue.withOpacity(0.12), AppColors.accentViolet.withOpacity(0.12)])))` wrapping an Icon + Text summary paragraph.

      In `DoctorDashboard.build()` ListView, replace the existing Row of `_StatCard`s and diagnostics section with the sequence: `_PatientPreviewCard()`, gap 20, `_VitalsRow()`, gap 20, `_HistorySection()`, gap 20, `_AppointmentsCard()`, gap 20, `_ReportsCard()`, gap 20, `_AiSummaryCard()`. Keep the existing `_MobilityChart` referenced from `_HistorySection` rather than inline. Keep `_StatCard` and `_DiagnosticTile` classes in the file (they may be used elsewhere or for future use).
      Files: `lib/screens/doctor_dashboard.dart`
      Verify: `flutter analyze lib/screens/doctor_dashboard.dart` — no errors. App builds: `flutter build apk --debug` (or `flutter run` if device attached) — DoctorDashboard renders without overflow or missing-symbol errors.

- [ ] 5. **Expand `lib/screens/caregiver_dashboard.dart` — add Critical Zone card, patient reports list, quick actions.**
      Keep `_LiveMapCard`, `_GridPainter`, `_AlertTile` classes unchanged.

      New private widget classes to add:

      - `_CriticalZoneCard` — StatefulWidget with two AnimationControllers:
        - `_pulseController` (500ms, repeat) — drives a `ColorTween(begin: AppColors.danger, end: AppColors.danger.withOpacity(0.3))` for the border color when CRITICAL.
        - `_riskScore` local int mock = 45 (CAUTION range; SAFE < 30, CAUTION 30–70, CRITICAL > 70).
        - Risk level string computed from score.
        - `AnimatedBuilder` wrapping a GlassCard with `borderColor` set to: SAFE→success, CAUTION→warning, CRITICAL→animated `_pulseController` value mapped to red.
        - Contents: risk level label with color, `LinearProgressIndicator(value: _riskScore/100)` styled with matching color, nearby hazard count Text (sourced from a mock value 3), last glasses data timestamp Text, map overlay indicator row.
        - `initState` starts `_pulseController` only if `_riskLevel == 'CRITICAL'`.

      - `_PatientReportsList` — StatelessWidget, GlassCard with a Column of 4 `_ReportTile` widgets. Each `_ReportTile` is a `ListTile` with leading `Container` severity badge (Icon + color matching severity: Hazard Alert=red, Navigation Event=blue, Session Summary=green), title = type + date, subtitle = description text.

      - `_QuickActionsRow` — Row of 3 `ElevatedButton`s: "📞 Call Patient" (success color), "⚠️ Send Alert" (warning), "📋 History" (accentBlue). Each `onPressed` is a stub showing a `ScaffoldMessenger.of(context).showSnackBar(...)`.

      In `CaregiverDashboard.build()`: after `_LiveMapCard()`, add `const SizedBox(height: 20)`, `const _CriticalZoneCard()`, `const SizedBox(height: 20)`, section title "Patient Reports", `const _PatientReportsList()`, `const SizedBox(height: 20)`, `const _QuickActionsRow()`. Replace the existing static `_AlertTile` list with `_PatientReportsList()` (the old 3 `_AlertTile`s can remain below as "Safety Alerts" sub-section or be removed — keep them for backward compatibility).
      Files: `lib/screens/caregiver_dashboard.dart`
      Verify: `flutter analyze lib/screens/caregiver_dashboard.dart` — 0 errors. Hot-reload shows Critical Zone card, reports list, and Quick Actions row without overflow.

- [ ] 6. **Expand `lib/screens/patient_dashboard.dart` — add My Details, Medication Reminders, Appointments, Session Reports, SnackBar reminder.**
      `_PatientDashboardState` is already a `StatefulWidget` — add to its `initState`:
      ```dart
      Future.delayed(const Duration(seconds: 3), () {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('💊 Time to take Aspirin 75mg'),
            backgroundColor: AppColors.warning.withOpacity(0.9),
            duration: const Duration(seconds: 5),
          ),
        );
      });
      ```

      New private widget classes:

      - `_MyDetailsCard` — StatelessWidget, GlassCard. Two-column info grid using `Row` + `Expanded` pairs: Name/John Doe, Age/34, Diagnosis/Low Vision, Doctor/Dr. Sarah Chen, Emergency Contact/+1-555-0147, Device ID/SG-948-22A, App Version/1.0.0+1. Each info row: small label `Text` in `AppColors.textMuted`, value `Text` in `textPrimary`.

      - `_DataSyncCard` — StatelessWidget, GlassCard. BLE connection status row (icon + "Connected · last sync 2 min ago"), `LinearProgressIndicator(value: 0.85)` with label "85% synced", `ElevatedButton("Sync Now")` stub, WiFi glasses status row ("WiFi Sync · SmartGlasses_WiFi · Active").

      - `_MedicationCard` — StatefulWidget. `List<_MedItem>` of 3 items with `name`, `time`, `bool taken`, `MedStatus` enum (taken/due/overdue). `build` returns GlassCard with `ListView` (shrinkWrap). Each row: med name + time label, color badge `Container` (green=taken, amber=due, red=overdue), `Switch(value: item.taken, onChanged: (v) => setState(() => item.taken = v))`. Badge color updates on toggle.

      - `_AppointmentsCard` (patient version) — StatelessWidget, GlassCard, 2 `ListTile`s: "Ophthalmology Check-up · 15 Nov 2026 · 10:30 AM" + "Neurology Follow-up · 28 Nov 2026 · 2:00 PM", each with trailing `Row` of `OutlinedButton("Confirm")` + `TextButton("View")`.

      - `_SessionReportsCard` — StatelessWidget, GlassCard, 3 `ListTile`s for last sessions: date, duration, hazard count, distance, falls, leading badge icon colored by rating (good=success, warning=warning).

      In `_PatientDashboardState.build()` ListView, insert in order before `_ConnectionCard`: `_MyDetailsCard()`, gap 20. After `_ConnectionCard`, add `_DataSyncCard()`, gap 20. After existing Device Settings section, add `_MedicationCard()`, gap 20, `_AppointmentsCard()`, gap 20, `_SessionReportsCard()`, gap 20. Keep existing `_recentAlerts` / `_AlertRow` section as the last item.
      Files: `lib/screens/patient_dashboard.dart`
      Verify: `flutter analyze lib/screens/patient_dashboard.dart` — 0 errors. SnackBar appears ~3 seconds after launching the patient screen. Medication toggles update badge color. All new cards render without RenderFlex overflow.

- [ ] 7. **Final integration check — run Flutter analyzer across all modified screens.**
      Run `flutter analyze lib/screens/` to catch any cross-file issues introduced by the additions (import conflicts, unused imports, missing `const`).
      Files: none (analysis only)
      Verify: `flutter analyze lib/screens/` outputs "No issues found!" or only lint hints (no errors or warnings of type `error`).

---

## Files Created / Modified

| File | Action |
|------|--------|
| `dashboard/style.css` | Modified — add new utility classes; no existing rules changed |
| `dashboard/index.html` | Modified — 4-role tabs, 3 new dashboard sections, notification bell, researcher section wrapped |
| `dashboard/app.js` | Modified — extend auth map, add `showDashboard()`, `initDoctorDashboard()`, `initCaregiverDashboard()`, `initPatientDashboard()`, `initNotifPanel()`; all existing functions preserved |
| `lib/screens/doctor_dashboard.dart` | Modified — add 6 new private widget classes, update `build()` ListView sequence |
| `lib/screens/caregiver_dashboard.dart` | Modified — add `_CriticalZoneCard`, `_PatientReportsList`, `_QuickActionsRow`, update `build()` |
| `lib/screens/patient_dashboard.dart` | Modified — add SnackBar in `initState`, add 5 new private widget classes, update `build()` ListView |
| `.agents/tasks/plan.md` | Created — this file |

## Files NOT Modified

`lib/main.dart`, `lib/theme/app_theme.dart`, `lib/widgets/glass_card.dart`, `lib/widgets/ambient_background.dart`, `lib/services/ble_service.dart`, `lib/services/location_service.dart`, `lib/screens/login_screen.dart`, `dashboard/server.py`, all Python files.
