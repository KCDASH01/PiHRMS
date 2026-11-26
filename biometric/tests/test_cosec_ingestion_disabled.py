"""Fail-closed COSEC attendance ingestion coverage without device traffic."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from biometric import views
from biometric.cbv.biometric import BiometricSheduleForm
from biometric.cosec import COSECBiometric
from horilla.horilla_middlewares import ThreadLocalMiddleware


@override_settings(COSEC_ATTENDANCE_INGESTION_ENABLED=False)
class CosecIngestionDisabledTests(SimpleTestCase):
    def setUp(self):
        self.device = Mock(
            id=uuid4(),
            machine_type="cosec",
            is_live=True,
            machine_ip="192.0.2.1",
            port=80,
            bio_username="fixture",
            bio_password="fixture",
        )

    def operator_request(self, *, post=False, data=None, path="/biometric/"):
        factory = RequestFactory()
        make_request = factory.post if post else factory.get
        request = make_request(path, data or {}, HTTP_HX_REQUEST="true")
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            employee_get=SimpleNamespace(is_active=True),
            has_perm=lambda _perm: True,
        )
        request.session = {"selected_company": "all"}
        return request

    def test_live_start_does_not_fetch_or_write_device(self):
        request = self.operator_request(data={"deviceId": self.device.id, "is_live": "on"})
        with (
            patch("base.models.BiometricAttendance.objects.filter") as installed,
            patch.object(views.BiometricDevices.objects, "get", return_value=self.device),
            patch.object(views, "COSECBiometric") as client,
            patch.object(views, "COSECBioAttendanceThread") as thread,
        ):
            installed.return_value.first.return_value = None
            self.assertEqual(views.biometric_device_live(request).status_code, 403)
        client.assert_not_called()
        thread.assert_not_called()
        self.device.save.assert_not_called()

    def test_existing_live_worker_does_not_read_or_write(self):
        with (
            patch.object(views.BiometricDevices.objects, "get") as load,
            patch.object(views, "COSECBiometric") as client,
            patch.object(views.COSECAttendanceArguments.objects, "update_or_create") as cursor,
        ):
            views.COSECBioAttendanceThread(self.device.id).run()
        load.assert_not_called()
        client.assert_not_called()
        cursor.assert_not_called()

    def test_schedule_creation_and_existing_job_are_disabled(self):
        request = self.operator_request(
            post=True,
            data={"scheduler_duration": "00:01"},
            path=reverse("biometric-device-schedule", kwargs={"pk": self.device.id}),
        )
        device_row = views.BiometricDevices(
            id=self.device.id,
            name="COSEC test device",
            machine_type="cosec",
            machine_ip=self.device.machine_ip,
            port=self.device.port,
            bio_username=self.device.bio_username,
            bio_password=self.device.bio_password,
        )
        schedule_view = ThreadLocalMiddleware(
            lambda request: BiometricSheduleForm.as_view()(request, pk=self.device.id)
        )
        with (
            patch("base.models.BiometricAttendance.objects.filter") as installed,
            patch.object(views.BiometricDevices.objects, "filter") as devices,
            patch.object(
                views.BiometricDevices.objects, "get", return_value=self.device
            ) as load_device,
            patch("biometric.cbv.biometric.BackgroundScheduler") as scheduler,
            patch.object(views, "BackgroundScheduler") as legacy_scheduler,
            patch.object(views.BiometricDevices, "find") as load,
            patch.object(views, "cosec_biometric_attendance_logs") as poll,
        ):
            installed.return_value.first.return_value = None
            devices.return_value.first.return_value = device_row
            response = schedule_view(request)
            self.assertEqual(response.status_code, 403)
            load_device.assert_called_once_with(id=self.device.id)
            self.assertEqual(views.biometric_device_schedule(request, self.device.id).status_code, 403)
            views.cosec_biometric_attendance_scheduler(self.device.id)
        scheduler.assert_not_called()
        legacy_scheduler.assert_not_called()
        load.assert_not_called()
        poll.assert_not_called()
        self.device.save.assert_not_called()

    def test_manual_fetch_does_not_call_poll(self):
        with (
            patch("base.models.BiometricAttendance.objects.filter") as installed,
            patch.object(views.BiometricDevices, "find", return_value=self.device),
            patch.object(views, "cosec_biometric_attendance_logs") as poll,
        ):
            installed.return_value.first.return_value = None
            response = views.biometric_device_fetch_logs(self.operator_request(), self.device.id)
        self.assertEqual(response.status_code, 403)
        poll.assert_not_called()

    def test_direct_poll_and_device_client_respect_flag(self):
        client = COSECBiometric("192.0.2.1", 80, "fixture", "fixture")
        with (
            patch.object(views.COSECAttendanceArguments.objects, "filter") as cursor,
            patch.object(views, "COSECBiometric") as constructor,
            patch("biometric.cosec.requests.get") as fetch,
        ):
            self.assertIsNone(views.cosec_biometric_attendance_logs(self.device))
            self.assertIsNone(client.get_attendance_events())
        cursor.assert_not_called()
        constructor.assert_not_called()
        fetch.assert_not_called()

    def test_in_flight_poll_and_live_batches_do_not_write_after_disable(self):
        for live in (False, True):
            with self.subTest(live=live):
                enabled = True

                def fetch():
                    nonlocal enabled
                    enabled = False
                    return [{"detail-1": "100", "seq-No": "2", "roll-over-count": "0"}]

                with (
                    patch.object(views, "cosec_attendance_ingestion_enabled", side_effect=lambda: enabled),
                    patch.object(views.BiometricDevices.objects, "get", return_value=self.device),
                    patch.object(views.COSECAttendanceArguments.objects, "filter") as load_cursor,
                    patch.object(views.COSECAttendanceArguments.objects, "update_or_create") as save_cursor,
                    patch.object(views.BiometricEmployees.objects, "filter") as mapping,
                    patch.object(views, "COSECBiometric") as client,
                    patch.object(views, "clock_in_from_source") as check_in,
                    patch.object(views, "clock_out_from_source") as check_out,
                ):
                    load_cursor.return_value.first.return_value = None
                    client.return_value.get_attendance_events.side_effect = lambda *_args: fetch()
                    if live:
                        views.COSECBioAttendanceThread(self.device.id).run()
                    else:
                        self.assertIsNone(views.cosec_biometric_attendance_logs(self.device))
                client.return_value.get_attendance_events.assert_called_once()
                mapping.assert_not_called()
                save_cursor.assert_not_called()
                check_in.assert_not_called()
                check_out.assert_not_called()
                self.device.save.assert_not_called()
