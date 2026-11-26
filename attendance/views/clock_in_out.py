"""
clock_in_out.py

This module is used register endpoints to the check-in check-out functionalities
"""

import ipaddress
import logging
from datetime import datetime, timedelta, timezone as utc_timezone

from django.core import signing
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from attendance.methods.punches import (
    BROWSER_CHECKOUT_SALT,
    PunchConflict,
    active_attendance,
    attendance_sessions,
    local_punch_time,
    lock_punches,
    open_sessions,
    request_punch_time,
    session_end,
    session_start,
    worked_session_seconds,
)
from attendance.methods.utils import (
    browser_clock_setting,
    employee_exists,
    format_time,
    geofence_denial_web,
    get_client_ip,
    shift_schedule_today,
    strtime_seconds,
)
from attendance.models import (
    Attendance,
    AttendanceActivity,
    AttendanceLateComeEarlyOut,
    GraceTime,
)
from attendance.views.views import attendance_validate
from base.context_processors import enable_late_come_early_out_tracking
from base.models import AttendanceAllowedIP, EmployeeShiftDay
from employee.models import EmployeeWorkInformation
from horilla.decorators import hx_request_required, login_required

logger = logging.getLogger(__name__)


def late_come_create(attendance):
    """
    used to create late come report
    args:
        attendance : attendance object
    """

    if AttendanceLateComeEarlyOut.objects.filter(
        type="late_come", attendance_id=attendance
    ).exists():
        late_come_obj = AttendanceLateComeEarlyOut.objects.filter(
            type="late_come", attendance_id=attendance
        ).first()
    else:
        late_come_obj = AttendanceLateComeEarlyOut()

    late_come_obj.type = "late_come"
    late_come_obj.attendance_id = attendance
    late_come_obj.employee_id = attendance.employee_id
    late_come_obj.save()
    return late_come_obj


def late_come(attendance, start_time, end_time, shift):
    """
    this method is used to mark the late check-in  attendance after the shift starts
    args:
        attendance : attendance obj
        start_time : attendance day shift start time
        end_time : attendance day shift end time

    """
    if not shift:
        return
    if not enable_late_come_early_out_tracking(None).get("tracking"):
        return
    now_sec = strtime_seconds(attendance.attendance_clock_in.strftime("%H:%M"))
    mid_day_sec = strtime_seconds("12:00")

    # Checking gracetime allowance before creating late come
    if shift and shift.grace_time_id:
        # checking grace time in shift, it has the higher priority
        if (
            shift.grace_time_id.is_active == True
            and shift.grace_time_id.allowed_clock_in == True
        ):
            # Setting allowance for the check in time
            now_sec -= shift.grace_time_id.allowed_time_in_secs
    # checking default grace time
    elif GraceTime.objects.filter(is_default=True, is_active=True).exists():
        grace_time = GraceTime.objects.filter(
            is_default=True,
            is_active=True,
        ).first()
        # Setting allowance for the check in time if grace allocate for clock in event
        if grace_time.allowed_clock_in:
            now_sec -= grace_time.allowed_time_in_secs
    else:
        pass
    is_late = now_sec > start_time or (start_time > end_time and now_sec < mid_day_sec)
    if is_late:
        late_come_create(attendance)
    else:
        _clear_exception(attendance, "late_come")


def _clear_exception(attendance, kind):
    # An applied penalty remains an auditable decision for HR to review.
    attendance.late_come_early_out.filter(
        type=kind, penaltyaccounts__isnull=True
    ).delete()


def _clock_in_schedule(instant, shift):
    day_date = instant.date()
    if instant.hour < 12 and shift:
        previous = day_date - timedelta(days=1)
        previous_day = EmployeeShiftDay.objects.get(day=previous.strftime("%A").lower())
        minimum, start, end = shift_schedule_today(day=previous_day, shift=shift)
        if start > end:
            return previous, previous_day, minimum, start, end
    day = EmployeeShiftDay.objects.get(day=day_date.strftime("%A").lower())
    minimum, start, end = shift_schedule_today(day=day, shift=shift)
    return day_date, day, minimum, start, end


