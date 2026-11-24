# PiHRMS design system

Checkpoint 1 specifies a light, indigo-accented workspace for KANPRI TECHNOLOGIES LLP. Use the existing PiHRMS mark and wordmark, Django templates, and local Inter font. The specifications below apply to future implementation.

## Design tokens

| Token | Value | Use |
| --- | --- | --- |
| `--pi-primary` | `#4F46E5` | Primary actions, links, selected icons, focus rings |
| `--pi-primary-hover` | `#4338CA` | Hover and pressed primary actions |
| `--pi-primary-subtle` | `#EEF2FF` | Current navigation, selected rows and chips |
| `--pi-background` | `#F8FAFC` | Workspace background |
| `--pi-surface` | `#FFFFFF` | Cards, navigation, header, forms and overlays |
| `--pi-heading` | `#0F172A` | Titles and KPI values |
| `--pi-text` | `#334155` | Body copy and controls |
| `--pi-muted` | `#64748B` | Secondary text on white or the workspace background |
| `--pi-border` | `#E2E8F0` | Decorative separators and panel boundaries |
| `--pi-control-border` | `#64748B` | Control boundaries when the outline identifies the field |
| `--pi-success` | `#16A34A` | Success icon, indicator, and chart series |
| `--pi-warning` | `#D97706` | Warning icon, indicator, and chart series |
| `--pi-error` | `#DC2626` | Error icon, restrictive action, and validation treatment |
| `--pi-info` | `#0284C7` | Informational indicator |
| Success text / fill | `#166534` / `#DCFCE7` | Approved, present, active |
| Warning text / fill | `#92400E` / `#FEF3C7` | Pending, late, requires review |
| Error text / fill | `#991B1B` / `#FEE2E2` | Rejected, absent, submission error |
| Info text / fill | `#075985` / `#E0F2FE` | Informational or planned |
| Neutral text / fill | `#334155` / `#F1F5F9` | Draft, inactive, unavailable |

Use explicit status labels. On primary-subtle surfaces and tinted selected states, use body or heading text. Approved or warning badges use the darker status foreground. For focus on a filled primary button, use a white gap and indigo outer ring. An outline with `--pi-border` can separate panels, while a field that relies on its boundary uses `--pi-control-border`.

Measured contrast with WCAG sRGB relative luminance, rounded to two decimals.

| Foreground and background | Ratio | Use |
| --- | ---: | --- |
| White on primary, then hover | 6.29:1 / 7.90:1 | Primary button label |
| Heading on white | 17.85:1 | Titles |
| Body on page background | 9.90:1 | Main copy |
| Muted on white, then page background | 4.76:1 / 4.55:1 | Supporting copy |
| Indigo on indigo subtle | 5.62:1 | Active navigation |
| Success, warning, error and info badge pairs | 6.49:1 / 6.37:1 / 6.80:1 / 6.59:1 | Normal badge text |
| White on success, warning and error base fills | 3.30:1 / 3.19:1 / 4.83:1 | Use the semantic badge pairs for normal success and warning text |
| Indigo focus ring on page background | 6.01:1 | Focus indicator |

### Typography, spacing and sizing

| Element | Specification |
| --- | --- |
| Font | Existing local Inter WOFF2, then `system-ui, "Segoe UI", sans-serif`. Use tabular numerals for counts, timers, dates, and currency where aligned. |
| Page title and section heading | 28/36 and 20/28 px, 600 weight. On mobile, page title 24/32 px. |
| Card title and controls | 14–16 px, 600 weight. Body 14/22. Table 13–14/20. Supporting text 12–13/18. KPI 30/36 px, 650–700 weight. |
| Spacing | 4, 8, 12, 16, 20, 24, 32, 40, and 48 px. Use 16 px page gutters on mobile, 24 on tablet, and 32 on desktop. |
| Radius | 8 px compact control, 10 px field or button, 12 px card, 14 px dialog, 16 px larger panel or desktop drawer. |
| Elevation | Panels use a border and `0 1px 2px rgba(15, 23, 42, .06)` where useful. Dropdowns and overlays use `0 8px 24px rgba(15, 23, 42, .10)`. |
| Targets and motion | Aim for 44 px touch targets and check the WCAG 2.2 target-size minimum and exceptions. Desktop controls can be denser while keeping a usable target. Use 120–180 ms opacity or transform transitions. Respect `prefers-reduced-motion` with immediate transitions and static loading feedback. |

