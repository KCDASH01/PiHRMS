# PiHRMS attendance consistency

## Root causes

- Clock-out selected an open activity across the employee's history, summed by that activity's date, and saved to the latest daily attendance row by a different sort. The web view chose a third row for its early-departure schedule lookup. None of these lookups established that the inspected and updated rows represented the same session.
- Individual, bulk and API approval duplicated the correction logic. A date change moved the daily record but left completed punches on the original date. The next daily record for that date then inherited the old punches when clock-out summed the date. Incomplete approvals could also rewrite a punch or create an open activity. The Day-Wise work record and old month's hour balance could remain linked to the moved record.
- Clock endpoints mixed server-local dates and times with Django-local timestamps. The duration helper discarded the seconds on each punch before subtracting. This changed the total across short sessions.
- The My Attendances bounds use an inclusive attendance-date field with an employee-scoped queryset. A separate source-reproducible cache path applied an earlier search term to an explicit date-only request. A search with the same attendance date and a nonmatching search term creates this cache entry because the key treats the search term as volatile. The exact production filter state from November 24 was not available locally.

## Behavior after the change

- A database transaction locks the employee for check-in, check-out and corrections. Check-out requires one open session, the same employee and logical attendance date, and an identifiable first punch on the daily record. A unique minute match supports older summaries that discarded check-in seconds. The first punch separates the current group from earlier punches left by a correction. Missing, ambiguous or inconsistent data leaves all punches intact. Repeated submissions while the same session is open or already closed cannot add duration.
- Completed sessions retain their precise punch timestamps, including overnight checkout dates. The total sums elapsed intervals, excludes breaks, and avoids double-counting overlapping intervals. PiHRMS continues to store daily worked hours in `HH:MM` by truncating the total to whole minutes after the sum. A new 18-second session therefore stores `00:00` and retains the 18 seconds in the original punch timestamps and elapsed-time view. Earlier genuine sessions in the report total 1,712 seconds and stay out of the new daily summary.
- Individual, bulk and API approvals use one service. The approved daily record is saved through the model, which records its history. Raw punch timestamps, logical punch dates, and punch audit entries remain intact. A correction waits for a live session to close and refuses a date move if the target already has a daily record or raw punches. An approved manual summary can remain incomplete without creating an active punch. A later live session requires an identifiable daily group and must not overwrite a conflicting approved total.
- A date move resets only attendance-derived values and the stale attendance reference in the old Day-Wise row, then reapplies existing leave and regularization. The daily model calculates overtime using its existing rules, and month moves rebuild both affected balances from recorded hours and approvals. Early and late indicators use the saved shift and existing grace rules. An indicator with a penalty is retained for HR review.
- Browser, API and biometric-supplied timestamps resolve to the configured local date and time. Elapsed intervals use absolute timestamps. A pre-noon check-in uses the previous day's schedule when that schedule is a night shift. A punch still open past the following local day is held for review.
- My Attendances honors explicit exact-date and inclusive range filters ahead of its saved search. The date fields, query parameters and employee scope remain in use.

## Files changed

| Area | Files |
| --- | --- |
| Punch ownership, time and approval | `attendance/methods/punches.py`, `attendance/methods/corrections.py`, `attendance/methods/utils.py`, `attendance/views/clock_in_out.py`, `attendance/views/requests.py` |
| Daily records and header state | `attendance/models.py`, `attendance/methods/work_record_sync.py`, `attendance/signals.py`, `attendance/templatetags/attendancefilters.py`, `employee/models.py` |
| API and date filters | `horilla_api/api_views/attendance/views.py`, `attendance/cbv/my_attendances.py`, `horilla_views/generic/cbv/views.py` |
| Tests and report | `attendance/tests/test_punch_consistency.py`, `docs/PIHRMS_ATTENDANCE_CONSISTENCY_REPORT.md` |

## Verification and open risks

| Check | Result |
| --- | --- |
| Python compilation and patch | All 14 changed Python files compiled. `git diff --check` passed. |
| Standalone checks | 11 assertions passed against the actual punch helper with an in-memory row adapter and a fixed local timezone. They checked numeric totals, date ownership, orphan isolation, legacy minute matching and ambiguity, overlap and invalid interval handling, overnight and open duration, and timestamp conversion. These checks did not use Django or a database. |
| Django integration tests | 18 regression tests were added. They cover single and multiple sessions, breaks and rounding, individual and bulk approvals, the reported reproduction, audit preservation, Day-Wise cleanup, overnight and stale/missing/ambiguous data, API retries, exact and range filters with caching, overtime and early out, and concurrent clock-out. The local Python environment lacks Django. The integration tests and PostgreSQL row-lock behavior remain unverified. |
| Scope | Checked that unrelated functions in the touched attendance request and API modules retain their original definitions. No schema files or database connection settings changed. |

The schema has no activity-to-daily foreign key. Rows that lack an identifiable first punch, have duplicate or partially entered historical punches, or have corrections in conflict with a live session may require manual review. An explicit activity-to-daily link would need a separately approved migration and a policy for historical associations. No migration was created or run for this fix. Existing suspect records were left as found.

## Staging verification plan

1. Run the focused suite on a disposable test database using the staging PostgreSQL engine and the application timezone. Verify that both concurrent workers finish and that exactly one updates the punch.
2. With synthetic employees and shifts, repeat the two original sessions, approve the move to the preceding day, and record the 18-second session. Compare the raw punch timestamps and audit entries with My Attendances, Day-Wise and the hour accounts. Repeat through bulk approval and cover a cross-month move and a pre-noon night-shift check-in.
3. Verify browser HTMX, API and authorized biometric check-in and check-out, a repeated submission, and error handling for an open session without a matching daily record. Check company and employee visibility, exact and range filters after a saved search, grace time, overtime and retained penalties.
4. Review any historical discrepancies separately with the attendance owner before approving a data repair.

Work was local. No commit, push, pull, merge, deployment, staging or production access, live database modification, or historical repair occurred.
