# PiHRMS Checkpoint 5 — Attendance and Leave Management

Applied the PiHRMS design system to existing attendance, shift, and leave screens in the Horilla HR 2.4.0 checkout. The shared stylesheet covers dashboard cards, navigation and filters, approval status, leave balances, tables, request forms, and calendar and modal sizing.

## Prior checkpoint reconciliation

All **37 templates** in the Checkpoint 4 manifest exist and appear in the cumulative working-tree diff against `6c15617b8`. The employee stylesheet and its template include are also present. The six-file summary represents a subset of the changes visible in the repository. No Checkpoint 4 template edits were missing.

The Checkpoint 5 baseline contained 117 working-tree changes including untracked files. The verification reconstructed the original bytes of the five previously edited shell and dashboard templates that received additive styling. The 111 other checked files match the baseline byte for byte. The implementation log gained the Checkpoint 5 entry.

## Inventory and render paths

The repository contains 146 attendance and 169 leave application templates. The route declarations include 232 names in attendance and 212 in leave. Review also covered the related base shift, schedule, work type, holiday, and company leave settings, plus the corresponding theme overrides and generic components. The configured loader searches database-backed templates, then the theme, app template directories, and the root fallback. No running instance was used to determine which database overrides are active. [UI page inventory](PIHRMS_UI_PAGE_INVENTORY.md) · [UI architecture](PIHRMS_UI_ARCHITECTURE.md)

| Workflow | Checkpoint changes and protected behavior |
| --- | --- |
| Check-In and Check-Out | Both template variants retain their existing employee, company, clock-state, eligibility, timer, and geolocation branches. The existing buttons now have explicit types and accessible names. The themed header still renders one attendance host. Both the normal HTMX GET and the geolocation handler's request keep the same route, target and swap. Existing form CSRF tags and all authentication, session, message and timestamp handling were preserved. |
| Attendance dashboard and records | Applied scoped cards, filters and table styles to the existing data, charts, validation queue and overtime links. Daily, personal, activity, late/early and monthly report pages retain their existing filters, sort, export, and pagination. No additional metrics were created. |
| Regularization | Styled the attendance request pages, the modal form, and the monthly summary calendar. Editable calendar days can open their existing action from the keyboard. Reasons, approvals, rejections, audit bindings and notifications stay connected to their original forms and endpoints. |
| Shifts and overtime | Styled shift, schedule, work type and rotation settings and assignments, shift and work type request pages, work records, and hour-account pages. |
| Leave dashboard, balances and approvals | Styled dashboard cards, employee balances, application and approval queues, status cells, allocation and compensatory leave, type and rule settings, and request forms. Existing selected date, type, attachment, approval routing and validation bindings remain in place. |
| Calendars, holidays and reports | Styled the existing shared attendance calendar that displays leave and holidays, including its read-only self-service use. Styled the repository's holiday, company leave and attendance/leave report templates. The inventory review did not identify a separate leave-only calendar page. |

The reviewed attendance request and monthly regularization code did not show enforcement of a three-per-month limit. The discussed 10 AM to 7 PM hours were not added to the UI or shift settings. Shift thresholds, overtime rules, payroll integration and leave eligibility stay in the existing application code.

## Verification

| Check | Evidence |
| --- | --- |
| Static template and binding comparison | 87 templates compared against the starting source. Existing URL, include and conditional tags, form markup, CSRF, record bindings, IDs, data/HTMX hooks and embedded scripts were preserved. 586 literal references resolved in the checkout. No newly unbalanced Django blocks. |
| Changes to protected files | No Checkpoint 5 Python, migrations, models, settings or API changes. The previous `base/context_processors.py` branding diff matches its baseline. Existing Check-In/Check-Out URL routes, timers and request dispatch scripts are unchanged. |
| Offline Edge responsive fixture | Passed at **320 × 568, 375 × 667, 667 × 375, 768 × 1024, 1024 × 768, 1366 × 768 and 1600 × 900** using bundled CSS and representative markup. Checked document and workspace bounds, KPI and balance card reflow, local table scroll, seven calendar columns, short-landscape calendar scrolling, header clock hit target and label display, and mobile modal bounds. |
| Accessibility | Checked visible focus on the clock and native date input in Edge. Reviewed the clock and calendar button labels, the new keyboard activation for editable calendar cells, existing textual status labels, and the reduced-motion CSS rules in source. |
| CSS and patch | PostCSS parsing and `git diff --check` passed. |

## Runtime limits and open verification

A follow-up Edge run for the clock label opacity adjustment timed out. The final stylesheet passed static checks, and the earlier seven-width fixture verified the clock target, label display, and keyboard focus.

Django is unavailable in the local Python environment. The Edge fixtures used representative data, so live template compilation, real Check-In/Check-Out, geolocation, timers after HTMX swaps, attendance and leave approvals, uploads, search/export flows, role and company isolation, and database-backed template overrides remain unverified. Physical-device and assistive-technology testing remains open. The code refers to `cbv/attendances/attendance_tab_shell.html` from the employee attendance tab view. That key has no checked-in template candidate and may need to be resolved in an authorized runtime.

## Changed files

**87 edited templates**