@transaction.atomic
def clock_in_attendance_and_activity(
    employee, work_info, instant, *, reject_duplicate=False
):
    """Create one open punch, retaining the first check-in and elapsed work."""
    instant = local_punch_time(instant)
    lock_punches(employee)
    active = list(open_sessions(employee).order_by("pk")[:2])
    if active:
        if len(active) != 1:
            raise PunchConflict(_("Multiple open sessions require attendance review."))
        attendance = active_attendance(employee, active[0])
        start = session_start(active[0])
        if (
            start is None
            or instant.astimezone(utc_timezone.utc) < start.astimezone(utc_timezone.utc)
            or instant.date() > attendance.attendance_date + timedelta(days=1)
        ):
            raise PunchConflict(_("The existing open session requires attendance review."))
        if reject_duplicate:
            raise PunchConflict(_("Already clocked-in"))
        return attendance

    shift = work_info.shift_id
    work_date, day, minimum, start, end = _clock_in_schedule(instant, shift)
    rows = list(
        Attendance.objects.filter(employee_id=employee, attendance_date=work_date)[:2]
    )
    if len(rows) > 1:
        raise PunchConflict(_("Multiple daily attendance records require review."))
    if rows:
        attendance = rows[0]
        sessions = list(attendance_sessions(attendance))
        if not sessions or (
            attendance.is_validate_request_approved
            and format_time(worked_session_seconds(sessions)) != attendance.attendance_worked_hour
        ):
            raise PunchConflict(_("The daily attendance needs review before adding another session."))
        ends = (session_end(item) for item in sessions)
        check_in_utc = instant.astimezone(utc_timezone.utc)
        if any(end is None or end.astimezone(utc_timezone.utc) > check_in_utc for end in ends):
            raise PunchConflict(_("Check-in must follow the previous session."))
        attendance.attendance_clock_out = None
        attendance.attendance_clock_out_date = None
    else:
        attendance = Attendance(
            employee_id=employee,
            shift_id=shift,
            work_type_id=work_info.work_type_id,
            attendance_date=work_date,
            attendance_day=day,
            attendance_clock_in=instant.time(),
            attendance_clock_in_date=instant.date(),
            minimum_hour=minimum,
        )
    AttendanceActivity.objects.create(
        employee_id=employee,
        attendance_date=work_date,
        clock_in_date=instant.date(),
        clock_in=instant.time(),
        shift_day=attendance.attendance_day,
        in_datetime=instant,
    )
    attendance.save()
    if rows:
        _clear_exception(attendance, "early_out")
    else:
        late_come(attendance, start_time=start, end_time=end, shift=shift)
    return attendance


@transaction.atomic
def clock_out_attendance_and_activity(employee, instant, *, expected_activity_id=None):
    """Close only the provable open session and update its own daily record."""
    instant = local_punch_time(instant)
    lock_punches(employee)
    sessions = open_sessions(employee).select_for_update(of=("self",)).order_by("pk")
    active = list(sessions[:2])
    if len(active) > 1:
        raise PunchConflict(_("Multiple open sessions require attendance review."))
    if expected_activity_id is not None and (
        not active or active[0].pk != expected_activity_id
    ):
        raise PunchConflict(_("This checkout is no longer current. Refresh attendance and try again."))
    if not active:
        return None  # A previously completed internal/API check-out can be retried.
    activity = active[0]
    attendance = active_attendance(employee, activity)
    started = session_start(activity)
    if started is None:
        raise PunchConflict(_("The open session has no check-in timestamp."))
    started_utc = started.astimezone(utc_timezone.utc)
    if instant.astimezone(utc_timezone.utc) < started_utc:
        raise PunchConflict(_("Check-out cannot be earlier than check-in."))
    if instant.date() > attendance.attendance_date + timedelta(days=1):
        raise PunchConflict(_("The existing open session requires attendance review."))

    sessions = list(attendance_sessions(attendance).exclude(pk=activity.pk))
    ends = (session_end(item) for item in sessions)
    if any(end is None or end.astimezone(utc_timezone.utc) > started_utc for end in ends):
        raise PunchConflict(
            _("The open session overlaps a previous session and requires attendance review.")
        )

    activity.clock_out = instant.time()
    activity.clock_out_date = instant.date()
    activity.out_datetime = instant
    activity.save()
    attendance.attendance_clock_out = instant.time()
    attendance.attendance_clock_out_date = instant.date()
    attendance.attendance_worked_hour = format_time(worked_session_seconds([*sessions, activity]))
    attendance.attendance_validated = attendance_validate(attendance)
    attendance.save()

    if attendance.shift_id:
        next_day = attendance.attendance_date + timedelta(days=1)
        if instant.date() == attendance.attendance_date or (
            attendance.is_night_shift() and instant.date() == next_day and instant.hour < 12
        ):
            _minimum_hour, start, end = shift_schedule_today(
                day=attendance.attendance_day, shift=attendance.shift_id
            )
            early_out(attendance, start, end, attendance.shift_id)
    return attendance


def early_out_create(attendance):
    """
    Used to create early out report
    args:
        attendance : attendance obj
    """
    if AttendanceLateComeEarlyOut.objects.filter(
        type="early_out", attendance_id=attendance
    ).exists():
        late_come_obj = AttendanceLateComeEarlyOut.objects.filter(
            type="early_out", attendance_id=attendance
        ).first()
    else:
        late_come_obj = AttendanceLateComeEarlyOut()
    late_come_obj.type = "early_out"
    late_come_obj.attendance_id = attendance
    late_come_obj.employee_id = attendance.employee_id
    late_come_obj.save()
    return late_come_obj


