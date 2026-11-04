import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.core.models import (
    Booking,
    Procedure,
    ProcedureOffering,
    Salon,
    Specialist,
    SpecialistSalon,
    WorkShift,
)
from apps.core.slots import get_available_slots, is_slot_available


@override_settings(YOOKASSA_SHOP_ID="test-shop", YOOKASSA_SECRET_KEY="test-key")
class YooKassaWebhookTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name="Салон", address="Адрес")
        self.procedure = Procedure.objects.create(
            title="Стрижка",
            duration_minutes=60,
            base_price=Decimal("1000.00"),
        )
        self.booking = self._create_booking(payment_id="payment-1")
        self.url = "/api/payments/webhook/"

    def _create_booking(self, *, payment_id, price=Decimal("1000.00")):
        start_at = timezone.now()
        return Booking.objects.create(
            salon=self.salon,
            procedure=self.procedure,
            customer_name="Клиент",
            phone="+79990000000",
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            price_original=price,
            price_final=price,
            payment_id=payment_id,
        )

    def _payment(self, *, status="succeeded", amount="1000.00", metadata=None):
        if metadata is None:
            metadata = {"booking_id": self.booking.id}
        return SimpleNamespace(
            status=status,
            amount=SimpleNamespace(value=amount),
            metadata=metadata,
        )

    def _post(self, payment_id="payment-1", status="succeeded"):
        payload = {
            "event": "payment.succeeded",
            "object": {"id": payment_id, "status": status},
        }
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_forged_success_is_rejected_when_yookassa_says_pending(self, find_one):
        find_one.return_value = self._payment(status="pending")

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.NEW)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_real_succeeded_payment_confirms_booking(self, find_one):
        find_one.return_value = self._payment()

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_amount_mismatch_does_not_confirm(self, find_one):
        find_one.return_value = self._payment(amount="1.00")

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.NEW)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_metadata_mismatch_does_not_confirm(self, find_one):
        find_one.return_value = self._payment(metadata={"booking_id": 999999})

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.NEW)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_canceled_booking_is_not_confirmed(self, find_one):
        self.booking.status = Booking.Status.CANCELED
        self.booking.save(update_fields=["status"])
        find_one.return_value = self._payment()

        response = self._post()

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELED)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_bulk_payment_confirms_all_bookings(self, find_one):
        payment_id = "payment-bulk"
        second = self._create_booking(payment_id=payment_id, price=Decimal("500.00"))
        self.booking.payment_id = payment_id
        self.booking.price_final = Decimal("1000.00")
        self.booking.save(update_fields=["payment_id", "price_final"])
        find_one.return_value = self._payment(
            amount="1500.00",
            metadata={"booking_ids": f"{self.booking.id},{second.id}"},
        )

        response = self._post(payment_id=payment_id)

        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(second.status, Booking.Status.CONFIRMED)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_webhook_is_idempotent(self, find_one):
        find_one.return_value = self._payment()

        first = self._post()
        second = self._post()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_unknown_payment_is_ignored_without_api_call(self, find_one):
        response = self._post(payment_id="unknown-payment")

        self.assertEqual(response.status_code, 200)
        find_one.assert_not_called()

    @override_settings(YOOKASSA_SHOP_ID="", YOOKASSA_SECRET_KEY="")
    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_verification_failure_returns_503(self, find_one):
        response = self._post()

        self.assertEqual(response.status_code, 503)
        find_one.assert_not_called()
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.NEW)

    def test_invalid_json_returns_400(self):
        response = self.client.post(
            self.url,
            data="{",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_get_is_not_allowed(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    @patch("apps.core.payment_views.YooPayment.find_one")
    def test_payment_success_page_does_not_trust_return_url(self, find_one):
        find_one.return_value = self._payment(status="pending")

        response = self.client.get(f"/payment-success/{self.booking.id}/")

        self.assertEqual(response.url, "/notes/?payment=pending")
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.NEW)


class BookingCreationTests(TransactionTestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name="Салон", address="Адрес")
        self.procedure = Procedure.objects.create(
            title="Стрижка",
            duration_minutes=60,
            base_price=Decimal("1000.00"),
        )
        ProcedureOffering.objects.create(
            salon=self.salon,
            procedure=self.procedure,
            price=Decimal("1000.00"),
        )
        self.date = timezone.localdate() + timedelta(days=1)
        self.start_at = timezone.make_aware(datetime.combine(self.date, time(10, 0)))
        self.end_at = self.start_at + timedelta(hours=1)
        self.specialist = self._add_specialist("Мастер 1")
        self.url = "/api/bookings/"

    def _add_specialist(self, name):
        specialist = Specialist.objects.create(full_name=name)
        specialist.procedures.add(self.procedure)
        SpecialistSalon.objects.create(specialist=specialist, salon=self.salon)
        WorkShift.objects.create(
            salon=self.salon,
            specialist=specialist,
            date=self.date,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        return specialist

    def _payload(self, *, start_at=None, specialist=None, salon=None, phone="+79990000000"):
        start_at = start_at or self.start_at
        return {
            "salon": (salon or self.salon).id,
            "procedure": self.procedure.id,
            "specialist": (specialist or self.specialist).id,
            "customer_name": "Клиент",
            "phone": phone,
            "start_at": start_at.isoformat(),
            "end_at": (start_at + timedelta(minutes=self.procedure.duration_minutes)).isoformat(),
        }

    def _create_booking(self, *, start_at=None, specialist=None, phone="+79990000000"):
        start_at = start_at or self.start_at
        return Booking.objects.create(
            salon=self.salon,
            procedure=self.procedure,
            specialist=specialist or self.specialist,
            customer_name="Клиент",
            phone=phone,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=self.procedure.duration_minutes),
            price_original=Decimal("1000.00"),
            price_final=Decimal("1000.00"),
        )

    def test_creates_booking(self):
        response = self.client.post(
            self.url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.filter(specialist=self.specialist).count(), 1)

    def test_rejects_overlap_even_if_slot_list_is_stale(self):
        self._create_booking()

        with patch(
            "apps.core.serializers.get_available_slots",
            return_value=[time(10, 30)],
        ):
            response = self.client.post(
                self.url,
                data=json.dumps(self._payload(start_at=self.start_at + timedelta(minutes=30))),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Booking.objects.filter(specialist=self.specialist).count(), 1)

    def test_rejects_same_specialist_in_another_salon(self):
        other_salon = Salon.objects.create(name="Другой салон", address="Другой адрес")
        SpecialistSalon.objects.create(specialist=self.specialist, salon=other_salon)
        ProcedureOffering.objects.create(
            salon=other_salon,
            procedure=self.procedure,
            price=Decimal("1000.00"),
        )
        WorkShift.objects.create(
            salon=other_salon,
            specialist=self.specialist,
            date=self.date,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        self._create_booking()

        with patch(
            "apps.core.serializers.get_available_slots",
            return_value=[time(10, 0)],
        ):
            response = self.client.post(
                self.url,
                data=json.dumps(self._payload(salon=other_salon)),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Booking.objects.filter(specialist=self.specialist).count(), 1)

    def test_slots_hide_booking_from_another_salon(self):
        other_salon = Salon.objects.create(name="Другой салон", address="Другой адрес")
        SpecialistSalon.objects.create(specialist=self.specialist, salon=other_salon)
        ProcedureOffering.objects.create(
            salon=other_salon,
            procedure=self.procedure,
            price=Decimal("1000.00"),
        )
        WorkShift.objects.create(
            salon=other_salon,
            specialist=self.specialist,
            date=self.date,
            start_time=time(9, 0),
            end_time=time(18, 0),
        )
        self._create_booking()

        slots = get_available_slots(
            salon=other_salon,
            specialist=self.specialist,
            procedure=self.procedure,
            date=self.date,
        )

        self.assertNotIn(time(10, 0), slots)
        self.assertIn(time(11, 0), slots)

    def test_allows_same_time_for_different_specialist(self):
        second = self._add_specialist("Мастер 2")
        self._create_booking()

        response = self.client.post(
            self.url,
            data=json.dumps(self._payload(specialist=second)),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.filter(start_at=self.start_at).count(), 2)

    def test_canceled_booking_does_not_block_slot(self):
        canceled = self._create_booking()
        canceled.status = Booking.Status.CANCELED
        canceled.save(update_fields=["status"])

        response = self.client.post(
            self.url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.filter(specialist=self.specialist).count(), 2)

    def test_db_rejects_exact_duplicate_active_booking(self):
        self._create_booking()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self._create_booking()

        self.assertEqual(Booking.objects.filter(specialist=self.specialist).count(), 1)

    def test_is_slot_available_detects_overlap(self):
        self._create_booking()

        self.assertFalse(
            is_slot_available(
                specialist=self.specialist,
                start_at=self.start_at + timedelta(minutes=30),
                end_at=self.end_at + timedelta(minutes=30),
            )
        )

    def test_parallel_requests_create_only_one_booking(self):
        barrier = threading.Barrier(2)

        def book(phone):
            close_old_connections()
            try:
                client = Client()
                payload = self._payload(phone=phone)
                barrier.wait(timeout=10)
                response = client.post(
                    self.url,
                    data=json.dumps(payload),
                    content_type="application/json",
                )
                return response.status_code
            finally:
                close_old_connections()

        # Обе заявки проходят валидацию по устаревшему списку слотов;
        # блокировка мастера должна пропустить только одну.
        with (
            patch(
                "apps.core.serializers.get_available_slots",
                return_value=[self.start_at.time()],
            ),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            statuses = sorted(pool.map(book, ["+79990000001", "+79990000002"]))

        self.assertEqual(statuses.count(201), 1, statuses)
        self.assertTrue(all(status in (201, 400, 409) for status in statuses), statuses)
        self.assertEqual(Booking.objects.filter(specialist=self.specialist).count(), 1, statuses)