## Component specifications

| Component | Layout and states | Existing behavior to preserve |
| --- | --- | --- |
| Sidebar and navigation | The mark and PiHRMS name anchor the desktop sidebar. Group related routes with readable labels. Current link uses an indigo tint and `aria-current="page"`. Expansion is keyboard operable and announces `aria-expanded`. Collapsed desktop icons retain accessible names and show labels at focus or hover. | Keep menu predicates, routes, ordering within existing groups, company context, pin preference, and script selectors. |
| Top header | Put breadcrumbs and page context first, then attendance, notifications, language, company switcher, and profile as space permits. Place existing search in its current supported context. Provide labelled controls when text is visually hidden. | Retain current dynamic breadcrumbs, company switching, actions, menus, and modal targets. Header wrapping keeps Check-In or Check-Out immediately reachable. |
| KPI card | Show label, primary value, and a period or comparison where provided by the existing data. Keep cards compact and equal-height within a row. Show unavailable values with explanatory copy. | Keep role-based metrics, data sources, number and time formatting, and chart controls. |
| Buttons | Use one primary emphasis per action group. Secondary uses outlined or neutral fill, tertiary uses text, destructive uses error coloring. Provide hover, focus, pressed, busy, and disabled states. | Preserve button type, method, submitter names, icon meaning, confirmations, and disabled behavior. Busy states retain width and announce progress. |
| Fields and date controls | Visible labels above controls, associated hint and error text, consistent required indicator, clear focus. Use existing native, date, Select2, checkbox, radio, and switch widgets. | Preserve field names, values, formats, data attributes, validation, uploads, keyboard behavior and initialization after HTMX swaps. |
| Dropdown and autocomplete | Align to its trigger with viewport-aware placement. Support Escape and focus return. Use menu semantics for actions and combobox/listbox semantics for Select2 and equivalents. | Preserve selection, typeahead, search input, permissions, dropdown parent positioning, and options populated by the server. |
| Tables and sort | Use a readable header, restrained separators, compact rows, and aligned tabular figures. Show current sort with a label and `aria-sort` where applicable. Keep overflow inside a labelled scroll container. | Preserve headers, column toggles, sorting, row IDs and selection, actions, inline edits, and exports. |
| Filters and search | Place search and primary filters in a toolbar. On narrow widths, let the toolbar wrap and use a labelled filter drawer. Show active filters as removable chips when the workflow supports it. | Use the existing query parameters, saved filters, submit targets, date controls and clear behavior. |
| Pagination | Display range and total when available. Use labelled previous/next buttons and indicate the current page. On mobile use a compact range and controls. | Preserve page size, current filters, query state, selection behavior, and HTMX targets. |
| Status badge | Use a visible textual state, tinted fill, and optional icon. Common business states follow the semantic token pairs. | Preserve status values, translation labels, approvals and form values. |
| Modal dialog | Use a readable heading, aria-labelled dialog, focus containment while open, Escape where permitted, and focus return. Content scrolls independently on small screens. Keep the action footer reachable. | Reuse modal hosts and HTMX targets. Preserve destructive confirmations, validation, Select2 portal parent, and close policy for busy or critical operations. |
| Drawer | Use a backdrop and named dialog for an exclusive mobile drawer. Desktop side panels can stay in flow when both regions must remain interactive. | Keep request focus and scroll state, browser history behavior, filters and list state. |
| Tabs | Use visibly selected states and maintain accessible focus. Use tab semantics for same-page panels and ordinary links for navigation. | Preserve existing IDs, route names, URL state and lazy HTMX loads. |
| Notifications and toast | Keep count, list, read/unread, permitted dismiss actions and a live region for asynchronous feedback. Use assertive announcements for blocking errors and polite updates for success. | Keep notification routes, unread counts, links, and existing confirmation steps. |
| Charts | Use the checked-in Chart.js setup. Prefer indigo for the primary series and use outlines, labels, or shapes for distinction. Keep legend, time range, and accessible summary or table. | Preserve data requests, formatting, dataset order when meaningful, filters, empty state, and tooltips. |
| Empty, loading and error states | Distinguish empty results, loading, unavailable data and request errors with brief text. Offer an existing clear or retry action where available. Use size-matched placeholders and `aria-busy` on the updated region. | Keep refresh and error paths attached to current handlers. Preserve previously loaded data while asynchronous refresh is in progress when the existing behavior allows it. |
| Employee profile | Use an avatar, preferred display name, designation and a compact fact group. Stack photo and facts on small screens. Group sections into existing tabs or sections. | Use approved avatar fallbacks and preserve field visibility, staff-only details, uploads, section links and permissions. |