def early_out(attendance, start_time, end_time, shift):
    """
    This method is used to mark the early check-out attendance before the shift ends
    args:
        attendance : attendance obj
        start_time : attendance day shift start time
        start_end : attendance day shift end time
    """
    if not shift:
        return
    if not enable_late_come_early_out_tracking(None).get("tracking"):
        return

    clock_out_time = attendance.attendance_clock_out
    if isinstance(clock_out_time, str):
        clock_out_time = datetime.strptime(clock_out_time, "%H:%M:%S")

    now_sec = strtime_seconds(clock_out_time.strftime("%H:%M"))
    mid_day_sec = strtime_seconds("12:00")
    # Checking gracetime allowance before creating early out
    if shift and shift.grace_time_id:
        if (
            shift.grace_time_id.is_active == True
            and shift.grace_time_id.allowed_clock_out == True
        ):
            now_sec += shift.grace_time_id.allowed_time_in_secs
    elif GraceTime.objects.filter(is_default=True, is_active=True).exists():
        grace_time = GraceTime.objects.filter(
            is_default=True,
            is_active=True,
        ).first()
        # Setting allowance for the check out time if grace allocate for clock out event
        if grace_time.allowed_clock_out:
            now_sec += grace_time.allowed_time_in_secs
    else:
        pass
    is_early = (
        now_sec >= mid_day_sec or now_sec < end_time
        if start_time > end_time
        else now_sec < end_time
    )
    if is_early:
        early_out_create(attendance)
    else:
        _clear_exception(attendance, "early_out")


def clock_in_from_source(request):
    """Record a trusted internal event from a device or activity import."""
    employee, work_info = employee_exists(request)
    if employee and work_info is not None and employee.is_active and request.user.is_active:
        try:
            return clock_in_attendance_and_activity(employee, work_info, request_punch_time(request))
        except PunchConflict as error:
            logger.warning("Check-in held for employee %s: %s", employee.pk, error.message)


def clock_out_from_source(request):
    """Record a trusted internal event from a device, import or scheduler."""
    employee, work_info = employee_exists(request)
    if employee and work_info is not None and employee.is_active and request.user.is_active:
        try:
            return clock_out_attendance_and_activity(employee, request_punch_time(request))
        except PunchConflict as error:
            logger.warning("Check-out held for employee %s: %s", employee.pk, error.message)


def _browser_punch_policy(request, company):
    attendance_setting = browser_clock_setting(company.pk)
    if attendance_setting is None or not attendance_setting.enable_check_in:
        return _("The attendance check-in/check-out feature has not been enabled for your company.")

    allowed_ips = AttendanceAllowedIP.objects.filter(company_id=company).first()
    if allowed_ips is None:
        allowed_ips = AttendanceAllowedIP.objects.filter(company_id__isnull=True).first()
    if allowed_ips and allowed_ips.is_enabled:
        address = get_client_ip(request)
        for network in (allowed_ips.additional_data or {}).get("allowed_ips", []):
            try:
                if ipaddress.ip_address(address) in ipaddress.ip_network(network, strict=False):
                    break
            except ValueError:
                continue
        else:
            return _("Attendance restricted: Your current network is not authorized.")
    return geofence_denial_web(request, company, coordinates=request.POST)


def _browser_clock_error(message, status):
    return HttpResponse(
        message,
        status=status,
        content_type="text/plain; charset=utf-8",
        headers={"X-Attendance-Error": "true"},
    )


def _browser_clock(request, *, checkout=False):
    employee = request.user.employee_get
    try:
        with transaction.atomic():
            lock_punches(employee)
            employee.refresh_from_db(fields=("employee_user_id", "is_active"))
            if not employee.is_active or employee.employee_user_id_id != request.user.pk:
                return _browser_clock_error(_("Your employee account cannot record attendance."), 403)
            work_info = EmployeeWorkInformation._base_manager.select_for_update().filter(
                employee_id=employee
            ).first()
            company_id = work_info.company_id_id if work_info else None
            selected = request.session.get("selected_company")
            if company_id is None or selected not in ("all", company_id, str(company_id)):
                return _browser_clock_error(_("Select your own company to record attendance."), 403)

            if checkout:
                try:
                    owner, tenant, activity_id = signing.loads(
                        request.POST.get("session_id", ""), salt=BROWSER_CHECKOUT_SALT
                    )
                except signing.BadSignature:
                    return _browser_clock_error(_("A valid checkout session is required."), 400)
                if (owner, tenant) != (employee.pk, company_id):
                    return _browser_clock_error(_("This checkout does not belong to you."), 403)

            denial = _browser_punch_policy(request, work_info.company_id)
            if denial:
                return _browser_clock_error(denial, 403)

            if checkout:
                clock_out_attendance_and_activity(
                    employee, timezone.now(), expected_activity_id=activity_id
                )
            else:
                clock_in_attendance_and_activity(employee, work_info, timezone.now())
    except PunchConflict as error:
        return _browser_clock_error(error.message, 409)

    employee.refresh_from_db()
    return render(request, "attendance/components/in_out_component.html", {"run": 1})


@require_POST
@login_required
@csrf_protect
@hx_request_required
def clock_in(request):
    return _browser_clock(request)


@require_POST
@login_required
@csrf_protect
@hx_request_required
def clock_out(request):
    return _browser_clock(request, checkout=True)
