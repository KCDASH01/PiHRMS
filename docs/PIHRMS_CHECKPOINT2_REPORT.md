# PiHRMS Checkpoint 2 report

Checkpoint 2 implements the shared authenticated shell for the Horilla HR 2.4.0 checkout, branch `2.0`, commit `6c15617b8297b7a6775daa6c29aefcc48b1eb29f`.

## Files changed

| File | Change |
| --- | --- |
| `horilla_theme/templates/index.html` | Loads the shell stylesheet and script, adds a skip link and drawer backdrop, and makes the existing content host a focusable main landmark. |
| `horilla_theme/templates/horilla_theme/components/header.html` | Adds the drawer trigger and breadcrumb landmark, presents the current breadcrumb as the page context, and gives existing header actions accessible names and responsive placement. |
| `horilla_theme/templates/horilla_theme/components/sidebar.html` | Uses the existing menu entries for expanded groups, a compact desktop flyout, and the mobile drawer. Keeps the pin setting, branding and company conditions, dynamic menu refresh and navigation hooks. |
| `horilla_theme/templates/horilla_theme/components/sidebar/top_menu.html` | Gives the existing Dashboard link a name and tooltip that remain available in compact mode. |
| `horilla_theme/static/horilla_theme/assets/css/pihrms-shell.css` | Adds scoped indigo tokens, the sticky header, responsive shell spacing, drawer and flyout styles, and a shared sticky-header offset for the grouped table toolbar. |
| `horilla_theme/static/horilla_theme/assets/js/pihrms-shell.js` | Manages drawer focus, backdrop and Escape dismissal, background interaction, breakpoint changes, and focus after a successful sidebar content swap. |
| `docs/PIHRMS_CHECKPOINT2_REPORT.md` | Records this implementation and verification. |
| `docs/PIHRMS_UI_IMPLEMENTATION_LOG.md` | Appends the Checkpoint 2 entry. |

## Scope and responsive behavior

- At 1024 px and above, the sidebar is 256 px expanded and 72 px compact. The saved `sidebarPinned` preference controls its state. Expanded groups use their existing menu links in place. Compact groups use the existing flyout, which can be opened from the keyboard. The active destination is highlighted and marked with `aria-current`.
- Below 1024 px, one permission-filtered navigation tree becomes a drawer. The hamburger opens it, sets the dialog state and focuses its close control. Escape, the backdrop, and the close control dismiss it and restore trigger focus. A successful sidebar HTMX swap transfers focus to the updated main region. The desktop preference survives resizing.
- The sticky header and scrollable workspace retain their existing content and notification hosts. Breadcrumbs, notification controls and unread count, language, company switcher, profile and quick actions retain the original conditions and targets. The mobile header wraps controls as space requires.
- The shell uses a light workspace, white surfaces, indigo active states and local Inter. Theme switching, existing per-company palette values and uploaded logo precedence remain active. The new light shell accents use PiHRMS tokens while module-level styles still receive their existing theme values.

## Template precedence and prior work

The filesystem candidate for the default authenticated shell is `horilla_theme/templates/index.html`, after the database-backed template loader. The root shell and standalone authentication and public layouts retain their own implementations. The assets added here are loaded only by the themed shell. A database-backed override with different hooks may need separate integration after its contents are reviewed in an authorized runtime.

`docs/.checkpoint1_inventory.py` was a temporary source-inventory generator used to enumerate route declarations, template files and duplicate keys. It was removed at Checkpoint 1 and is absent from the Checkpoint 2 starting tree and Git index.

`horilla_views.views.DynamicView` is a legacy HTMX handler at the slash-delimited `dynamic-path/<str:field>/<str:session_key>/` route. It references `dynamic.html`, for which no checked-in candidate was found. The generic and optional dynamic-field forms point to a different, hyphenated request path, which the generic form view registers at runtime. The shell depends on neither render path. The legacy reference remains an open inventory item pending confirmation of actual usage and any database override. [Legacy view](../horilla_views/views.py#L1135) · [Generic route registration](../horilla_views/generic/cbv/views.py#L2256)

## Attendance and protected behavior

The header still has exactly one `#attendance-activity-container` and includes the existing attendance component under its existing installed-app guard. Both attendance template variants and their actions, routes, data attributes, HTMX targets, timers, and geolocation handling were preserved. Shell CSS makes the existing action text visible on small and touch viewports and keeps the timer visible when supplied. The existing control remains in the header outside the navigation drawer.

The existing sidebar menu loops, module permissions, URL tags, company branches, navbar badge hooks, HTMX targets, and modal IDs were checked. Models, migrations, database settings, backend code, and API contracts are outside the checkpoint diff. No database or running Django service was used.

## Verification

| Check | Status | Evidence |
| --- | --- | --- |
| Template references and DOM hooks | PASS | Compared literal URL and include tags, Django conditions, and existing IDs, HTMX and data attributes for the four changed templates. All literal static and template references resolve to local files. |
| Attendance and branding | PASS | Confirmed the one attendance host and original include. Git showed no changes to attendance templates or handlers. Both PiHRMS SVG hashes match the baseline. |
| Stylesheet and JavaScript parsing | PASS | PostCSS parsed the shell stylesheet. Node checked the new script and template inline JavaScript after removing Django substitutions. |
| Drawer logic | PASS | A Node DOM stub exercised open, focus wrapping and restoration, Escape, backdrop and button dismissal, the desktop breakpoint, and a simulated successful sidebar HTMX swap. |
| Offline visual review | PASS | Edge rendered local shell fixtures at 320, 820, and 1366 px. Reviewed drawer, navigation labels, workspace spacing, and desktop header. Fixed an inherited 45 px rule that clipped expanded menu labels. Fixture screenshots use sample content. |
| Backend and schema source protection | PASS | Git checks found no checkpoint edits to Python code, models, migrations, settings or API paths. The pre-existing PiHRMS fallback name change is the only Python diff from the release. |
| Live PiHRMS rendering, database and functional regression | NOT EXECUTED | The local Python environment lacks Django. The offline browser interaction harness did not produce a reliable complete run. Actual template resolution, HTMX responses, permissions and attendance actions still require an authorized running instance. |

## Remaining verification

- **High:** Render the themed shell with employee, manager, HR, and company-scope variations. Confirm the effective template variants and test authorization and navigation against real responses.
- **High:** Exercise Check-In, Check-Out, timer changes, and optional geolocation in an authorized test environment. Confirm that an HTMX swap updates the single header control.
- **Medium:** Verify mobile keyboard navigation and screen-reader output with real content, including modal stacking, notification panels, filters, calendar dropdowns, dark mode, and tables with long content.
- **Medium:** Confirm whether the legacy `dynamic.html` route is used in the active environment before touching that workflow.

The next checkpoint covers authentication and dashboards. Begin after approval.
