# PiHRMS UI architecture

Checkpoint 0 records the repository and frontend architecture for the KANPRI TECHNOLOGIES LLP redesign. The findings come from the local checkout and its Git metadata.

## Checkout and branding baseline

| Item | Finding |
| --- | --- |
| Branch | `2.0`, tracking local metadata for `origin/2.0` |
| Commit | `6c15617b8297b7a6775daa6c29aefcc48b1eb29f` |
| Version | `horilla/__version__.py` declares `2.4.0`. The same commit carries the `2.4.0` tag and the subject `[REL] Prepare 2.4.0`. |
| Working tree at entry | 29 tracked modifications, two untracked SVGs, zero staged changes |
| PiHRMS asset sources | `static/images/brand/pihrms-logo.svg` and `static/images/brand/pihrms-mark.svg` |

Local tags, newest first by creator date, are `2.4.0`, `2.3.1`, `2.3.0`, `2.2.0`, `2.1.8`, `2.1.7`, `2.1.6`, `2.1.5`, `2.1.4`, `2.1.3`, `2.1.2`, `2.1.1`, `2.1.0`, `2.0.0`, `2.0.0-rc1`, `1.6.1`, `1.6.0`, `1.5.0`, `release/v2.1.0`, `v2.0.0-beta.1`, `1.4.0`, `1.3.2`, `1.3.1`, `1.3`, `1.2.3`, `1.2.2`, `1.2.1`, `1.2.0`, `1.1.0`, and `1.0.0`.

Both sign-in templates use the PiHRMS wordmark as their fallback. Both sidebars use the compact mark when a company image is absent. The changed PNGs supply existing template, email, and document references, and the favicon PNGs and ICO supply browsers and the web app manifest. The branding diff in `base/context_processors.py` changes two fallback strings to PiHRMS. The white-labelling and company selection branches still control when uploaded images take precedence.

### Existing changes to preserve

Paths grouped under a directory below are relative to that directory.

| Directory | Modified paths |
| --- | --- |
| Root and base | `README.md`, `base/context_processors.py` |
| `horilla_theme/templates/` | `base/auth/password_change_form.html`, `base/auth/username_change_form.html`, `forgot_password.html`, `horilla_theme/components/sidebar.html`, `initialize_database/horilla_user.html`, `login.html`, `recruitment/open_recruitments.html`, `reset_password.html` |
| `horilla_theme/static/horilla_theme/assets/img/` | `horilla-logo.png` |
| `recruitment/templates/candidate/` | `self_login.html` |
| `templates/` | `403.html`, `404.html`, `405.html`, `demo_database/animation_load_data.html`, `initialize_database/horilla_user.html`, `login.html`, `reset_send.html`, `sidebar.html` |
| `static/` | `build/manifest.json`, `images/ui/auth-logo.png`, `images/ui/horilla-logo.png` |
| `static/favicons/` | `android-chrome-192x192.png`, `android-chrome-512x512.png`, `apple-touch-icon.png`, `favicon-16x16.png`, `favicon-32x32.png`, `favicon.ico` |

The two SVGs listed above were untracked at entry. The branding changes overlap with the planned shell and authentication work. Use the current working copies as the baseline for those checkpoints.

## Template resolution

The app uses server-rendered Django templates. `requirements.txt` specifies Django `~=5.2.17` and the Dockerfile uses Python 3.12. The base settings select `horilla_theme` and wrap four loaders in Django’s cached loader. Resolution follows this order.

1. `horilla_dbtemplate.loaders.Loader` can supply an active site or global override with language and scheduling rules.
2. The filesystem loader searches `horilla_theme/templates/`.
3. The app-directories loader searches installed apps in order.
4. The filesystem loader searches the root `templates/` directory.

An enumeration of version-controlled HTML under non-static `templates/` directories found **2,158 files**, **1,835 logical template names**, and **323 names present in the theme and at least one other template directory**. Literal inheritance references include 258 to `index.html`, 63 to `settings.html`, five to `master_import/base.html`, three to `admin/base_site.html`, and three to `candidate/application_form_component.html`. These counts describe source files and declarations. A route can render a full document, a partial, or a different template depending on the request.

### Layout and route families

