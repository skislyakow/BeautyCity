import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.models import Booking, Procedure, Salon


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
