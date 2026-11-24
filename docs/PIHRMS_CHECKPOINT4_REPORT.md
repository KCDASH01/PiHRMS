# PiHRMS Checkpoint 4 — Employee management

Updated the employee directory, employee and self-service profiles, creation and editing forms, document workflows, and organization settings with PiHRMS styling. The local checkout remains on Horilla HR 2.4.0.

## Discovery and template precedence

The review covered **206 employee and organization templates**. This count includes 151 under `employee/templates`, 46 same-name theme overrides, and 9 templates under the department, job position, and job role settings directories. It includes legacy and fallback candidates. Shared shell and generic component dependencies were reviewed separately. The route review covered 233 static name declarations in `employee/urls.py`, the related settings paths in `base/urls.py`, and the view-generated generic routes and tabs used by the screens below. The page inventory records the broader route-to-template mapping. [UI page inventory](PIHRMS_UI_PAGE_INVENTORY.md)

The configured loader checks database templates first, followed by the bundled theme, app templates, and the root fallback. The changes cover checked-in theme and app candidates where relevant. Database-supplied templates could affect the rendered result. [UI architecture](PIHRMS_UI_ARCHITECTURE.md)

| Workflow | Checked-in entry points and dependencies |
| --- | --- |
| Directory | `employee-view`, `employees-nav`, the list and card endpoints, the generic nav and table widgets, and employee actions and import/export scripts. Search, filters, selection, grouping, list/grid switching, sort, pagination, export, and permission-dependent actions use their existing bindings. Cards show the existing avatar, presence indicator, name, designation, department and archive state. |
| Employee and self-service profiles | The employee detail and self-profile entry points use the existing generic profile renderer. Existing access checks govern personal, work, documents, history, and related-record tabs and profile actions. The history filter and before/after values keep their existing endpoint and data bindings. |
| Create, edit, and employee settings | Theme and fallback forms, the HTMX edit fragment, and active themed personal, work and bank sections use the existing forms, validators, CSRF tokens, conditional fields, date and file inputs, and save/cancel actions. The policy, disciplinary, allocations and employee settings screens receive scoped component styling. |
| Documents | The request pipeline, employee document tab, document lists and upload form retain their status predicates, request categories, upload and file endpoints, preview/download controls, approval actions and permissions. The grouped view keeps its shared header and records in a locally scrolling region on narrow layouts. |
| Organization and onboarding links | Department, job position and job role settings keep their existing generic view endpoints. The chart, grouping, reporting manager details, and existing onboarding-related navigation keep their relationships and links. |

## Shared components and accessibility

The employee stylesheet consumes the shared PiHRMS palette and local Inter font. It styles adaptable directory cards, header surfaces, focus outlines, profile tabs, form sections, file input controls, document rows, scroll regions, and small-screen dialogs. It reuses the generic nav, card, table, paginator, quick actions, profile tabs, loading/empty states, and modal behaviors. The card template uses the employee variant for the native profile link and keyboard-operable actions. The generic dropdown handler extends its selector to include the employee trigger. The chart and grouped document region have accessible names.

## Verification

| Check | Result |
| --- | --- |
| Offline Edge fixture | Passed at **320 × 568, 375 × 667, 667 × 375, 768 × 1024, 1024 × 768, 1366 × 768 and 1600 × 900**. The fixture used the bundled theme and shell CSS with representative employee markup. Checks covered page overflow, card and form grids, tab bounds, local list and grouped-document scrolling, document header alignment and narrow stacking, history reflow, modal bounds, and visible keyboard focus. |
| Template structure and references | Balanced Django template blocks in all changed templates. Verified literal template, static and URL references against the checkout. Verified the new stylesheet reference. |
| Workflow source parity | Checked original route, include, permission and condition tags, forms, CSRF markers, record bindings, names, IDs, data and HTMX hooks, and embedded scripts across all 37 edited templates. The card drop-down selector extension is the only change to an original embedded script. |
| Protected scope | Compared pre-existing worktree files byte-for-byte before the implementation log update. The 77 files checked included the shell, authentication and dashboards. Checkpoint 4 changes consist of employee-facing templates, scoped CSS and documentation. Models, migrations and all backend source match the pre-checkpoint worktree. |
| Styles and patch | PostCSS parsing and `git diff --check` passed. |

Visually inspected the offline directory and profile fixture at 375 and 810 px for card stacking, text wrap, spacing, and column alignment.

## Runtime limitations and remaining risks

Django is unavailable in the local Python environment. The offline checks used representative markup, so runtime template compilation, database overrides, role and company isolation, search and filter exchanges, company settings, employee creation and editing, document upload/preview/approval, and the chart's live data and interactions remain unverified. Production data, physical devices, and screen-reader behavior were outside this run. The legacy `dynamic.html` lookup remains a separate inventory item. [Checkpoint 2 report](PIHRMS_CHECKPOINT2_REPORT.md)

## Changed files

**37 existing templates modified**

- `base/templates/base/department/department.html`
- `base/templates/base/job_position/job_position.html`
- `base/templates/base/job_role/job_role.html`
- `employee/templates/cbv/allocations/allocations.html`
- `employee/templates/cbv/disciplinary_actions/disciplinary_actions.html`
- `employee/templates/cbv/documents/document_list.html`
- `employee/templates/cbv/documents/inherit_form.html`
- `employee/templates/cbv/documents/pipeline.html`
- `employee/templates/cbv/employees_view/card_body.html`
- `employee/templates/cbv/employees_view/view_employees.html`
- `employee/templates/cbv/profile/profile_view.html`
- `employee/templates/documents/document_requests.html`
- `employee/templates/employee/create_form/form_view.html`
- `employee/templates/employee/profile/profile.html`
- `employee/templates/employee/profile/profile_view.html`
- `employee/templates/employee/update_form/form_view.html`
- `employee/templates/employee/update_form/form_view_fragment.html`
- `employee/templates/employee/view/individual.html`
- `employee/templates/employee_personal_info/employee_view.html`
- `employee/templates/organisation_chart/org_chart.html`
- `employee/templates/policies/view_policies.html`
- `horilla_theme/templates/cbv/documents/document_list.html`
- `horilla_theme/templates/documents/document_requests.html`
- `horilla_theme/templates/employee/create_form/form_view.html`
- `horilla_theme/templates/employee/create_form/personal_info.html`
- `horilla_theme/templates/employee/update_form/bank_details.html`
- `horilla_theme/templates/employee/update_form/form_view.html`
- `horilla_theme/templates/employee/update_form/form_view_fragment.html`
- `horilla_theme/templates/employee/update_form/personal_info.html`
- `horilla_theme/templates/employee/update_form/work_details.html`
- `horilla_theme/templates/employee/view/individual.html`
- `horilla_theme/templates/employee_settings/employee_settings.html`
- `horilla_theme/templates/generic/horilla_card.html`
- `horilla_theme/templates/organisation_chart/chart.html`
- `horilla_theme/templates/organisation_chart/org_chart.html`
- `horilla_theme/templates/tabs/document_tab.html`
- `horilla_theme/templates/tabs/personal_tab.html`

**Two new frontend files**

- `static/pihrms/employee.css`
- `templates/pihrms/employee_styles.html`

**Documentation**

- `docs/PIHRMS_CHECKPOINT4_REPORT.md`
- `docs/PIHRMS_UI_IMPLEMENTATION_LOG.md`

Checkpoint 5 covers Attendance and Leave Management and awaits approval.