| Family | Source path and selection |
| --- | --- |
| Authenticated theme shell | `horilla_theme/templates/index.html` provides the content and styles blocks, main header, sidebar, shared scripts, messages, and modal targets. Shared includes live in `horilla_theme/templates/horilla_theme/components/`. The header hosts breadcrumbs, the attendance control, notifications, language selection, company switching, system preferences, and profile actions. |
| Root shell | `templates/index.html` is the lower-priority implementation with its own header markup and `templates/sidebar.html`. It loads the legacy stylesheet and script stack. Evaluate it separately if a configuration or layout uses the root implementation. |
| Settings, device preferences, and import | Both `horilla_theme/templates/settings.html` and `templates/settings.html` extend the main shell. Company settings and permissions have their own module fragments. The master import wizard uses `master_import/templates/master_import/base.html`. Theme administration registers under `/theme/`. |
| Main analytics dashboard | `/dashboard/` calls `base.dashboard.main_dashboard_view` and renders the logical name `dashboard.html`, supplied by `templates/dashboard.html` on disk. It inherits the selected `index.html`. `horilla_theme/templates/dashboard/dashboard.html` resolves the different name `dashboard/dashboard.html` used by the recruitment dashboard view. |
| Employee self-service dashboard | `/my-dashboard/` renders `base/templates/base/ess_dashboard.html` inside the main shell. `base/dashboard_roles.py` and `base/ess_dashboard.py` determine home routing and available controls. The analytics view redirects ordinary employees to ESS by default and preserves the explicit analytics switch. |
| Module dashboards and profiles | Employee, attendance, leave, payroll, recruitment, onboarding, offboarding, performance, projects, assets, and helpdesk ship separate templates or dashboard fragments. Trace each URL to its view and exact logical template before styling. Several URL configurations retain both current and legacy entry points. |
| Sign-in and recovery | `/login/` and password recovery use standalone theme and root templates named `login.html`, `forgot_password.html`, and `reset_password.html`. `/accounts/login/` redirects to the configured sign-in. The two-factor view renders `base/auth/two_factor_auth.html`. Change-password and change-username forms have theme and app variants. Setup uses themed and root `initialize_database/horilla_user.html`. |
| Public recruitment and candidate portal | The open recruitments route has theme and recruitment-app variants under `recruitment/open_recruitments.html`. The candidate flows use `recruitment/templates/candidate/` for the application form, sign-in, self-tracking, and success page. The application form uses a standalone candidate layout. |
| External onboarding | Token-based onboarding routes resolve standalone templates under `onboarding/` for user setup, profile and employee details, banking details, and welcome. Theme and app variants coexist. Internal onboarding and offboarding screens use the authenticated layout or async fragments. |
| Errors and alternate surfaces | Root templates supply 403, 404, 405, access-denied, and password-reset confirmation pages. The Django admin at `/admin/` uses a separate admin layout family, including overrides for some administration surfaces. Email and PDF templates ship independently of the interactive web layouts. The tracked `auth/login.html` sits outside the configured filesystem and app-template paths, and no literal Python or template references to that path were found. |

## Module boundaries

The source map combines `INSTALLED_APPS`, the root URL configuration, and routes registered by app startup. It is a starting point for the route and page inventory in Checkpoint 1.

| Area | Apps and entry points to trace |
| --- | --- |
| Core workspace | `base`, `employee`, `horilla_auth`, `horilla_theme`, `notifications`, `horilla_crumbs`, `accessibility`, and `horilla_tour`. These cover account and organization settings, roles and groups, employee directories and profiles, dashboards, and shared navigation. |
| Time and money | `attendance`, `biometric`, `leave`, and `payroll`. Dedicated route families cover records, reviews, overtime, balances, payroll processing, contracts, payslips, and exports. |
| Hiring and lifecycle | `recruitment`, `onboarding`, `offboarding`, and `horilla_documents`. Follow the public candidate portal, internal pipelines and interviews, employee document screens, and approval transitions. |
| Work and support | `pms`, `project`, `asset`, and `helpdesk`. Each combines dashboard and list/detail workflows with module-specific actions. |
| Reporting and shared tooling | `report`, `horilla_widgets`, `horilla_views`, `master_import`, `horilla_audit`, `horilla_automations`, `horilla_backup`, and `horilla_dbtemplate`. These include reporting, saved filters and exports, imports, configuration and history, and template administration. |
| Integrations and opt-ins | `horilla_api`, `horilla_meet`, `horilla_ldap`, and `whatsapp` are in base settings. The checkout also ships `facedetection`, `geofencing`, `outlook_auth`, and `dynamic_fields` outside the default installed-app list. Include screens for these apps in source discovery and record whether the reviewed environment enables them. |

## Shared UI and assets

