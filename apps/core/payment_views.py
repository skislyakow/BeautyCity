import contextlib
import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from yookassa import Configuration
from yookassa import Payment as YooPayment

from .models import Booking
from .phone_auth import get_guest_booking_ids, get_user_phone

logger = logging.getLogger(__name__)


class PaymentVerificationError(Exception):
    pass


def _configure_yookassa():
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        return False
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return True


def _find_payment(payment_id):
    if not _configure_yookassa():
        raise PaymentVerificationError("ЮKassa не настроена")
    try:
        return YooPayment.find_one(payment_id)
    except Exception as exc:
        logger.exception("Не удалось получить платёж %s из ЮKassa", payment_id)
        raise PaymentVerificationError("Не удалось проверить платёж") from exc


def _metadata_matches(payment, bookings):
    metadata = getattr(payment, "metadata", None) or {}
    if not isinstance(metadata, dict):
        return False

    actual = {str(booking.pk) for booking in bookings}
    booking_id = metadata.get("booking_id")
    booking_ids = metadata.get("booking_ids")

    if booking_ids:
        expected = {part.strip() for part in str(booking_ids).split(",") if part.strip()}
        return expected == actual
    if booking_id is not None:
        return {str(booking_id)} == actual
    return True


def _confirm_paid_bookings(payment_id):
    payment = _find_payment(payment_id)
    if getattr(payment, "status", None) != "succeeded":
        return False

    try:
        paid_amount = Decimal(str(getattr(payment.amount, "value", None)))
    except (AttributeError, InvalidOperation, TypeError, ValueError) as exc:
        logger.warning("Платёж %s: не удалось прочитать сумму (%s)", payment_id, exc)
        return False

    with transaction.atomic():
        bookings = list(Booking.objects.select_for_update().filter(payment_id=payment_id))
        if not bookings:
            logger.warning("Платёж %s: связанные записи не найдены", payment_id)
            return False

        expected_amount = sum((booking.price_final for booking in bookings), Decimal("0"))
        if paid_amount != expected_amount:
            logger.warning(
                "Платёж %s: сумма %s не совпадает с суммой записей %s",
                payment_id,
                paid_amount,
                expected_amount,
            )
            return False

        if not _metadata_matches(payment, bookings):
            logger.warning("Платёж %s: metadata не совпадает с записями", payment_id)
            return False

        active = [booking for booking in bookings if booking.status != Booking.Status.CANCELED]
        if not active:
            return False

        for booking in active:
            if booking.status != Booking.Status.CONFIRMED:
                booking.status = Booking.Status.CONFIRMED
                booking.save(update_fields=["status"])

        return all(booking.status == Booking.Status.CONFIRMED for booking in active)


def has_booking_access(request, booking):
    if request.user.is_authenticated and get_user_phone(request.user) == booking.phone:
        return True
    return booking.pk in get_guest_booking_ids(request)


def create_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if not has_booking_access(request, booking):
        return JsonResponse(
            {"status": "error", "message": "Нет доступа к записи"},
            status=403,
        )
    if booking.status == Booking.Status.CONFIRMED:
        return redirect("/?error=already_paid")
    if not _configure_yookassa():
        return JsonResponse(
            {
                "status": "error",
                "message": "Оплата временно недоступна: не настроен приём платежей",
            },
            status=400,
        )
    try:
        payment = YooPayment.create(
            {
                "amount": {"value": f"{float(booking.price_final):.2f}", "currency": "RUB"},
                "capture": True,
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{settings.SITE_URL}/payment-success/{booking_id}/",
                },
                "description": f"Запись #{booking_id} - {booking.procedure.title}",
                "metadata": {"booking_id": booking_id, "customer": booking.customer_name},
            }
        )
    except Exception as exc:
        return JsonResponse(
            {"status": "error", "message": f"Ошибка при создании платежа: {exc}"},
            status=502,
        )
    booking.payment_id = payment.id or ""
    booking.save()

    confirmation = payment.confirmation
    if confirmation is None:
        return JsonResponse(
            {"status": "error", "message": "ЮKassa не вернула ссылку на оплату"},
            status=502,
        )
    return redirect(confirmation.confirmation_url)


