"""Regression coverage for punch ownership, corrections, and personal date filters."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone as utc_timezone
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.db import connections
from django.http import QueryDict
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.test import override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from attendance.cbv.my_attendances import MyAttendanceList
from attendance.methods.corrections import approve_attendance_correction
from attendance.methods.punches import PunchConflict, request_punch_time
from attendance.models import Attendance, AttendanceActivity, AttendanceOverTime, WorkRecords
from attendance.templatetags.attendancefilters import is_clocked_in
from attendance.views.clock_in_out import (
    clock_in_attendance_and_activity,
    clock_out_attendance_and_activity,
)
from base.models import EmployeeShift, EmployeeShiftDay, EmployeeShiftSchedule
from horilla.horilla_middlewares import set_selected_company
from horilla.testkit import make_company, make_employee, make_user
from horilla_views.cbv_methods import saved_filter_cache_key
from horilla_views.generic.cbv.views import CACHE


LOCAL = ZoneInfo("Asia/Kolkata")
MONDAY = date(2025, 11, 24)


def stamp(hour, minute=0, second=0, day=MONDAY):
    return datetime.combine(day, time(hour, minute, second), tzinfo=LOCAL)


class PunchFixtures:
    def setUp(self):
        super().setUp()
        set_selected_company(None)
        self.addCleanup(set_selected_company, None)
        company = make_company("Punch consistency")
        self.shift = EmployeeShift.objects.create(employee_shift="Day Shift")
        self.shift.company_id.add(company)
        for day in ("sunday", "monday", "tuesday", "friday"):
            weekday, _ = EmployeeShiftDay.objects.get_or_create(day=day)
            EmployeeShiftSchedule.objects.create(
                day=weekday, shift_id=self.shift, start_time=time(9),
                end_time=time(17), minimum_working_hour="08:00",
            ).company_id.add(company)
        self.employee = make_employee(
            company=company, email="punch-employee@test.horilla", shift=self.shift
        )
        self.admin = make_user("punch-approver", is_superuser=True)
        self.approver = make_employee(
            company=company, email="punch-approver@test.horilla", user=self.admin
        )

    def clock_in(self, instant):
        return clock_in_attendance_and_activity(
            self.employee, self.employee.employee_work_info, instant
        )

    def clock_out(self, instant):
        return clock_out_attendance_and_activity(self.employee, instant)

    def request_move(self, record, target, **changes):
        record.refresh_from_db()
        requested = record.serialize()
        requested.update(attendance_date=target.isoformat(), **changes)
        record.requested_data = json.dumps(requested)
        record.is_validate_request = True
        record.save()

    def manager_post(self, url, *args, data=None):
        self.client.force_login(self.admin)
        return self.client.post(reverse(url, args=args), data or {})


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Kolkata")
class PunchConsistencyTests(PunchFixtures, TestCase):
    def test_single_session_and_a_repeat_checkout(self):
        record = self.clock_in(stamp(9, 0, 30))
        self.assertEqual(self.clock_in(stamp(9, 1)).pk, record.pk)
        closed = self.clock_out(stamp(9, 1, 5))
        self.assertEqual(closed.attendance_clock_in, time(9, 0, 30))
        self.assertEqual(closed.attendance_clock_out, time(9, 1, 5))
        self.assertEqual(closed.attendance_worked_hour, "00:00")
        self.assertEqual(closed.get_at_work_from_activities(), 35)
        self.assertIsNone(self.clock_out(stamp(9, 2)))
        self.assertEqual(closed.activities()["count"], 1)
        self.assertEqual(AttendanceActivity.objects.get().clock_out, time(9, 1, 5))

    def test_multiple_sessions_exclude_breaks_and_keep_first_and_last(self):
        record = self.clock_in(stamp(9))
        self.clock_out(stamp(10, 0, 30))
        self.clock_in(stamp(11))
        record.refresh_from_db()
        self.assertEqual(record.attendance_worked_hour, "01:00")
        self.clock_out(stamp(12, 0, 30))
        record.refresh_from_db()
        self.assertEqual(record.attendance_clock_in, time(9))
        self.assertEqual(record.attendance_clock_out, time(12, 0, 30))
        self.assertEqual(record.attendance_worked_hour, "02:01")
        self.assertEqual(record.activities()["count"], 2)

    def test_individual_move_preserves_raw_history_and_isolates_next_session(self):
        record = self.clock_in(stamp(10, 54, 7))
        self.clock_out(stamp(11, 19, 15))
        self.clock_in(stamp(11, 19, 30))
        self.clock_out(stamp(11, 22, 54))
        snapshot = list(AttendanceActivity.objects.order_by("pk").values())
        history_counts = [item.history.count() for item in AttendanceActivity.objects.order_by("pk")]
        corrected_date = MONDAY - timedelta(days=1)
        self.request_move(record, corrected_date)

        response = self.manager_post("approve-validate-attendance-request", record.pk)
        self.assertIn(response.status_code, (200, 302))
        record.refresh_from_db()
        self.assertEqual(record.attendance_date, corrected_date)
        self.assertEqual(record.attendance_day.day, "sunday")
        self.assertEqual(record.attendance_worked_hour, "00:28")
        self.assertTrue(record.history.filter(attendance_date=MONDAY).exists())
        self.assertTrue(record.history.filter(attendance_date=corrected_date).exists())
        self.assertEqual(list(AttendanceActivity.objects.order_by("pk").values()), snapshot)
        self.assertEqual(
            [item.history.count() for item in AttendanceActivity.objects.order_by("pk")],
            history_counts,
        )
        old_work = WorkRecords.objects.get(employee_id=self.employee, date=MONDAY)
        self.assertIsNone(old_work.attendance_id)
        self.assertEqual(old_work.at_work_second, 0)

        new = self.clock_in(stamp(11, 31, 20))
        self.clock_out(stamp(11, 31, 38))
        new.refresh_from_db()
        self.assertNotEqual(new.pk, record.pk)
        self.assertEqual(new.attendance_date, MONDAY)
        self.assertEqual(new.attendance_worked_hour, "00:00")
        self.assertEqual(new.get_at_work_from_activities(), 18)
        self.assertEqual(new.activities()["count"], 1)
        self.assertEqual(AttendanceActivity.objects.count(), 3)

    def test_bulk_approves_safe_move_and_preserves_conflicting_pending_request(self):
        moved = self.clock_in(stamp(9))
        self.clock_out(stamp(10))
        self.request_move(moved, MONDAY - timedelta(days=1))

        tuesday = MONDAY + timedelta(days=1)
        active = self.clock_in(stamp(9, day=tuesday))
        self.request_move(active, MONDAY)
        response = self.manager_post(
            "bulk-approve-attendance-request", data={"ids": json.dumps([moved.pk, active.pk])}
        )
        self.assertEqual(json.loads(response["X-Hlv-Bulk-Result"]), {"done": 1, "failed": 1})
        moved.refresh_from_db()
        active.refresh_from_db()
        self.assertFalse(moved.is_validate_request)
        self.assertTrue(active.is_validate_request)
        self.assertEqual(active.attendance_date, tuesday)
        self.assertIsNone(AttendanceActivity.objects.get(attendance_date=tuesday).clock_out)

    def test_occupied_correction_date_changes_neither_pending_request_nor_punches(self):
        a = self.clock_in(stamp(9))
        self.clock_out(stamp(10))
        tomorrow = MONDAY + timedelta(days=1)
        self.clock_in(stamp(9, day=tomorrow))
        self.clock_out(stamp(10, day=tomorrow))
        self.request_move(a, tomorrow)
        with self.assertRaises(PunchConflict):
            approve_attendance_correction(a.pk, self.approver)
        a.refresh_from_db()
        self.assertTrue(a.is_validate_request)
        self.assertEqual(a.attendance_date, MONDAY)
        self.assertEqual(AttendanceActivity.objects.count(), 2)

    def test_overnight_checkout_uses_open_session_even_when_later_daily_record_exists(self):
        tuesday = MONDAY + timedelta(days=1)
        EmployeeShiftSchedule.objects.filter(shift_id=self.shift, day__day="monday").update(
            start_time=time(22), end_time=time(6), is_night_shift=True
        )
        record = self.clock_in(stamp(22))
        later = Attendance.objects.create(employee_id=self.employee, attendance_date=tuesday)
        with patch.object(timezone, "localdate", return_value=tuesday):
            self.assertTrue(is_clocked_in(self.employee.employee_user_id))
        self.clock_out(stamp(2, day=tuesday).astimezone(utc_timezone.utc))
        record.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(record.attendance_date, MONDAY)
        self.assertEqual(record.attendance_clock_out_date, tuesday)
        self.assertEqual(record.attendance_worked_hour, "04:00")
        self.assertIsNone(later.attendance_clock_out)

    def test_pre_noon_punch_uses_previous_night_schedule_even_if_today_is_a_day_shift(self):
        EmployeeShiftSchedule.objects.filter(shift_id=self.shift, day__day="monday").update(
            start_time=time(22), end_time=time(6), is_night_shift=True
        )
        next_day = MONDAY + timedelta(days=1)
        record = self.clock_in(stamp(1, day=next_day))
        self.clock_out(stamp(6, day=next_day))
        record.refresh_from_db()
        self.assertEqual(record.attendance_date, MONDAY)
        self.assertEqual(record.attendance_clock_in_date, next_day)
        self.assertEqual(record.attendance_worked_hour, "05:00")

    def test_orphan_or_ambiguous_open_punches_are_not_closed(self):
        orphan = AttendanceActivity.objects.create(
            employee_id=self.employee, attendance_date=MONDAY, clock_in_date=MONDAY,
            clock_in=time(9), in_datetime=stamp(9),
        )
        with self.assertRaises(PunchConflict):
            self.clock_out(stamp(10))
        AttendanceActivity.objects.create(
            employee_id=self.employee, attendance_date=MONDAY, clock_in_date=MONDAY,
            clock_in=time(9, 30), in_datetime=stamp(9, 30),
        )
        with self.assertRaises(PunchConflict):
            self.clock_out(stamp(10))
        orphan.refresh_from_db()
        self.assertIsNone(orphan.clock_out)
        self.assertEqual(AttendanceActivity.objects.filter(clock_out__isnull=True).count(), 2)

    def test_ambiguous_minute_precision_legacy_anchor_is_not_guessed(self):
        record = self.clock_in(stamp(9, 0, 20))
        self.clock_out(stamp(9, 0, 25))
        self.clock_in(stamp(9, 0, 40))
        Attendance.objects.filter(pk=record.pk).update(attendance_clock_in=time(9))
        with self.assertRaises(PunchConflict):
            self.clock_out(stamp(9, 1))
        self.assertEqual(AttendanceActivity.objects.filter(clock_out__isnull=True).count(), 1)

    def test_unique_minute_precision_legacy_anchor_can_close(self):
        record = self.clock_in(stamp(9, 2, 19))
        Attendance.objects.filter(pk=record.pk).update(attendance_clock_in=time(9, 2))
        closed = self.clock_out(stamp(9, 3, 20))
        self.assertEqual(closed.pk, record.pk)
        self.assertEqual(closed.attendance_worked_hour, "00:01")
        self.assertEqual(closed.get_at_work_from_activities(), 61)

    def test_approved_manual_summary_without_checkout_does_not_open_a_punch(self):
        record = self.clock_in(stamp(9))
        self.clock_out(stamp(10))
        self.request_move(
            record, MONDAY - timedelta(days=1),
            attendance_clock_out=None, attendance_clock_out_date=None,
        )
        corrected = approve_attendance_correction(record.pk, self.approver)
        self.assertEqual(AttendanceActivity.objects.count(), 1)
        self.assertIsNone(corrected.attendance_clock_out)
        self.assertNotEqual(
            WorkRecords.objects.get(attendance_id=corrected).message, "Currently working",
        )

    def test_legacy_activity_created_by_approval_cannot_be_closed_as_a_live_punch(self):
        record = Attendance.objects.create(
            employee_id=self.employee, attendance_date=MONDAY,
            attendance_clock_in_date=MONDAY, attendance_clock_in=time(9),
            is_validate_request_approved=True,
        )
        activity = AttendanceActivity.objects.create(
            employee_id=self.employee, attendance_date=MONDAY,
            clock_in_date=MONDAY, clock_in=time(9),
        )
        with self.assertRaises(PunchConflict):
            self.clock_out(stamp(10))
        activity.refresh_from_db()
        record.refresh_from_db()
        self.assertIsNone(activity.clock_out)
        self.assertEqual(record.attendance_worked_hour, "00:00")

    def test_same_day_correction_recalculates_overtime_and_clears_stale_early_out(self):
        with patch("attendance.views.clock_in_out.enable_late_come_early_out_tracking",
                   return_value={"tracking": True}):
            record = self.clock_in(stamp(8))
            self.clock_out(stamp(16, 30))
            self.assertTrue(record.late_come_early_out.filter(type="early_out").exists())
            self.request_move(
                record, MONDAY, attendance_clock_out="18:00:00",
                attendance_worked_hour="10:00",
            )
            updated = approve_attendance_correction(record.pk, self.approver)
        self.assertEqual(updated.overtime_second, 7200)
        self.assertFalse(updated.late_come_early_out.filter(type="early_out").exists())
        self.assertEqual(AttendanceActivity.objects.get().clock_out, time(16, 30))
        self.assertEqual(updated.get_at_work_from_activities(), 36000)
        with self.assertRaises(PunchConflict):
            self.clock_in(stamp(18, 30))

    def test_cross_month_move_rebuilds_worked_and_approved_overtime_balances(self):
        friday = date(2025, 10, 31)
        record = self.clock_in(stamp(8, day=friday))
        self.clock_out(stamp(17, day=friday))
        record.refresh_from_db()
        record.attendance_overtime_approve = True
        record.save()
        self.request_move(
            record, date(2025, 11, 1),
            attendance_clock_in_date="2025-11-01",
            attendance_clock_out_date="2025-11-01",
        )
        approve_attendance_correction(record.pk, self.approver)
        accounts = self.employee.employee_overtime.filter(year="2025")
        self.assertEqual(accounts.get(month="october").overtime_second, 0)
        self.assertEqual(accounts.get(month="october").hour_account_second, 0)
        self.assertEqual(accounts.get(month="november").overtime_second, 3600)
        self.assertEqual(AttendanceOverTime.objects.filter(employee_id=self.employee).count(), 2)

    def test_my_attendances_explicit_exact_and_range_override_cached_search(self):
        tuesday = MONDAY + timedelta(days=1)
        mine = [self.clock_in(stamp(9))]
        self.clock_out(stamp(10))
        mine.append(self.clock_in(stamp(9, day=tuesday)))
        self.clock_out(stamp(10, day=tuesday))
        Attendance.objects.create(employee_id=self.approver, attendance_date=MONDAY)
        for query, expected in (
            ({"attendance_date": MONDAY.isoformat()}, [mine[0].pk]),
            ({"attendance_date__gte": MONDAY.isoformat(), "attendance_date__lte": tuesday.isoformat()},
             [item.pk for item in mine]),
        ):
            request = RequestFactory().get(reverse("my-attendance-list"), query)
            request.user = self.employee.employee_user_id
            request.session = type("TestSession", (dict,), {"session_key": "attendance-check"})()
            key = saved_filter_cache_key(request)
            prior = RequestFactory().get(request.path, {**query, "search": "no such employee"})
            prior.session = request.session
            self.assertEqual(saved_filter_cache_key(prior), key)
            CACHE.set(key, {"query_dict": prior.GET})
            self.addCleanup(CACHE.delete, key)
            view = MyAttendanceList()
            view.setup(request)
            self.assertCountEqual(view.get_queryset().values_list("pk", flat=True), expected)

    def test_supplied_punch_time_normalizes_before_selecting_local_date(self):
        instant = datetime(2025, 11, 23, 19, tzinfo=utc_timezone.utc)
        with timezone.override(LOCAL):
            self.assertEqual(request_punch_time(SimpleNamespace(datetime=instant)), stamp(0, 30))
            self.assertEqual(
                request_punch_time(SimpleNamespace(date=MONDAY, time=time(7, 52))),
                stamp(7, 52),
            )

    def test_api_uses_same_punch_and_retries_do_not_create_extra_sessions(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from horilla_api.api_views.attendance import views

        def post(view):
            request = APIRequestFactory().post("/clock/")
            force_authenticate(request, user=self.employee.employee_user_id)
            return view.as_view()(request)

        with (
            patch.object(views, "geofence_denial", return_value=None),
            patch.object(views, "request_punch_time", side_effect=[
                stamp(9), stamp(9, 1), stamp(10), stamp(10, 1)
            ]),
        ):
            self.assertEqual(post(views.ClockInAPIView).status_code, 200)
            self.assertEqual(post(views.ClockInAPIView).status_code, 400)
            self.assertEqual(post(views.ClockOutAPIView).status_code, 200)
            self.assertEqual(post(views.ClockOutAPIView).status_code, 400)
        self.assertEqual(AttendanceActivity.objects.count(), 1)
        self.assertEqual(Attendance.objects.get().attendance_worked_hour, "01:00")


@override_settings(USE_TZ=True, TIME_ZONE="Asia/Kolkata")
class ConcurrentCheckoutTests(PunchFixtures, TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_requests_close_once(self):
        record = self.clock_in(stamp(9))
        barrier = Barrier(2, timeout=10)

        def checkout():
            try:
                barrier.wait()
                closed = self.clock_out(stamp(10))
                return closed.pk if closed is not None else None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(checkout) for _ in range(2)]
            self.assertCountEqual([result.result(timeout=15) for result in results], [record.pk, None])
        record.refresh_from_db()
        self.assertEqual(record.attendance_worked_hour, "01:00")
        self.assertEqual(record.activities()["count"], 1)
