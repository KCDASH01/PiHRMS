"""
clock_in_out.py

This module is used register endpoints to the check-in check-out functionalities
"""

import ipaddress
import logging
from datetime import datetime, timedelta, timezone as utc_timezone

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from attendance.methods.punches import (
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
    AttendanceGeneralSetting,
    AttendanceLateComeEarlyOut,
    GraceTime,
)
from attendance.views.views import attendance_validate
from base.context_processors import enable_late_come_early_out_tracking
from base.models import AttendanceAllowedIP, Company, EmployeeShiftDay
from horilla.decorators import hx_request_required, login_required
from horilla.http.response import HorillaRedirect

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


@login_required
@hx_request_required
def clock_in(request):
    """
    This method is used to mark the attendance once per a day and multiple attendance activities.
    """
    # check wether check in/check out feature is enabled
    selected_company = request.session.get("selected_company")
    if selected_company == "all":
        company = None
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=None
        ).first()
    else:
        company = Company.objects.filter(id=selected_company).first()
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=company
        ).first()
    # request.__dict__.get("datetime")' used to check if the request is from a biometric device
    if (
        attendance_general_settings
        and attendance_general_settings.enable_check_in
        or request.__dict__.get("datetime")
    ):
        allowed_attendance_ips = AttendanceAllowedIP.objects.filter(
            company_id=company
        ).first()

        if (
            not request.__dict__.get("datetime")
            and allowed_attendance_ips
            and allowed_attendance_ips.is_enabled
        ):
            # get_client_ip() only trusts X-Forwarded-For as far as the
            # deployment's declared proxy count -- taking the client-supplied
            # header at face value let anyone claim to be on the office
            # network.
            ip = get_client_ip(request)

            allowed_ips = (allowed_attendance_ips.additional_data or {}).get(
                "allowed_ips", []
            )
            ip_allowed = False
            for allowed_ip in allowed_ips:
                try:
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(
                        allowed_ip, strict=False
                    ):
                        ip_allowed = True
                        break
                except ValueError:
                    continue

            if not ip_allowed:
                messages.error(
                    request,
                    _("Check-In Restricted: Your current network is not authorized "),
                )
                return HorillaRedirect(request)

        if not request.__dict__.get("datetime"):
            # The mobile/API clock-in already enforces a configured
            # geo-fence; this view didn't, so an employee outside the fence
            # could still punch in from a browser.
            geofence_error = geofence_denial_web(request, company)
            if geofence_error:
                messages.error(request, geofence_error)
                return HorillaRedirect(request)

        employee, work_info = employee_exists(request)
        if employee and work_info is not None:
            try:
                clock_in_attendance_and_activity(employee, work_info, request_punch_time(request))
            except PunchConflict as error:
                if request.__dict__.get("datetime"):
                    logger.warning("Check-in held for employee %s: %s", employee.pk, error.message)
                else:
                    messages.error(request, error.message)
            # Refresh employee from DB so template re-evaluates is_clocked_in correctly
            employee.refresh_from_db()
            return render(
                request, "attendance/components/in_out_component.html", {"run": 1}
            )
        messages.error(
            request,
            _(
                "Check-In Unavailable: Your employee profile or work information is incomplete."
            ),
        )
        return HorillaRedirect(request)
    else:
        messages.error(
            request,
            _(
                "The attendance check-in/check-out feature has not been enabled for your company."
            ),
        )
        return HorillaRedirect(request)


@transaction.atomic
def clock_out_attendance_and_activity(employee, instant):
    """Close only the provable open session and update its own daily record."""
    instant = local_punch_time(instant)
    lock_punches(employee)
    active = list(open_sessions(employee).order_by("pk")[:2])
    if not active:
        return None  # A previously completed check-out can be safely retried.
    if len(active) != 1:
        raise PunchConflict(_("Multiple open sessions require attendance review."))
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


@login_required
@hx_request_required
def clock_out(request):
    """
    This method is used to set the out date and time for attendance and attendance activity
    """
    # check wether check in/check out feature is enabled
    selected_company = request.session.get("selected_company")
    if selected_company == "all":
        company = None
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=None
        ).first()
    else:
        company = Company.objects.filter(id=selected_company).first()
        attendance_general_settings = AttendanceGeneralSetting.objects.filter(
            company_id=company
        ).first()
    if (
        attendance_general_settings
        and attendance_general_settings.enable_check_in
        or request.__dict__.get("datetime")
    ):
        allowed_attendance_ips = AttendanceAllowedIP.objects.filter(
            company_id=company
        ).first()

        if (
            not request.__dict__.get("datetime")
            and allowed_attendance_ips
            and allowed_attendance_ips.is_enabled
        ):
            # get_client_ip() only trusts X-Forwarded-For as far as the
            # deployment's declared proxy count -- taking the client-supplied
            # header at face value let anyone claim to be on the office
            # network.
            ip = get_client_ip(request)

            allowed_ips = (allowed_attendance_ips.additional_data or {}).get(
                "allowed_ips", []
            )
            ip_allowed = False
            for allowed_ip in allowed_ips:
                try:
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(
                        allowed_ip, strict=False
                    ):
                        ip_allowed = True
                        break
                except ValueError:
                    continue

            if not ip_allowed:
                messages.error(
                    request,
                    _("Check-Out Restricted: Your current network is not authorized"),
                )
                return HorillaRedirect(request)

        if not request.__dict__.get("datetime"):
            geofence_error = geofence_denial_web(request, company)
            if geofence_error:
                messages.error(request, geofence_error)
                return HorillaRedirect(request)

        employee, work_info = employee_exists(request)
        if not employee or work_info is None:
            messages.error(request, _("Check-Out Unavailable: Your employee profile or work information is incomplete."))
            return HorillaRedirect(request)
        try:
            clock_out_attendance_and_activity(employee, request_punch_time(request))
        except PunchConflict as error:
            if request.__dict__.get("datetime"):
                logger.warning("Check-out held for employee %s: %s", employee.pk, error.message)
            else:
                messages.error(request, error.message)

        # Refresh employee from DB so template re-evaluates is_clocked_in correctly
        employee.refresh_from_db()
        return render(
            request, "attendance/components/in_out_component.html", {"run": 1}
        )

    else:
        messages.error(
            request,
            _(
                "The attendance check-in/check-out feature has not been enabled for your company."
            ),
        )
        return HorillaRedirect(request)