@csrf_exempt
@require_POST
def yookassa_webhook(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Некорректный JSON от ЮKassa: %s", exc)
        return JsonResponse({"error": "invalid json"}, status=400)

    payment = data.get("object") or {}
    payment_id = payment.get("id")
    if payment.get("status") != "succeeded":
        return JsonResponse({"status": "ignored"})
    if not payment_id:
        return JsonResponse({"error": "payment id required"}, status=400)

    if not Booking.objects.filter(payment_id=payment_id).exists():
        return JsonResponse({"status": "ignored"})

    try:
        confirmed = _confirm_paid_bookings(payment_id)
    except PaymentVerificationError:
        return JsonResponse({"error": "payment verification failed"}, status=503)

    return JsonResponse({"status": "ok" if confirmed else "ignored"})


@login_required(login_url="/")
@require_POST
def create_bulk_payment(request):
    user_phone = get_user_phone(request.user)
    unpaid_bookings = Booking.objects.filter(phone=user_phone, start_at__gte=now()).exclude(
        status__in=[Booking.Status.CONFIRMED, Booking.Status.CANCELED]
    )

    if not unpaid_bookings.exists():
        return redirect("/notes/?error=no_unpaid")
    if not _configure_yookassa():
        return JsonResponse(
            {
                "status": "error",
                "message": "Оплата временно недоступна: не настроен приём платежей",
            },
            status=400,
        )

    booking_ids = list(unpaid_bookings.values_list("id", flat=True))
    total_amount = sum(b.price_final for b in unpaid_bookings)

    try:
        payment = YooPayment.create(
            {
                "amount": {"value": f"{float(total_amount):.2f}", "currency": "RUB"},
                "capture": True,
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{settings.SITE_URL}/payment-success-bulk/?booking_ids={','.join(map(str, booking_ids))}",
                },
                "description": f"Массовая оплата записей ({unpaid_bookings.count()} шт.)",
                "metadata": {"booking_ids": ",".join(map(str, booking_ids))},
            }
        )
    except Exception as exc:
        return JsonResponse(
            {"status": "error", "message": f"Ошибка при создании платежа: {exc}"},
            status=502,
        )

    unpaid_bookings.update(payment_id=payment.id or "")

    confirmation = payment.confirmation
    if confirmation is None:
        return JsonResponse(
            {"status": "error", "message": "ЮKassa не вернула ссылку на оплату"},
            status=502,
        )
    return redirect(confirmation.confirmation_url)


def payment_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if booking.status != Booking.Status.CONFIRMED and booking.payment_id:
        with contextlib.suppress(PaymentVerificationError):
            _confirm_paid_bookings(booking.payment_id)
        booking.refresh_from_db(fields=["status"])

    if booking.status == Booking.Status.CONFIRMED:
        return redirect("/notes/?payment=success")
    return redirect("/notes/?payment=pending")


def payment_success_bulk(request):
    ids_param = request.GET.get("booking_ids", "")
    try:
        booking_ids = [int(x) for x in ids_param.split(",") if x]
    except ValueError:
        booking_ids = []

    bookings = Booking.objects.filter(id__in=booking_ids)
    if not bookings.exists():
        return redirect("/notes/?payment=unknown")

    payment_ids = set(bookings.exclude(payment_id="").values_list("payment_id", flat=True))
    if len(payment_ids) == 1:
        with contextlib.suppress(PaymentVerificationError):
            _confirm_paid_bookings(payment_ids.pop())

    if bookings.filter(status=Booking.Status.CONFIRMED).exists():
        return redirect("/notes/?payment=success")
    return redirect("/notes/?payment=pending")
