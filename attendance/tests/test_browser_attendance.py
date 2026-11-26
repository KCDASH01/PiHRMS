"""Browser punch security and exact activity checkout coverage."""

import re
from unittest.mock import patch

from django.conf import settings
from django.core import signing
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from attendance.methods.punches import BROWSER_CHECKOUT_SALT
from attendance.models import Attendance, AttendanceActivity, WorkRecords
from attendance.tests.test_punch_consistency import PunchFixtures, stamp
from employee.models import EmployeeWorkInformation
from geofencing.models import GeoFencing
from horilla.testkit import make_company, make_employee, make_user


@override_settings(
    USE_TZ=True, TIME_ZONE="Asia/Kolkata", COSEC_ATTENDANCE_INGESTION_ENABLED=False
)
class BrowserAttendanceTests(PunchFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.company = self.employee.get_company()
        self.user = make_user("browser-clock")
        self.employee = make_employee(
            company=self.company, email=self.user.email, user=self.user, shift=self.shift
        )
        self.browser = self.browser_for(self.user)

    def browser_for(self, user=None):
        browser = Client(enforce_csrf_checks=True)
        if user is not None:
            browser.force_login(user)
            session = browser.session
            session["selected_company"] = str(self.company.pk)
            session.save()
        request = RequestFactory().get("/")
        browser.csrf_token = get_token(request)
        browser.cookies[settings.CSRF_COOKIE_NAME] = request.META["CSRF_COOKIE"]
        return browser

    def post_punch(self, name, instant, data=None, *, browser=None, csrf=True, query=""):
        browser = browser or self.browser
        headers = {"HTTP_X_CSRFTOKEN": browser.csrf_token} if csrf else {}
        with patch("attendance.views.clock_in_out.timezone.now", return_value=instant):
            return browser.post(
                reverse(name) + query,
                data or {},
                secure=True,
                HTTP_HX_REQUEST="true",
                HTTP_REFERER="https://testserver/",
                **headers,
            )

    def check_in(self, instant, *, browser=None):
        response = self.post_punch("clock-in", instant, browser=browser)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, 'hx-post="' + reverse("clock-out") + '"')
        token = re.search(r'"session_id": "([^"]+)"', response.content.decode())
        self.assertIsNotNone(token)
        return token[1]

    def check_out(self, instant, token):
        return self.post_punch("clock-out", instant, {"session_id": token})

    def snapshot(self):
        return [
            list(model.objects.order_by("pk").values())
            for model in (AttendanceActivity, Attendance, WorkRecords)
        ]

    def test_browser_check_in_and_out_with_cosec_disabled(self):
        self.assertFalse(settings.COSEC_ATTENDANCE_INGESTION_ENABLED)
        token = self.check_in(stamp(9))
        response = self.check_out(stamp(10), token)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-post="' + reverse("clock-in") + '"')
        punch = AttendanceActivity.objects.get(employee_id=self.employee)
        self.assertEqual(punch.out_datetime, stamp(10))
        attendance = Attendance.objects.get(employee_id=self.employee)
        self.assertEqual(attendance.attendance_worked_hour, "01:00")
        self.assertEqual(WorkRecords.objects.get(employee_id=self.employee).at_work_second, 3600)

    def test_two_browser_sessions_exclude_break(self):
        first = self.check_in(stamp(9))
        self.assertEqual(self.check_out(stamp(10), first).status_code, 200)
        second = self.check_in(stamp(11))
        self.assertNotEqual(first, second)
        self.assertEqual(self.check_out(stamp(12), second).status_code, 200)
        self.assertEqual(AttendanceActivity.objects.filter(employee_id=self.employee).count(), 2)
        self.assertEqual(
            Attendance.objects.get(employee_id=self.employee).attendance_worked_hour, "02:00"
        )

    def test_stale_checkout_does_not_close_newer_session(self):
        first = self.check_in(stamp(9))
        self.assertEqual(self.check_out(stamp(10), first).status_code, 200)
        second = self.check_in(stamp(11))
        original = self.snapshot()
        self.assertEqual(self.check_out(stamp(12), first).status_code, 409)
        self.assertEqual(self.snapshot(), original)
        self.assertEqual(self.check_out(stamp(12), second).status_code, 200)

    def test_duplicate_checkout_changes_nothing(self):
        token = self.check_in(stamp(9))
        self.assertEqual(self.check_out(stamp(10), token).status_code, 200)
        original = self.snapshot()
        self.assertEqual(self.check_out(stamp(11), token).status_code, 409)
        self.assertEqual(self.snapshot(), original)

    def test_missing_invalid_and_mismatched_session_are_rejected(self):
        self.check_in(stamp(9))
        activity = AttendanceActivity.objects.get(employee_id=self.employee)
        wrong = signing.dumps(
            (self.employee.pk, self.company.pk, activity.pk + 1), salt=BROWSER_CHECKOUT_SALT
        )
        original = self.snapshot()
        for token, status in (("", 400), (str(activity.pk), 400), (wrong, 409)):
            with self.subTest(status=status, token=token):
                self.assertEqual(self.check_out(stamp(10), token).status_code, status)
                self.assertEqual(self.snapshot(), original)

    def test_cross_employee_checkout_token_is_rejected(self):
        self.check_in(stamp(9))
        other = make_user("other-browser-clock")
        make_employee(company=self.company, email=other.email, user=other, shift=self.shift)
        foreign = self.check_in(stamp(9), browser=self.browser_for(other))
        original = self.snapshot()
        self.assertEqual(self.check_out(stamp(10), foreign).status_code, 403)
        self.assertEqual(self.snapshot(), original)

    def test_checkout_token_is_rejected_after_company_transfer(self):
        token = self.check_in(stamp(9))
        company = make_company("Transferred browser clock", hq=False)
        EmployeeWorkInformation.objects.filter(employee_id=self.employee).update(company_id=company)
        session = self.browser.session
        session["selected_company"] = str(company.pk)
        session.save()
        original = self.snapshot()
        self.assertEqual(self.check_out(stamp(10), token).status_code, 403)
        self.assertEqual(self.snapshot(), original)

    def test_anonymous_post_cannot_write(self):
        token = self.check_in(stamp(9))
        original = self.snapshot()
        anonymous = self.browser_for()
        for name in ("clock-in", "clock-out"):
            with self.subTest(name=name):
                response = self.post_punch(
                    name, stamp(10), {"session_id": token}, browser=anonymous
                )
                self.assertEqual(response.status_code, 204)
                self.assertEqual(self.snapshot(), original)

    def test_post_without_csrf_cannot_write(self):
        original = self.snapshot()
        self.assertEqual(self.post_punch("clock-in", stamp(9), csrf=False).status_code, 403)
        self.assertEqual(self.snapshot(), original)
        token = self.check_in(stamp(9))
        original = self.snapshot()
        response = self.post_punch("clock-out", stamp(10), {"session_id": token}, csrf=False)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.snapshot(), original)

    def test_get_cannot_open_or_close_a_session(self):
        original = self.snapshot()
        response = self.browser.get(reverse("clock-in"), secure=True, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.snapshot(), original)
        token = self.check_in(stamp(9))
        original = self.snapshot()
        response = self.browser.get(
            reverse("clock-out"), {"session_id": token}, secure=True, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.snapshot(), original)

    def test_geofenced_check_in_uses_post_coordinates(self):
        GeoFencing.objects.update_or_create(
            company_id=self.company,
            defaults={"start": True, "latitude": 12.97, "longitude": 77.59, "radius_in_meters": 100},
        )
        original = self.snapshot()
        response = self.post_punch("clock-in", stamp(9), query="?latitude=12.97&longitude=77.59")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.snapshot(), original)
        response = self.post_punch("clock-in", stamp(9), {"latitude": 12.97, "longitude": 77.59})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, 'data-session-id=')
