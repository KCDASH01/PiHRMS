"""Record-level request authorization and source punch retention."""

import json
from datetime import date, time
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from attendance.methods.corrections import approve_attendance_correction
from attendance.methods.request_access import can_access_request_employee
from attendance.models import (
    Attendance,
    AttendanceActivity,
    AttendanceLateComeEarlyOut,
    AttendanceRequestComment,
)
from base.models import CompanyGroupAssignment, EmployeeShiftDay
from employee.models import EmployeeWorkInformation
from horilla.horilla_middlewares import set_selected_company
from horilla.testkit import make_company, make_employee, make_user
from horilla_views.generic.cbv.views import HorillaFormView


DAY = date(2025, 11, 24)


@override_settings(SECURE_SSL_REDIRECT=True, COMPANY_SCOPED_PERMISSIONS=False)
class AttendanceRequestAuthorizationTests(TestCase):
    def setUp(self):
        set_selected_company(None)
        self.addCleanup(set_selected_company, None)
        self.company = make_company("Request security")
        self.manager_user = make_user("request-security-manager")
        self.manager = make_employee(
            company=self.company,
            email="request-security-manager@test.horilla",
            user=self.manager_user,
        )
        self.report = make_employee(
            company=self.company, email="request-security-report@test.horilla"
        )
        self.other = make_employee(
            company=self.company, email="request-security-other@test.horilla"
        )
        EmployeeWorkInformation.objects.filter(employee_id=self.report).update(
            reporting_manager_id=self.manager
        )
        self.report.refresh_from_db()
        EmployeeShiftDay.objects.get_or_create(day="monday")
        self.client.force_login(self.manager_user)

    def attendance(self, employee, *, pending=True):
        return Attendance.objects.create(
            employee_id=employee,
            attendance_date=DAY,
            attendance_clock_in_date=DAY,
            attendance_clock_in=time(9),
            attendance_clock_out_date=DAY,
            attendance_clock_out=time(10),
            attendance_worked_hour="01:00",
            is_validate_request=pending,
        )

    def post(self, name, record=None, **data):
        path = reverse(name, args=[record.pk] if record is not None else [])
        return self.client.post(path, data, secure=True, HTTP_HX_REQUEST="true")

    def assert_pending(self, record):
        record.refresh_from_db()
        self.assertTrue(record.is_validate_request)
        self.assertFalse(record.is_validate_request_approved)
        self.assertIsNone(record.approved_by_id)

    def test_manager_cannot_approve_another_teams_request(self):
        record = self.attendance(self.other)
        self.post("approve-validate-attendance-request", record)
        self.assert_pending(record)

    def test_manager_cannot_cancel_or_bulk_reject_another_teams_request(self):
        record = self.attendance(self.other)
        self.post("cancel-validate-attendance-request", record)
        self.assert_pending(record)
        response = self.post(
            "bulk-reject-attendance-request", ids=json.dumps([record.pk])
        )
        self.assertEqual(json.loads(response["X-Hlv-Bulk-Result"]), {"done": 0, "failed": 1})
        self.assert_pending(record)

    def test_owner_cannot_approve_own_request_but_can_withdraw_it(self):
        record = self.attendance(self.manager)
        self.post("approve-validate-attendance-request", record)
        self.assert_pending(record)
        self.post("cancel-validate-attendance-request", record)
        record.refresh_from_db()
        self.assertFalse(record.is_validate_request)
        self.assertFalse(record.is_validate_request_approved)

    def test_bulk_approval_counts_only_authorized_records(self):
        report = self.attendance(self.report)
        other = self.attendance(self.other)
        response = self.post(
            "bulk-approve-attendance-request",
            ids=json.dumps([report.pk, other.pk, report.pk]),
        )
        self.assertEqual(response.status_code, 200, response.get("Location"))
        self.assertEqual(json.loads(response["X-Hlv-Bulk-Result"]), {"done": 1, "failed": 1})
        report.refresh_from_db()
        self.assertTrue(report.is_validate_request_approved)
        self.assertEqual(report.approved_by_id, self.manager.pk)
        self.assert_pending(other)

    def test_manager_cannot_comment_on_another_teams_request(self):
        record = self.attendance(self.other)
        self.post("attendance-request-add-comment", record, comment="Out of team")
        self.assertFalse(AttendanceRequestComment.objects.filter(request_id=record).exists())

    def test_api_cancellation_denies_an_out_of_scope_record(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from horilla_api.api_views.attendance.views import AttendanceRequestCancelView

        record = self.attendance(self.other)
        request = APIRequestFactory().put("/")
        force_authenticate(request, user=self.manager_user)
        response = AttendanceRequestCancelView.as_view()(request, pk=record.pk)
        self.assertEqual(response.status_code, 403)
        self.assert_pending(record)

    @override_settings(COMPANY_SCOPED_PERMISSIONS=True)
    def test_reporting_relationship_cannot_cross_an_unassigned_company(self):
        outside = make_employee(
            company=make_company("Outside company", hq=False),
            email="request-security-outside@test.horilla",
        )
        EmployeeWorkInformation.objects.filter(employee_id=outside).update(
            reporting_manager_id=self.manager
        )
        outside.refresh_from_db()
        # The fixture updates work info after linking the user and employee.
        self.manager_user.refresh_from_db()
        self.assertEqual(
            self.manager_user.employee_get.employee_work_info.company_id_id,
            self.company.pk,
        )
        self.assertEqual(
            self.report.employee_work_info.reporting_manager_id_id, self.manager.pk
        )
        self.assertEqual(
            outside.employee_work_info.reporting_manager_id_id, self.manager.pk
        )
        request = RequestFactory().post("/")
        request.user = self.manager_user
        self.assertTrue(
            can_access_request_employee(request, self.report, "attendance.change_attendance")
        )
        self.assertFalse(
            can_access_request_employee(request, outside, "attendance.change_attendance")
        )

    @override_settings(COMPANY_SCOPED_PERMISSIONS=True)
    def test_all_companies_does_not_union_write_grants_for_a_target(self):
        outside_company = make_company("Assigned outside company", hq=False)
        outside = make_employee(
            company=outside_company, email="request-security-assigned@test.horilla"
        )
        writer = Group.objects.create(name="Attendance request home writer")
        reader = Group.objects.create(name="Attendance request outside reader")
        writer.permissions.add(
            Permission.objects.get(content_type__app_label="attendance", codename="change_attendance")
        )
        CompanyGroupAssignment.objects.create(
            user=self.manager_user, company=self.company, group=writer
        )
        CompanyGroupAssignment.objects.create(
            user=self.manager_user, company=outside_company, group=reader
        )
        set_selected_company("all")
        request = RequestFactory().post("/")
        request.user = self.manager_user
        self.assertTrue(
            can_access_request_employee(request, self.other, "attendance.change_attendance")
        )
        self.assertFalse(
            can_access_request_employee(request, outside, "attendance.change_attendance")
        )

    def test_protected_daily_deletion_preserves_rows_and_punch_history(self):
        record = self.attendance(self.report, pending=False)
        punch = AttendanceActivity.objects.create(
            employee_id=self.report, attendance_date=DAY,
            clock_in_date=DAY, clock_in=time(9),
            clock_out_date=DAY, clock_out=time(10),
        )
        exception = AttendanceLateComeEarlyOut.objects.create(
            attendance_id=record, type="early_out"
        )
        exception.refresh_from_db()
        self.assertEqual(exception.employee_id_id, self.report.pk)
        original = AttendanceActivity.objects.values().get(pk=punch.pk)
        original_history = punch.history.count()
        with self.assertRaises(ProtectedError):
            record.delete()
        self.assertTrue(Attendance.objects.filter(pk=record.pk).exists())
        self.assertEqual(AttendanceActivity.objects.values().get(pk=punch.pk), original)
        self.assertEqual(punch.history.count(), original_history)

    def test_successful_summary_deletion_does_not_delete_its_punch(self):
        record = self.attendance(self.report, pending=False)
        record_pk = record.pk
        punch = AttendanceActivity.objects.create(
            employee_id=self.report, attendance_date=DAY,
            clock_in_date=DAY, clock_in=time(9),
            clock_out_date=DAY, clock_out=time(10),
        )
        record.delete()
        self.assertFalse(Attendance.objects.filter(pk=record_pk).exists())
        self.assertTrue(AttendanceActivity.objects.filter(pk=punch.pk).exists())

    def test_web_creation_passes_authorized_employee_to_form(self):
        with patch.object(HorillaFormView, "dispatch", return_value=HttpResponse()) as dispatch:
            self.post("request-new-attendance", employee_id=str(self.report.pk))
            dispatch.assert_called_once()
            self.post("request-new-attendance", employee_id="invalid")
            dispatch.assert_called_once()

    def test_api_creation_passes_authorized_employee_to_form(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from horilla_api.api_views.attendance.views import AttendanceRequestView

        request = APIRequestFactory().post("/", {"employee_id": self.report.pk})
        force_authenticate(request, user=self.manager_user)
        with patch("attendance.forms.NewRequestForm") as form:
            form.return_value.is_valid.return_value = False
            form.return_value.errors = {"attendance_date": ["Required"]}
            response = AttendanceRequestView.as_view()(request)
        form.assert_called_once()
        self.assertEqual(response.status_code, 404)

    def test_approval_rechecks_target_after_initial_scope_check(self):
        record = self.attendance(self.report)

        def with_changed_owner(attendance_id, approver, **kwargs):
            # Simulate a competing owner change before the service acquires locks.
            Attendance.objects.filter(pk=attendance_id).update(employee_id=self.other)
            return approve_attendance_correction(attendance_id, approver, **kwargs)

        with patch(
            "attendance.views.requests.approve_attendance_correction",
            side_effect=with_changed_owner,
        ) as service:
            self.post("approve-validate-attendance-request", record)
        service.assert_called_once()
        self.assert_pending(record)

    def test_approval_post_without_csrf_token_is_rejected(self):
        record = self.attendance(self.report)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager_user)
        response = client.post(
            reverse("approve-validate-attendance-request", args=[record.pk]),
            secure=True,
            HTTP_HX_REQUEST="true",
            HTTP_REFERER="https://testserver/",
        )
        self.assertEqual(response.status_code, 403)
        self.assert_pending(record)
