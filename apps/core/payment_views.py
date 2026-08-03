import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, get_object_or_404
from yookassa import Configuration, Payment as YooPayment
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from .models import Booking
from django.views.decorators.http import require_POST


def _configure_yookassa():
    if not settings.YOOKASSA_SHOP_ID or not settings.YOOKASSA_SECRET_KEY:
        return False
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY
    return True


def create_payment(request, booking_id):
    """Одиночная оплата — без изменений, уже работает."""
    booking = get_object_or_404(Booking, id=booking_id)
    if booking.status == 'confirmed':
        return redirect('/?error=already_paid')
    if not _configure_yookassa():
        return JsonResponse(
            {'status': 'error', 'message': 'Оплата временно недоступна: не настроен приём платежей'},
            status=400,
        )
    try:
        payment = YooPayment.create({
            "amount": {
                "value": f"{float(booking.price_final):.2f}",
                "currency": "RUB"
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": f"{settings.SITE_URL}/payment-success/{booking_id}/"
            },
            "description": f"Запись #{booking_id} - {booking.procedure.title}",
            "metadata": {
                "booking_id": booking_id,
                "customer": booking.customer_name
            }
        })
    except Exception as exc:
        return JsonResponse(
            {'status': 'error', 'message': f'Ошибка при создании платежа: {exc}'},
            status=502,
        )
    booking.payment_id = payment.id
    booking.save()

    return redirect(payment.confirmation.confirmation_url)


@csrf_exempt
def yookassa_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            payment_id = data.get('object', {}).get('id')
            status = data.get('object', {}).get('status')
            if status == 'succeeded':
                bookings = Booking.objects.filter(payment_id=payment_id)
                if bookings.exists():
                    updated_count = bookings.update(status='confirmed')
                    print(f" Массово оплачено записей: {updated_count}")
                else:
                    print(f" Записи не найдены")
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            print(f"Ошибка: {e}")
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST required'}, status=400)


@login_required(login_url='/')
@require_POST
def create_bulk_payment(request):
    user_phone = request.user.username
    unpaid_bookings = Booking.objects.filter(
        phone=user_phone,
        start_at__gte=now()
    ).exclude(status__in=['confirmed', 'canceled'])

    if not unpaid_bookings.exists():
        return redirect('/notes/?error=no_unpaid')
    if not _configure_yookassa():
        return JsonResponse(
            {'status': 'error', 'message': 'Оплата временно недоступна: не настроен приём платежей'},
            status=400,
        )

    # id записей известны ЗАРАНЕЕ, до создания платежа (в отличие от payment.id) —
    # поэтому именно их и кладём в return_url
    booking_ids = list(unpaid_bookings.values_list('id', flat=True))
    total_amount = sum(b.price_final for b in unpaid_bookings)

    try:
        payment = YooPayment.create({
            "amount": {
                "value": f"{float(total_amount):.2f}",
                "currency": "RUB"
            },
            "capture": True,
            "confirmation": {
                "type": "redirect",
                "return_url": f"{settings.SITE_URL}/payment-success-bulk/?booking_ids={','.join(map(str, booking_ids))}"
            },
            "description": f"Массовая оплата записей ({unpaid_bookings.count()} шт.)"
        })
    except Exception as exc:
        return JsonResponse(
            {'status': 'error', 'message': f'Ошибка при создании платежа: {exc}'},
            status=502,
        )

    unpaid_bookings.update(payment_id=payment.id)

    return redirect(payment.confirmation.confirmation_url)


def payment_success(request, booking_id):
    """Возврат с одиночной оплаты — без изменений."""
    booking = get_object_or_404(Booking, id=booking_id)

    if booking.status != 'confirmed' and booking.payment_id and _configure_yookassa():
        try:
            payment = YooPayment.find_one(booking.payment_id)
            if payment.status == 'succeeded':
                booking.status = Booking.Status.CONFIRMED
                booking.save()
        except Exception:
            pass

    if booking.status == 'confirmed':
        return redirect(f'/notes/?payment=success')
    return redirect(f'/notes/?payment=pending')


def payment_success_bulk(request):
    """Возврат с массовой оплаты — новая вьюха, раньше её не было вообще."""
    ids_param = request.GET.get('booking_ids', '')
    try:
        booking_ids = [int(x) for x in ids_param.split(',') if x]
    except ValueError:
        booking_ids = []

    bookings = Booking.objects.filter(id__in=booking_ids)
    if not bookings.exists():
        return redirect('/notes/?payment=unknown')

    payment_id = bookings.first().payment_id
    if payment_id and not bookings.filter(status='confirmed').exists() and _configure_yookassa():
        try:
            payment = YooPayment.find_one(payment_id)
            if payment.status == 'succeeded':
                bookings.update(status='confirmed')
        except Exception:
            pass

    if bookings.filter(status='confirmed').exists():
        return redirect('/notes/?payment=success')
    return redirect('/notes/?payment=pending')