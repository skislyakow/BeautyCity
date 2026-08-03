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
    total_amount = sum(b.price_final for b in unpaid_bookings)
    payment = YooPayment.create({
        "amount": {
            "value": f"{float(total_amount):.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"{settings.SITE_URL}/payment-success/"
        },
        "description": f"Массовая оплата записей ({unpaid_bookings.count()} шт.)"
    })

    unpaid_bookings.update(payment_id=payment.id)

    return redirect(payment.confirmation.confirmation_url)


def payment_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if booking.status != 'confirmed' and booking.payment_id:
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