## Responsive shell

| Viewport | Navigation and layout |
| --- | --- |
| Mobile, 320–767 px | One-column workspace. A labelled menu button opens the navigation drawer. Header actions can wrap to a second row. Present attendance as an identifiable control even when secondary profile, company, or preference actions use an overflow menu. Cards and forms stack. Contain wide tables in their own scroll regions. |
| Tablet, 768–1023 px | Keep the same explicit menu drawer. Allow two columns for cards or forms when their content reflows without clipping. Let toolbar actions wrap. Use the full content area for tables and report configurators. |
| Desktop, 1024 px and above | Pinned sidebar with a compact mode and a keyboard-accessible pin control. A 248–272 px expanded width and 64–72 px compact width are starting points. Keep the shell suitable for wide tables, reports, and up to four KPI columns depending on content. |

### Mobile navigation interaction

Use one permission-filtered menu instance for the shell. The menu trigger references the navigation container and exposes its open state. On open, move focus to the close control or current destination, lock background scroll, and make background controls inert while the drawer is modal. Support Escape, close control, backdrop, and navigation. On dismissal, restore the trigger focus. After successful navigation, move focus to the new content heading or main region. At the desktop breakpoint, release mobile modal state and restore the existing desktop pin preference. Keep ordinary navigation links and expandable groups keyboard-friendly. Preserve route and company switch state across the transition.

Keep the attendance component in the header in every layout with a single live DOM instance. Preserve `#attendance-activity-container`, the `clock-in` and `clock-out` URLs, HTMX attributes, timer hooks, the existing geolocation branch, and current company eligibility logic. A mobile menu can link to attendance screens using existing permission-filtered links. Check on narrow screens that the clock control is usable without hover and that focus survives a successful swap.

### Accessibility and implementation checks

- Validate keyboard order, skip link, landmarks, heading hierarchy, form labels, focus visibility and focus restoration. Verify sticky headers and overlays leave the active element visible.
- Review reflow at 320 px and browser zoom up to 400%. Wide data tables may scroll within their region. Check touch size, text wrapping, and both left-to-right and right-to-left layouts.
- Verify text, icon, and state contrast against the effective background for company palettes and dark mode. Pair status colors with labels and avoid color-only chart series. Test status announcements and reduced motion.
- Start future integration with an authored, scoped stylesheet via Django static tags after the existing shell styles. Keep existing Tailwind and widget bundles, inline hook targets, permission conditions, uploaded logo behavior and session theme behavior. Use CSS variable fallbacks so older layouts and company palettes can be adopted intentionally.
- Validate shell regions first. Then apply and verify components through actual module views and HTMX swaps. Cover public layouts separately and preserve the output structure of emails and PDFs.

See [the page inventory](PIHRMS_UI_PAGE_INVENTORY.md) for source paths and regression priorities.