- **Navigation and permissions.** `horilla/config.py` builds menus from `settings.SIDEBARS`, app `sidebar.py` modules, accessibility callbacks, and Django permissions. Templates add their own conditionals. The themed desktop rail uses `#sidebar`, `#sidebarFlyout`, and `#sidebarPinBtn` plus a saved `sidebarPinned` preference. At widths below 992px the CSS keeps a 4rem icon rail and flyout. The requested mobile drawer is new work.
- **Lists, forms, and overlays.** `horilla_views/templates/generic/` contains generic forms, lists and tables, navigation and filters, cards, tabs, detail and history, kanban, pagination flows, exports, and delete confirmation. The theme overrides many keys under `horilla_theme/templates/generic/`. The shell provides common modal hosts; module-specific modals and SweetAlert2 confirmations also exist.
- **Browser behavior.** HTMX drives partial views and modal content. Alpine handles some state, hyperscript appears in the themed shell, and jQuery and jQuery UI remain in use. Select2 is initialized after HTMX swaps. Chart.js, PivotTable, Summernote, the organization chart, Driver.js, and module calendars carry their own markup and initialization dependencies. Preserve selectors, event hooks, `hx-*` bindings, modal targets, CSRF headers, and focus during styling.
- **Typography and icons.** Inter already ships as a local stylesheet and WOFF2 files under `horilla_theme/static/cdn/googleapi/`. The checkout includes Font Awesome, Material Icons, Ionicons, and theme icon assets. Reuse existing fonts and icons when building the tokens and component patterns.
- **Theme state.** `base/templatetags/horillafilters.py` supplies `get_company` and `get_def_theme` from the theme models. The theme shell combines those values with inline rules, Tailwind classes, `global.css`, `v1_styles.css`, and `dark.css`. Dark mode is session-controlled and has a `toggle-theme/` route. Where the redesign defaults to light mode, preserve the existing appearance preference and test both contexts.

### Build and delivery

| Layer | Source and delivery |
| --- | --- |
| Themed CSS | Authored CSS and JS are under `horilla_theme/static/horilla_theme/assets/`. The checked-in `tailwind.css` and bundled Tailwind scripts are already served by templates. Tailwind configuration is present in `assets/js/tailwind.config.js` and the CSS directives under `horilla_theme/static/cdn/tailwind/css/input.css`. |
| Legacy CSS and JS | `static/src/scss/main.scss` imports component, page, vendor and responsive SCSS, and includes Prepros configuration in its directory. Legacy templates use `static/build/css/style.min.css`, CSS overrides, and `static/build/js/web.frontend.min.js`. `static/src/js/` includes custom headers, footers, and modules. |
| Manifests | `static/build/manifest.json` is the PiHRMS installable web app manifest. `static/build/js/mix-manifest.json` maps two legacy JS filenames. Vendored package manifests exist, but the repository root has no package manifest or lockfile for an app-wide frontend build. |
| Django and Docker | Django discovers root and app static directories. WhiteNoise uses compressed static storage. Docker’s entrypoint collects the checked-in assets, with release tasks that also involve migrations. No frontend rebuild command is defined in the root Makefile or the Docker/CI paths reviewed. |
| Checks | Django tests and coverage are configured in the Makefile and unit-test workflow. The quality workflow runs Ruff, formatting checks and Django checks. Repository tests cover dashboard roles, company icons, template behavior, dark-mode form fields, authentication and several module dashboards. No first-party browser suite was found in the root or CI configuration reviewed. |

## Risks and implementation sequence

| Severity | Finding | Approach for later checkpoints |
| --- | --- | --- |
| High | Database-backed overrides, theme overrides, and standalone pages can deliver different markup from the same-looking filename. | Index pages by URL and resolved template key. Record on-disk variants and verify effective overrides in an authorized runtime. |
| High | Layout and styling selectors double as HTMX, modal, widget, and sidebar hooks. | Keep IDs, permission predicates, form attributes, and event targets stable. Verify asynchronous workflows when runtime access is available. |
| High | Role and company scope alter menu entries, dashboard content, and sensitive routes. | Compare role and company contexts. Keep authorization, dashboard data, and payroll behavior in the current handlers. |
| High | Django is absent from the available Python environment. The baseline audit cannot resolve runtime templates, render the app, or exercise workflows. | Continue with static inventory and design tokens within the current restrictions. Keep runtime status pending until an authorized test environment is available. |
| Medium | Dynamic company palettes, dark mode, legacy SCSS, bundled Tailwind, and inline CSS can produce competing colors and layout rules. | Introduce an authored, scoped stylesheet loaded through Django static tags. Reuse local Inter and add tokens at shared boundaries. Trace style order before replacing rules. |
| Medium | The desktop rail’s mobile breakpoint retains hover and flyout behavior. Tables and dialogs also have module-specific sizing. | Validate the shell first at 320px and up, including touch, keyboard, reduced motion, table scrolling, and modal focus. |
| Medium | Several runtime assets are checked-in bundles with incomplete build instructions. Some legacy and module templates also reference external libraries. | Avoid editing generated bundles with available sources. Keep existing dependency behavior during UI work and trace external dependencies before changing them. |

Checkpoint 1 should map each route, role, fragment, and standalone layout, then define shared tokens and component states. Implement the shell after that inventory. Follow with sign-in and dashboards, then each module and the responsive and regression passes. Record source and runtime evidence separately at each checkpoint.