- `attendance/templates/attendance/attendance/attendance_empty.html`
- `attendance/templates/attendance/attendance/attendance_view.html`
- `attendance/templates/attendance/attendance_account/attendance_overtime_view.html`
- `attendance/templates/attendance/attendance_account/overtime_empty.html`
- `attendance/templates/attendance/attendance_activity/activity_empty.html`
- `attendance/templates/attendance/attendance_activity/attendance_activity_view.html`
- `attendance/templates/attendance/components/in_out_component.html`
- `attendance/templates/attendance/dashboard.html`
- `attendance/templates/attendance/dashboard/dashboard.html`
- `attendance/templates/attendance/grace_time/grace_time.html`
- `attendance/templates/attendance/late_come_early_out/reports.html`
- `attendance/templates/attendance/late_come_early_out/reports_empty.html`
- `attendance/templates/attendance/monthly_summary/_calendar_modal_host.html`
- `attendance/templates/attendance/monthly_summary/calendar_modal.html`
- `attendance/templates/attendance/monthly_summary/monthly_summary.html`
- `attendance/templates/attendance/own_attendance/own_empty.html`
- `attendance/templates/attendance/own_attendance/view_own_attendances.html`
- `attendance/templates/attendance/settings/attendance_rule.html`
- `attendance/templates/attendance/work_record/work_record_view.html`
- `attendance/templates/cbv/attendance_activity/attendance_activity_home.html`
- `attendance/templates/cbv/attendance_request/attendance_request.html`
- `attendance/templates/cbv/attendances/attendance_view_page.html`
- `attendance/templates/cbv/hour_account/hour_account.html`
- `attendance/templates/cbv/hour_account/hour_account_main.html`
- `attendance/templates/cbv/late_come_and_early_out/late_come_and_early_out.html`
- `attendance/templates/cbv/my_attendances/my_attendances.html`
- `attendance/templates/requests/attendance/attendance_form.html`
- `attendance/templates/requests/attendance/requests_empty.html`
- `attendance/templates/requests/attendance/view-requests.html`
- `base/templates/base/rotating_shift/rotating_shift.html`
- `base/templates/base/rotating_shift/rotating_shift_assign.html`
- `base/templates/base/rotating_work_type/rotating_work_type.html`
- `base/templates/base/rotating_work_type/rotating_work_type_assign.html`
- `base/templates/base/settings/company_leaves.html`
- `base/templates/base/settings/holidays.html`
- `base/templates/base/shift/schedule.html`
- `base/templates/base/shift/shift.html`
- `base/templates/base/work_type/work_type.html`
- `base/templates/cbv/company_leaves/company_leave_home.html`
- `base/templates/cbv/holidays/holidays_home.html`
- `base/templates/cbv/rotating_shift/rotating_shift.html`
- `base/templates/cbv/rotating_work_type/rotating_work_home.html`
- `base/templates/cbv/shift_request/shift_request.html`
- `base/templates/cbv/work_shift_tab/profile_tab_shell.html`
- `base/templates/cbv/work_type_request/work_type_home.html`
- `base/templates/company_leave/company_leave_view.html`
- `base/templates/holiday/holiday_view.html`
- `base/templates/shift_request/shift_request_view.html`
- `base/templates/work_type_request/work_type_request_view.html`
- `horilla_theme/templates/attendance/components/in_out_component.html`
- `horilla_theme/templates/attendance/dashboard/dashboard.html`
- `horilla_theme/templates/attendance/work_record/work_record_view.html`
- `horilla_theme/templates/cbv/employee_individual/leave_tab.html`
- `horilla_theme/templates/index.html`
- `horilla_theme/templates/leave/leave_type/leave_type_creation.html`
- `horilla_theme/templates/leave/leave_type/leave_type_update.html`
- `horilla_theme/templates/report/attendance_report.html`
- `horilla_theme/templates/report/leave_report.html`
- `leave/templates/cbv/assigned_leave/assigned_leave_home.html`
- `leave/templates/cbv/compensatory_leave/compensatory_home.html`
- `leave/templates/cbv/employee_individual/leave_tab.html`
- `leave/templates/cbv/leave_allocation_request/leave_allocation_request.html`
- `leave/templates/cbv/leave_requests/custom_status_col.html`
- `leave/templates/cbv/leave_requests/form/inherit.html`
- `leave/templates/cbv/leave_requests/leave_requests_home.html`
- `leave/templates/cbv/leave_settings/leave_settings_main.html`
- `leave/templates/cbv/leave_types/leave_type_home.html`
- `leave/templates/cbv/my_leave_request/form/inherit.html`
- `leave/templates/cbv/my_leave_request/my_leave_request_home.html`
- `leave/templates/cbv/restricted_days/restricted_days.html`
- `leave/templates/leave/company_leave/company_leave_view.html`
- `leave/templates/leave/compensatory_leave/compensatory_leave_view.html`
- `leave/templates/leave/dashboard.html`
- `leave/templates/leave/holiday/holiday_view.html`
- `leave/templates/leave/leave_allocation_request/leave_allocation_request_view.html`
- `leave/templates/leave/leave_assign/assign_view.html`
- `leave/templates/leave/leave_request/request_view.html`
- `leave/templates/leave/leave_type/leave_type_creation.html`
- `leave/templates/leave/leave_type/leave_type_empty_view.html`
- `leave/templates/leave/leave_type/leave_type_update_page.html`
- `leave/templates/leave/leave_type/leave_type_view.html`
- `leave/templates/leave/leave_type_creation.html`
- `leave/templates/leave/restrict/view_restrict.html`
- `leave/templates/leave/settings/leave_rules.html`
- `leave/templates/leave/settings/restrict_leaves.html`
- `leave/templates/leave/user_leave/user_request_view.html`
- `templates/index.html`

**Shared presentation and documentation**

- `static/pihrms/time-off.css`
- `docs/PIHRMS_CHECKPOINT5_REPORT.md`
- `docs/PIHRMS_UI_IMPLEMENTATION_LOG.md`

Payroll and subsequent checkpoints await approval.
