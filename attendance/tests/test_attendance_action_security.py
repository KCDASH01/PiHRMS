"""Employee-scoped attendance writes, REST reads, and overtime approval."""

import json
from datetime import date, time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from attendance.models import (
    Attendance, AttendanceActivity, AttendanceLateComeEarlyOut,
    AttendanceOverTime, BatchAttendance, WorkRecords,
)
from base.models import CompanyGroupAssignment, EmployeeShift, EmployeeShiftDay
from employee.models import EmployeeWorkInformation
from horilla.horilla_middlewares import ThreadLocalMiddleware, set_selected_company
from horilla.testkit import make_company, make_employee, make_user
from horilla_api.api_views.attendance.views import (
    AttendanceActivityView, AttendanceView, LateComeEarlyOutView,
)


DAY = date(2025, 11, 24)


@override_settings(COMPANY_SCOPED_PERMISSIONS=True)
class AttendanceActionSecurityTests(TestCase):
    def setUp(self):
        set_selected_company(None)
        self.addCleanup(set_selected_company, None)
        self.company = make_company("Attendance action scope")
        self.other_company = make_company("Other attendance scope", hq=False)
        self.user = make_user("attendance-action-manager")
        self.manager = make_employee(company=self.company, email=self.user.email, user=self.user)
        self.report = make_employee(company=self.company, email="report@attendance.example")
        self.unrelated = make_employee(company=self.company, email="peer@attendance.example")
        self.external = make_employee(company=self.other_company, email="foreign@attendance.example")
        EmployeeWorkInformation.objects.filter(employee_id=self.report).update(
            reporting_manager_id=self.manager
        )
        self.user.refresh_from_db()
        self.shift = EmployeeShift.objects.create(employee_shift="Attendance test shift")
        self.shift.company_id.add(self.company)
        EmployeeShiftDay.objects.get_or_create(day="monday")
        self.client.force_login(self.user)

    def grant(self, company, *codenames):
        group = Group.objects.create(name="Attendance test grant " + str(company.pk))
        group.permissions.set(Permission.objects.filter(
            content_type__app_label="attendance", codename__in=codenames
        ))
        CompanyGroupAssignment.objects.create(user=self.user, company=company, group=group)

    def payload(self, employee, hours="01:00"):
        return {
            "employee_id": employee.pk,
            "shift_id": self.shift.pk,
            "attendance_date": DAY.isoformat(),
            "attendance_clock_in_date": DAY.isoformat(),
            "attendance_clock_out_date": DAY.isoformat(),
            "attendance_clock_in": "09:00",
            "attendance_clock_out": "10:00",
            "attendance_worked_hour": hours,
            "minimum_hour": "00:30",
        }

    def attendance(self, employee):
        return Attendance.objects.create(
            employee_id=employee, attendance_date=DAY, shift_id=self.shift,
            attendance_clock_in_date=DAY, attendance_clock_out_date=DAY,
            attendance_clock_in=time(9), attendance_clock_out=time(10),
            attendance_worked_hour="01:00", minimum_hour="00:30",
        )

    def snapshot(self):
        return [
            list(model.objects.order_by("pk").values())
            for model in (Attendance, AttendanceActivity, AttendanceOverTime, WorkRecords)
        ]

    def api(self, view, verb, data=None, **kwargs):
        request = getattr(APIRequestFactory(), verb)("/attendance/", data or {})
        force_authenticate(request, self.user)
        dispatch = view.as_view()
        return ThreadLocalMiddleware(lambda request: dispatch(request, **kwargs))(request)

    def post(self, name, data=None, *, args=(), query=""):
        return self.client.post(
            reverse(name, args=args) + query, data or {},
            secure=True, HTTP_HX_REQUEST="true",
        )

    def test_manager_can_create_attendance_only_for_an_authorized_employee(self):
        original = self.snapshot()
        denied = self.api(AttendanceView, "post", self.payload(self.unrelated))
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.snapshot(), original)
        response = self.api(AttendanceView, "post", self.payload(self.report))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(Attendance.objects.filter(employee_id=self.report, attendance_date=DAY).exists())

    def test_web_multi_create_rejects_entire_mixed_selection(self):
        original = self.snapshot()
        payload = self.payload(self.report)
        payload["employee_id"] = [self.report.pk, self.unrelated.pk]
        self.post("attendance-create", payload)
        self.assertEqual(self.snapshot(), original)

    def test_web_edit_rejects_unrelated_record_and_unauthorized_transfer(self):
        allowed = self.attendance(self.report)
        denied = self.attendance(self.unrelated)
        original = self.snapshot()
        self.post("attendance-update", self.payload(self.unrelated, "02:00"), args=(denied.pk,))
        self.post("attendance-update", self.payload(self.unrelated, "02:00"), args=(allowed.pk,))
        self.assertEqual(self.snapshot(), original)
        response = self.post(
            "attendance-update", self.payload(self.report, "02:00"), args=(allowed.pk,)
        )
        self.assertEqual(response.status_code, 200)
        allowed.refresh_from_db()
        self.assertEqual(allowed.attendance_worked_hour, "02:00")

    def test_rest_edit_checks_source_and_destination_against_each_company_grant(self):
        home = self.attendance(self.report)
        foreign = self.attendance(self.external)
        self.grant(self.company, "change_attendance")
        self.grant(self.other_company, "view_attendance")
        set_selected_company("all")
        original = self.snapshot()
        original_history_count = Attendance.history.count()
        for forbidden_target, record, employee in (
            ("source", foreign, self.report),
            ("destination", home, self.external),
        ):
            with self.subTest(forbidden_target=forbidden_target):
                response = self.api(
                    AttendanceView, "put", self.payload(employee, "02:00"), pk=record.pk
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.snapshot(), original)
                self.assertEqual(Attendance.history.count(), original_history_count)
        response = self.api(AttendanceView, "put", self.payload(self.report, "02:00"), pk=home.pk)
        self.assertEqual(response.status_code, 200, response.data)
        home.refresh_from_db()
        self.assertEqual(home.attendance_worked_hour, "02:00")

    def test_rest_activity_and_exception_lists_allow_self_and_reports(self):
        for employee in (self.manager, self.report, self.unrelated, self.external):
            record = self.attendance(employee)
            AttendanceActivity.objects.create(
                employee_id=employee, attendance_date=DAY, clock_in_date=DAY, clock_in=time(9)
            )
            AttendanceLateComeEarlyOut.objects.create(attendance_id=record, type="early_out")
        for view in (AttendanceActivityView, LateComeEarlyOutView):
            with self.subTest(view=view.__name__):
                response = self.api(view, "get")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {row["employee_id"] for row in response.data}, {self.manager.pk, self.report.pk}
                )
        self.grant(self.company, "view_attendanceactivity", "view_attendancelatecomeearlyout")
        self.grant(self.other_company, "view_attendance")
        set_selected_company("all")
        for view in (AttendanceActivityView, LateComeEarlyOutView):
            with self.subTest(view=view.__name__):
                response = self.api(view, "get")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {row["employee_id"] for row in response.data},
                    {self.manager.pk, self.report.pk, self.unrelated.pk},
                )

    def test_payroll_attendance_actions_scope_each_target(self):
        denied = self.attendance(self.unrelated)
        allowed = self.attendance(self.report)
        original = self.snapshot()
        for action in ("validate", "approve_ot"):
            self.post("payslip-pending-attendance-action", {"attendance_id": denied.pk, "action": action})
            self.assertEqual(self.snapshot(), original)
        for action in ("validate", "approve_ot"):
            response = self.post(
                "payslip-pending-attendance-action",
                {"attendance_id": allowed.pk, "action": action},
            )
            self.assertEqual(response.status_code, 200)
        allowed.refresh_from_db()
        self.assertTrue(allowed.attendance_validated)
        self.assertTrue(allowed.attendance_overtime_approve)

    def test_overtime_requires_post_csrf_and_authorized_target(self):
        denied = self.attendance(self.unrelated)
        allowed = self.attendance(self.report)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("approve-overtime", args=[allowed.pk])
        original = self.snapshot()
        self.assertEqual(client.get(url, secure=True).status_code, 405)
        self.assertEqual(client.post(url, secure=True, HTTP_REFERER="https://testserver/").status_code, 403)
        self.assertEqual(self.snapshot(), original)

        request = RequestFactory().get("/")
        token = get_token(request)
        client.cookies[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
        headers = {"HTTP_REFERER": "https://testserver/", "HTTP_X_CSRFTOKEN": token,
                   "HTTP_HX_REQUEST": "true"}
        client.post(reverse("approve-overtime", args=[denied.pk]), secure=True, **headers)
        self.assertEqual(self.snapshot(), original)
        with patch("attendance.views.views.notify.send"):
            response = client.post(url, secure=True, **headers)
        self.assertEqual(response.status_code, 200)
        allowed.refresh_from_db()
        self.assertTrue(allowed.attendance_overtime_approve)

    def test_mixed_batch_assignment_makes_no_changes(self):
        report = self.attendance(self.report)
        unrelated = self.attendance(self.unrelated)
        batch = BatchAttendance.objects.create(title="Authorized attendance batch")
        original = self.snapshot()
        self.post(
            "attendance-add-to-batch", {"batch_attendance_id": batch.pk},
            query=f"?ids={json.dumps([report.pk, unrelated.pk])}",
        )
        self.assertEqual(self.snapshot(), original)
