import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.core.models import (
    Booking,
    CustomerProfile,
    Procedure,
    ProcedureOffering,
    PromoCode,
    Review,
    Salon,
    Specialist,
    SpecialistSalon,
    Tip,
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

    def test_creates_booking_without_logging_in(self):
        response = self.client.post(
            self.url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.session["guest_booking_ids"], [response.json()["id"]])
        self.assertFalse(User.objects.filter(username="+79990000000").exists())

    def test_guest_notes_show_only_created_booking(self):
        other = self._create_booking(start_at=self.start_at + timedelta(hours=2))

        response = self.client.post(
            self.url,
            data=json.dumps(self._payload()),
            content_type="application/json",
        )
        created_id = response.json()["id"]

        notes = self.client.get("/notes/")

        self.assertEqual(notes.status_code, 200)
        self.assertContains(notes, f"Запись №{created_id}")
        self.assertNotContains(notes, f"Запись №{other.id}")

    def test_notes_without_guest_session_redirects_home(self):
        response = self.client.get("/notes/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

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

    def test_promo_check_valid(self):
        PromoCode.objects.create(code="KID20", discount_percent=20, is_active=True)

        response = self.client.post(
            "/api/promo/check/",
            data=json.dumps({"code": "kid20"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(response.json()["discount_percent"], 20)

    def test_promo_check_invalid(self):
        response = self.client.post(
            "/api/promo/check/",
            data=json.dumps({"code": "BAD"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["valid"])

    def test_booking_with_valid_promo_applies_discount(self):
        PromoCode.objects.create(code="KID20", discount_percent=20, is_active=True)

        payload = self._payload()
        payload["promo_code"] = "kid20"
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.first()
        self.assertEqual(booking.price_original, Decimal("1000.00"))
        self.assertEqual(booking.price_final, Decimal("800.00"))
        self.assertEqual(booking.promo_code.code, "KID20")

    def test_booking_with_invalid_promo_returns_error(self):
        payload = self._payload()
        payload["promo_code"] = "BAD"
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Booking.objects.count(), 0)


class MyBookingsAuthTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name="Салон", address="Адрес")
        self.procedure = Procedure.objects.create(
            title="Стрижка",
            duration_minutes=60,
            base_price=Decimal("1000.00"),
        )
        self.user = User.objects.create_user(username="+79990000001", password="pass")
        CustomerProfile.objects.create(user=self.user, phone="+79990000001")
        self.other = User.objects.create_user(username="+79990000002", password="pass")
        CustomerProfile.objects.create(user=self.other, phone="+79990000002")

        self.own_booking = self._create_booking(
            phone="+79990000001",
            start_at=timezone.now() + timedelta(days=1),
        )
        self.other_booking = self._create_booking(
            phone="+79990000002",
            start_at=timezone.now() + timedelta(days=2),
        )
        self.url = "/api/my-bookings/"

    def _create_booking(self, *, phone, start_at):
        return Booking.objects.create(
            salon=self.salon,
            procedure=self.procedure,
            customer_name="Клиент",
            phone=phone,
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            price_original=Decimal("1000.00"),
            price_final=Decimal("1000.00"),
        )

    def test_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertIn(response.status_code, (401, 403))

    def test_returns_only_own_bookings(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.json()}, {self.own_booking.id})

    def test_ignores_phone_query_parameter(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url, {"phone": "+79990000002"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.json()}, {self.own_booking.id})

    def test_uses_profile_phone_instead_of_username(self):
        user = User.objects.create_user(username="client@example.com", password="pass")
        CustomerProfile.objects.create(user=user, phone="+79990000003")
        booking = self._create_booking(
            phone="+79990000003",
            start_at=timezone.now() + timedelta(days=3),
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.json()}, {booking.id})

    def test_falls_back_to_username_without_profile(self):
        user = User.objects.create_user(username="+79990000004", password="pass")
        booking = self._create_booking(
            phone="+79990000004",
            start_at=timezone.now() + timedelta(days=4),
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.json()}, {booking.id})

    def test_notes_shows_only_own_phone_bookings(self):
        self.client.force_login(self.user)

        response = self.client.get("/notes/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Запись №{self.own_booking.id}")
        self.assertNotContains(response, f"Запись №{self.other_booking.id}")

    @patch("apps.core.payment_views._configure_yookassa", return_value=False)
    def test_guest_can_pay_only_created_booking(self, _configure_yookassa):
        session = self.client.session
        session["guest_booking_ids"] = [self.own_booking.id]
        session.save()

        denied = self.client.post(f"/api/payments/{self.other_booking.id}/")
        self.assertEqual(denied.status_code, 403)

        allowed = self.client.post(f"/api/payments/{self.own_booking.id}/")
        self.assertEqual(allowed.status_code, 400)

    def test_authenticated_user_cannot_pay_other_users_booking(self):
        self.client.force_login(self.user)

        response = self.client.post(f"/api/payments/{self.other_booking.id}/")

        self.assertEqual(response.status_code, 403)

    def test_sms_login_clears_guest_booking_ids(self):
        session = self.client.session
        session["auth_phone"] = "+79990000001"
        session["auth_code"] = "1234"
        session["guest_booking_ids"] = [self.own_booking.id]
        session.save()

        response = self.client.post(
            "/phone-confirm/",
            {"num1": "1", "num2": "2", "num3": "3", "num4": "4"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("guest_booking_ids", self.client.session)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)


class ReviewTipCancelTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name="Салон", address="Адрес")
        self.procedure = Procedure.objects.create(
            title="Стрижка",
            duration_minutes=60,
            base_price=Decimal("1000.00"),
        )
        self.specialist = Specialist.objects.create(full_name="Мастер")
        self.user = User.objects.create_user(username="+79990000011", password="pass")
        CustomerProfile.objects.create(user=self.user, phone="+79990000011")
        self.other = User.objects.create_user(username="+79990000012", password="pass")
        CustomerProfile.objects.create(user=self.other, phone="+79990000012")
        start_at = timezone.now() + timedelta(days=1)
        self.booking = Booking.objects.create(
            salon=self.salon,
            procedure=self.procedure,
            specialist=self.specialist,
            customer_name="Клиент",
            phone="+79990000011",
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            price_original=Decimal("1000.00"),
            price_final=Decimal("1000.00"),
        )

    def test_owner_can_cancel_booking(self):
        self.client.force_login(self.user)
        response = self.client.post(f"/api/bookings/{self.booking.id}/cancel/")
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELED)

    def test_guest_session_can_cancel_booking(self):
        session = self.client.session
        session["guest_booking_ids"] = [self.booking.id]
        session.save()
        response = self.client.post(f"/api/bookings/{self.booking.id}/cancel/")
        self.assertEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.CANCELED)

    def test_other_user_cannot_cancel_booking(self):
        self.client.force_login(self.other)
        response = self.client.post(f"/api/bookings/{self.booking.id}/cancel/")
        self.assertEqual(response.status_code, 403)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.NEW)

    def test_create_review(self):
        response = self.client.post(
            "/api/reviews/",
            data=json.dumps(
                {
                    "specialist": self.specialist.id,
                    "author_name": "Анна",
                    "rating": 5,
                    "text": "Отлично",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.first().specialist_id, self.specialist.id)

    def test_owner_can_create_tip(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/tips/",
            data=json.dumps({"booking_id": self.booking.id, "amount": "150.50"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Tip.objects.count(), 1)
        self.assertEqual(Tip.objects.first().amount, Decimal("150.50"))

    def test_other_user_cannot_create_tip(self):
        self.client.force_login(self.other)
        response = self.client.post(
            "/api/tips/",
            data=json.dumps({"booking_id": self.booking.id, "amount": "100"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Tip.objects.count(), 0)


class AdminPanelStatsTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name="Салон", address="Адрес")
        self.procedure = Procedure.objects.create(
            title="Стрижка",
            duration_minutes=60,
            base_price=Decimal("1000.00"),
        )
        self.staff = User.objects.create_user(username="staff", password="pass", is_staff=True)
        self.current = timezone.now().replace(day=15, hour=12, minute=0, second=0, microsecond=0)

    def _booking(self, *, start_at, status):
        return Booking.objects.create(
            salon=self.salon,
            procedure=self.procedure,
            customer_name="Клиент",
            phone="+79990000999",
            start_at=start_at,
            end_at=start_at + timedelta(hours=1),
            status=status,
            price_original=Decimal("1000.00"),
            price_final=Decimal("1000.00"),
        )

    @patch("apps.core.views.now")
    def test_admin_panel_counts_past_confirmed_visits(self, mock_now):
        mock_now.return_value = self.current
        self._booking(start_at=self.current - timedelta(days=1), status=Booking.Status.CONFIRMED)
        self._booking(start_at=self.current - timedelta(days=2), status=Booking.Status.NEW)
        self._booking(start_at=self.current + timedelta(days=1), status=Booking.Status.CONFIRMED)
        self._booking(start_at=self.current - timedelta(days=3), status=Booking.Status.CANCELED)

        self.client.force_login(self.staff)
        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["visits_month"], 1)
        self.assertEqual(response.context["visit_percentage"], 50)
        self.assertEqual(response.context["visits_year"], 1)


class LandingReviewsTests(TestCase):
    def test_index_renders_reviews_from_database(self):
        specialist = Specialist.objects.create(full_name="Мастер")
        Review.objects.create(
            specialist=specialist,
            author_name="Тестовый клиент",
            rating=5,
            text="Отзыв из базы данных",
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тестовый клиент")
        self.assertContains(response, "Отзыв из базы данных")
        self.assertNotContains(response, "12 ноября 2022")
