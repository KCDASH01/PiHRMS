# PiHRMS Checkpoint 3 report

Checkpoint 3 updates authentication screens and dashboards in the local Horilla HR 2.4.0 checkout on branch `2.0`, commit `6c15617b8297b7a6775daa6c29aefcc48b1eb29f`.

## Authentication

The themed login and root fallback share a brand panel, with the existing uploaded company logo taking precedence and the PiHRMS SVG as fallback. The desktop layout places the introduction beside the form. Mobile reduces it to a wordmark above a single-column form.

The styling also covers password recovery, reset confirmation and expired links, the password reset email confirmation, two-factor authentication, account password and username changes and their fallback fragments, access denial and HTTP 403, 404 and 405 pages, initial setup authentication, and candidate sign-in. Existing button hooks were kept. Where the theme used non-focusable password visibility toggles, native buttons provide a keyboard target for the same click handler.

The login and recovery routes, entered field names, form actions, CSRF, validation and error bindings, initialization and demo conditions, and HTMX targets remain in their existing templates and views. The Django admin’s packaged authentication UI and the repository’s standalone `auth/login.html` example are separate surfaces. The example is outside the configured template roots.

## Dashboards

| Surface | Selection and styling |
| --- | --- |
| Shared analytics home | `/dashboard/` resolves `templates/dashboard.html` on disk. Existing leadership, HR and manager role defaults and permission predicates still select content. The header now has an optional welcome using the signed-in employee’s existing first name. |
| Employee self-service | `/my-dashboard/` resolves `base/templates/base/ess_dashboard.html`. It retains personal widgets and the existing conditions for switching to analytics. The employee’s own first name supplies the optional welcome. |
| Module dashboards | The existing employee, attendance, leave, payroll, recruitment, onboarding, offboarding, performance, project, helpdesk and asset dashboards use shared card, filter, heading and responsive grid styles. |
| Alternate layouts | The fallback shell dashboard component and legacy attendance, recruitment, performance, project, offboarding and employee dashboard variants use scoped styles. Their existing widget and chart wiring stays in place. |

The shared dashboard stylesheet layers on top of the existing UI, including on content returned through HTMX. Headings, date controls, KPI values, panels, and focus states follow the PiHRMS palette. Indigo replaces the existing dashboard brand accent while retaining chart series mappings and other status colors. Seventy-two chart or analytics regions reference their existing card titles for accessible naming. The dashboard scripts retain their existing requests, metric bindings, initialization and interaction logic.

## Permissions, attendance and template resolution

- `base/dashboard_roles.py` still selects employee, manager, HR or leadership. The company and permission gates, scoped widget data, route checks, and API endpoints remain in existing code.
- The Checkpoint 2 shell was preserved byte for byte. Its header still renders the existing attendance component under the installed-app condition, with one `#attendance-activity-container`. The clock-in and clock-out routes, geolocation branch, permissions, handlers, timers and notifications are unchanged. The dashboards reuse this header control.
- Django’s database-backed loader precedes the theme and root templates. Source inspection establishes the local default candidates. The instance-specific override list has not been accessed.
- The unresolved `dynamic.html` key belongs to the older generic dynamic-field HTMX route. Neither the authentication templates nor the dashboard render paths directly reference it. Its view, route and missing file status remain as documented in Checkpoint 2.

## Verification

| Check | Status | Evidence |
| --- | --- | --- |
| Form and route preservation | PASS | Compared auth and dashboard URL tags, CSRF tags, form methods and targets, IDs and field names with the checked-in source. Before editing, the auth transformations also compared those bindings against the working copies. |
| Dashboard and chart behavior source | PASS | Preserved existing conditions and matched inline dashboard scripts after normalizing presentation classes and the brand color. All 72 added chart-title relationships had unique targets. |
| Template and static references | PASS | Checked Django block balance and resolved 213 literal template and static references. |
| CSS and JavaScript source checks | PASS | PostCSS parsed both stylesheets. Node checked 29 inline scripts with Django substitutions removed. One script had the same substitution-related parse error before and after, so this check establishes that the edit introduced no new syntax errors. |
| Prior checkpoints and protected source | PASS | The shell, attendance integration, both original brand SVGs and prior reports retained their source hashes or matched Git. The only Python diff from the release remains the earlier branding change. No backend files, migrations, database settings or database contents were edited. |
| Visual and responsive verification | PASS | Inspected offline Edge fixtures of the login and analytics layout at 320, 375, 768, 1024, 1366 and 1600 px. Both fixtures reported no document-level horizontal overflow at every width. The dashboard fixture exercised card and filter reflow without live chart data. |
| Live Django rendering and functional regression | NOT EXECUTED | Django is unavailable in the local Python environment. Offline fixtures do not resolve Django templates or validate real HTMX requests, accounts, permissions, chart data, or database state. |

## Remaining risks

- **High:** Verify valid and invalid login, password recovery and reset, two-factor authentication and account changes with real responses. Check per-company branding and validation in both template variants.
- **High:** Test leadership, HR, manager and employee dashboards with actual company scopes and role restrictions. Verify live charts, data loading, empty and error states, and dashboard preference persistence.
- **High:** Test the existing mobile drawer and header clock through live Check-In and Check-Out, including optional geolocation and failure handling.
- **Medium:** Check long labels, keyboard and screen-reader navigation, dark mode, third-party chart rendering, and any database-backed overrides in a permitted instance.

