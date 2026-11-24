"""Apply an approved correction to the daily record and leave raw punches intact."""

import copy
import json

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from attendance.methods.punches import PunchConflict, lock_punches, open_sessions
from attendance.methods.utils import month_date_range, shift_schedule_today
from attendance.methods.work_record_sync import detach_moved_attendance
from attendance.models import Attendance, AttendanceOverTime
from attendance.views.clock_in_out import _clear_exception, early_out, late_come
from base.models import EmployeeShiftDay


def _apply_requested_fields(attendance):
    data = attendance.requested_data
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as exc:
            raise PunchConflict(_("The saved attendance correction is invalid.")) from exc
    if data is None:
        return
    if not isinstance(data, dict):
        raise PunchConflict(_("The saved attendance correction is invalid."))
    if "employee_id" in data and str(data["employee_id"]) != str(attendance.employee_id_id):
        raise PunchConflict(_("An attendance correction cannot change the employee."))

    for key in (attendance.serialize().keys() & data.keys()) - {"employee_id"}:
        field = Attendance._meta.get_field(key)
        value = data[key]
        if field.null and value in ("None", "", None):
            value = None
        if field.is_relation:
            value = field.target_field.to_python(value)
        else:
            value = field.to_python(value)
        setattr(attendance, field.attname, value)


def _rebuild_month(attendance, *, rebuild_overtime):
    account, _created = AttendanceOverTime.objects.get_or_create(
        employee_id=attendance.employee_id,
        month=attendance.attendance_date.strftime("%B").lower(),
        year=attendance.attendance_date.year,
    )
    if rebuild_overtime:
        first, last = month_date_range(
            attendance.attendance_date.year, attendance.attendance_date.month
        )
        account.overtime_second = Attendance.objects.filter(
            employee_id=attendance.employee_id,
            attendance_date__range=(first, last),
            attendance_overtime_approve=True,
        ).aggregate(total=Sum("approved_overtime_second"))["total"] or 0
    attendance.update_ot(account)


@transaction.atomic
def approve_attendance_correction(attendance_id, approver):
    """Approve the pending version once under the same lock as the punch flow."""
    original = Attendance.objects.filter(pk=attendance_id).first()
    if original is None:
        return None
    employee = original.employee_id
    lock_punches(employee)
    attendance = Attendance.objects.select_for_update(of=("self",)).filter(
        pk=attendance_id, employee_id=employee, is_validate_request=True
    ).first()
    if attendance is None:
        return None

    previous = copy.copy(attendance)
    try:
        _apply_requested_fields(attendance)
        if attendance.attendance_date is None:
            raise ValidationError(_("An attendance correction requires an attendance date."))
        if not attendance.attendance_worked_hour or not attendance.minimum_hour:
            raise ValidationError(_("An attendance correction requires valid worked and minimum hours."))
        attendance.clean()
    except ValidationError as exc:
        raise PunchConflict(exc.messages[0]) from exc

    dates = (previous.attendance_date, attendance.attendance_date)
    if open_sessions(employee).filter(attendance_date__in=dates).exists():
        raise PunchConflict(_("Close the open session before approving this correction."))

    moved = dates[0] != dates[1]
    if moved and (
        Attendance.objects.filter(employee_id=employee, attendance_date=dates[1]).exists()
        or employee.employee_attendance_activities.filter(attendance_date=dates[1]).exists()
    ):
        raise PunchConflict(_("The corrected date already has an attendance record or punches."))

    if moved or not attendance.attendance_day_id:
        attendance.attendance_day = EmployeeShiftDay.objects.get(
            day=attendance.attendance_date.strftime("%A").lower()
        )
    attendance.attendance_validated = True
    attendance.is_validate_request_approved = True
    attendance.is_validate_request = False
    attendance.request_description = None
    attendance.approved_by = approver
    if attendance.request_type == "create_request":
        attendance.request_type = "created_request"
        attendance.requested_data = None
    try:
        with transaction.atomic():
            attendance.save()
    except IntegrityError as exc:
        if moved and Attendance.objects.filter(
            employee_id=employee, attendance_date=dates[1]
        ).exclude(pk=attendance.pk).exists():
            raise PunchConflict(_("The corrected date already has an attendance record.")) from exc
        raise

    shift = attendance.shift_id
    _, start, end = shift_schedule_today(attendance.attendance_day, shift)
    if attendance.attendance_clock_in is not None:
        late_come(attendance, start, end, shift)
    else:
        _clear_exception(attendance, "late_come")
    if attendance.attendance_clock_out is not None:
        early_out(attendance, start, end, shift)
    else:
        _clear_exception(attendance, "early_out")

    cross_month = (dates[0].year, dates[0].month) != (dates[1].year, dates[1].month)
    if moved:
        detach_moved_attendance(previous)
    if cross_month:
        _rebuild_month(previous, rebuild_overtime=True)
    _rebuild_month(attendance, rebuild_overtime=cross_month)
    return attendance
