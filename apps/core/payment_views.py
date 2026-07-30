"""
Платежи через ЮKassa - простая кнопка на сайте
"""
import json
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, get_object_or_404
from yookassa import Configuration, Payment as YooPayment
from .models import Booking


Configuration.account_id = settings.YOOKASSA_SHOP_ID
Configuration.secret_key = settings.YOOKASSA_SECRET_KEY


def create_payment(request, booking_id):
    """
    Создать платеж в ЮKassa (вызывается при нажатии на кнопку)
    URL: /create-payment/{booking_id}/
    """

    booking = get_object_or_404(Booking, id=booking_id)


    if booking.status == 'confirmed':
        return redirect('/?error=already_paid')

    # Создаем платеж в ЮKassa
    payment = YooPayment.create({
        "amount": {
            "value": f"{float(booking.price_final):.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": f"{settings.SITE_URL}/payment-success/"
        },
        "description": f"Запись #{booking_id} - {booking.procedure.title}",
        "metadata": {
            "booking_id": booking_id,
            "customer": booking.customer_name
        }
    })

    # Сохраняем ID платежа
    booking.payment_id = payment.id
    booking.save()


    return redirect(payment.confirmation.confirmation_url)


@csrf_exempt
def yookassa_webhook(request):
    """
    Получаем уведомления от ЮKassa об оплате
    URL: /yookassa-webhook/
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            payment_id = data.get('object', {}).get('id')
            status = data.get('object', {}).get('status')

            print(f"💰 Получен платеж: {payment_id} - статус: {status}")


            if status == 'succeeded':
                try:
                    booking = Booking.objects.get(payment_id=payment_id)
                    booking.status = 'confirmed'
                    booking.save()
                    print(f"✅ Запись #{booking.id} оплачена")
                except:
                    print(f"⚠️ Запись не найдена")

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'POST required'}, status=400)


def payment_success(request):
    """
    Страница после успешной оплаты
    URL: /payment-success/
    """
    from django.shortcuts import render
    return render(request, 'service_finally.html', {'payment_success': True})