## Files changed

- [`asset/templates/asset/dashboard.html`](../asset/templates/asset/dashboard.html)
- [`attendance/templates/attendance/dashboard.html`](../attendance/templates/attendance/dashboard.html)
- [`attendance/templates/attendance/dashboard/dashboard.html`](../attendance/templates/attendance/dashboard/dashboard.html)
- [`base/templates/base/auth/password_change_form.html`](../base/templates/base/auth/password_change_form.html)
- [`base/templates/base/auth/two_factor_auth.html`](../base/templates/base/auth/two_factor_auth.html)
- [`base/templates/base/auth/username_change_form.html`](../base/templates/base/auth/username_change_form.html)
- [`base/templates/base/ess_dashboard.html`](../base/templates/base/ess_dashboard.html)
- [`docs/PIHRMS_CHECKPOINT3_REPORT.md`](../docs/PIHRMS_CHECKPOINT3_REPORT.md)
- [`docs/PIHRMS_UI_IMPLEMENTATION_LOG.md`](../docs/PIHRMS_UI_IMPLEMENTATION_LOG.md)
- [`employee/templates/employee/dashboard.html`](../employee/templates/employee/dashboard.html)
- [`employee/templates/employee/dashboard/dashboard_employee.html`](../employee/templates/employee/dashboard/dashboard_employee.html)
- [`helpdesk/templates/helpdesk/dashboard.html`](../helpdesk/templates/helpdesk/dashboard.html)
- [`horilla_theme/templates/attendance/dashboard/dashboard.html`](../horilla_theme/templates/attendance/dashboard/dashboard.html)
- [`horilla_theme/templates/base/auth/password_change_form.html`](../horilla_theme/templates/base/auth/password_change_form.html)
- [`horilla_theme/templates/base/auth/username_change_form.html`](../horilla_theme/templates/base/auth/username_change_form.html)
- [`horilla_theme/templates/dashboard/dashboard.html`](../horilla_theme/templates/dashboard/dashboard.html)
- [`horilla_theme/templates/dashboard/pms_dashboard.html`](../horilla_theme/templates/dashboard/pms_dashboard.html)
- [`horilla_theme/templates/dashboard/project_dashboard.html`](../horilla_theme/templates/dashboard/project_dashboard.html)
- [`horilla_theme/templates/forgot_password.html`](../horilla_theme/templates/forgot_password.html)
- [`horilla_theme/templates/horilla_theme/components/dashboard.html`](../horilla_theme/templates/horilla_theme/components/dashboard.html)
- [`horilla_theme/templates/initialize_database/horilla_user.html`](../horilla_theme/templates/initialize_database/horilla_user.html)
- [`horilla_theme/templates/login.html`](../horilla_theme/templates/login.html)
- [`horilla_theme/templates/offboarding/dashboard/dashboard.html`](../horilla_theme/templates/offboarding/dashboard/dashboard.html)
- [`horilla_theme/templates/reset_password.html`](../horilla_theme/templates/reset_password.html)
- [`leave/templates/leave/dashboard.html`](../leave/templates/leave/dashboard.html)
- [`offboarding/templates/offboarding/dashboard.html`](../offboarding/templates/offboarding/dashboard.html)
- [`offboarding/templates/offboarding/dashboard/dashboard.html`](../offboarding/templates/offboarding/dashboard/dashboard.html)
- [`onboarding/templates/onboarding/dashboard.html`](../onboarding/templates/onboarding/dashboard.html)
- [`payroll/templates/payroll/dashboard.html`](../payroll/templates/payroll/dashboard.html)
- [`pms/templates/dashboard/pms_dashboard.html`](../pms/templates/dashboard/pms_dashboard.html)
- [`pms/templates/pms/dashboard.html`](../pms/templates/pms/dashboard.html)
- [`project/templates/dashboard/project_dashboard.html`](../project/templates/dashboard/project_dashboard.html)
- [`project/templates/project/dashboard.html`](../project/templates/project/dashboard.html)
- [`recruitment/templates/candidate/self_login.html`](../recruitment/templates/candidate/self_login.html)
- [`recruitment/templates/recruitment/dashboard.html`](../recruitment/templates/recruitment/dashboard.html)
- [`static/pihrms/auth.css`](../static/pihrms/auth.css)
- [`static/pihrms/dashboard.css`](../static/pihrms/dashboard.css)
- [`templates/403.html`](../templates/403.html)
- [`templates/404.html`](../templates/404.html)
- [`templates/405.html`](../templates/405.html)
- [`templates/dashboard.html`](../templates/dashboard.html)
- [`templates/forgot_password.html`](../templates/forgot_password.html)
- [`templates/initialize_database/horilla_user.html`](../templates/initialize_database/horilla_user.html)
- [`templates/login.html`](../templates/login.html)
- [`templates/no_perm.html`](../templates/no_perm.html)
- [`templates/pihrms/auth_styles.html`](../templates/pihrms/auth_styles.html)
- [`templates/pihrms/dashboard_styles.html`](../templates/pihrms/dashboard_styles.html)
- [`templates/pihrms/sign_in_brand.html`](../templates/pihrms/sign_in_brand.html)
- [`templates/reset_password.html`](../templates/reset_password.html)
- [`templates/reset_send.html`](../templates/reset_send.html)

The next checkpoint is employee management. Begin after approval.
