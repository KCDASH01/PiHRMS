"""Identify and total sessions using the fields available on legacy attendance rows."""

from datetime import datetime, time, timedelta, timezone as utc_timezone

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


BROWSER_CHECKOUT_SALT = "attendance.browser.checkout"


class PunchConflict(ValidationError):
    """A punch cannot be assigned safely with the available records."""


def local_punch_time(value):
    if timezone.is_naive(value):
        return timezone.make_aware(value)
    return timezone.localtime(value)


def request_punch_time(request):
    supplied_datetime = getattr(request, "datetime", None)
    if supplied_datetime is not None:
        return local_punch_time(supplied_datetime)
    local_now = timezone.localtime()
    supplied_date = getattr(request, "date", None)
    supplied_time = getattr(request, "time", None)
    if supplied_date is not None or supplied_time is not None:
        return local_punch_time(
            datetime.combine(
                supplied_date or local_now.date(), supplied_time or local_now.time()
            )
        )
    return local_now


def lock_punches(employee):
    """Serialize punches and approvals even when a daily row does not yet exist."""
    type(employee)._base_manager.select_for_update().only("pk").get(pk=employee.pk)


def session_start(activity):
    if activity.in_datetime is not None:
        return local_punch_time(activity.in_datetime)
    if activity.clock_in_date is not None and activity.clock_in is not None:
        return local_punch_time(
            datetime.combine(activity.clock_in_date, activity.clock_in)
        )
    return None


def session_end(activity):
    if activity.out_datetime is not None:
        return local_punch_time(activity.out_datetime)
    if activity.clock_out_date is not None and activity.clock_out is not None:
        return local_punch_time(
            datetime.combine(activity.clock_out_date, activity.clock_out)
        )
    return None


def open_sessions(employee):
    return employee.employee_attendance_activities.filter(
        clock_out__isnull=True, clock_out_date__isnull=True, out_datetime__isnull=True
    )


def attendance_sessions(attendance):
    """Use the first punch as the boundary between successive records for a day.

    Older clock-ins stored only minutes on the daily row. Allow a unique
    same-minute match for those rows. A missing or ambiguous anchor proves
    no ownership. Older activity IDs may belong to a row since moved away.
    """
    day = attendance.attendance_clock_in_date
    first = attendance.attendance_clock_in
    activities = attendance.employee_id.employee_attendance_activities.filter(
        attendance_date=attendance.attendance_date
    )
    if day is None or first is None:
        return activities.none()
    if isinstance(first, str):
        try:
            first = time.fromisoformat(first)
        except ValueError:
            return activities.none()
    candidates = activities.filter(clock_in_date=day)
    exact = list(candidates.filter(clock_in=first).order_by("pk")[:2])
    if not exact and first.second == first.microsecond == 0:
        exact = list(
            candidates.filter(
                clock_in__gt=first,
                clock_in__lte=first.replace(second=59, microsecond=999999),
            ).order_by("pk")[:2]
        )
    if len(exact) != 1:
        return activities.none()
    return activities.filter(pk__gte=exact[0].pk)


def worked_session_seconds(sessions, *, open_until=None):
    """Total the union of valid intervals so breaks and duplicates add no time."""
    intervals = []
    for session in sessions:
        start, end = session_start(session), session_end(session)
        if end is None and session.clock_out is None and session.clock_out_date is None:
            end = open_until
        if start is not None and end is not None:
            start = start.astimezone(utc_timezone.utc)
            end = end.astimezone(utc_timezone.utc)
            if end > start:
                intervals.append((start, end))

    worked = timedelta()
    previous_end = None
    for start, end in sorted(intervals):
        if previous_end is not None:
            start = max(start, previous_end)
        if end > start:
            worked += end - start
            previous_end = end
    return int(worked.total_seconds())


def active_attendance(employee, activity):
    from attendance.models import Attendance

    matches = list(
        Attendance.objects.filter(
            employee_id=employee, attendance_date=activity.attendance_date
        ).order_by("pk")[:2]
    )
    if len(matches) != 1:
        raise PunchConflict(_("The open session has no unique daily attendance record."))
    attendance = matches[0]
    if (
        attendance.is_validate_request_approved
        and activity.in_datetime is None
        and activity.shift_day_id is None
    ):
        raise PunchConflict(_("The open activity may be a manual correction and requires review."))
    if (
        attendance.attendance_clock_out is not None
        or attendance.attendance_clock_out_date is not None
        or not attendance_sessions(attendance).filter(pk=activity.pk).exists()
    ):
        raise PunchConflict(_("The open session does not match its daily attendance record."))
    return attendance


def current_open_punch(employee, today):
    """Return the open activity and its daily record for the clock controls."""
    activities = list(open_sessions(employee).order_by("pk")[:2])
    if len(activities) != 1:
        return None
    activity = activities[0]
    if activity.attendance_date not in (today, today - timedelta(days=1)):
        return None
    try:
        return activity, active_attendance(employee, activity)
    except PunchConflict:
        return None


def current_open_attendance(employee, today):
    punch = current_open_punch(employee, today)
    return punch[1] if punch else None
