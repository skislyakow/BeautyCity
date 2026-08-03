from django.contrib.auth import login, logout
from django.shortcuts import redirect
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import CustomerProfile

TESTING_CODE = '1234'


@require_POST
def phone_login_view(request):
    phone = request.POST.get('tel', '').strip()
    if not phone:
        return JsonResponse({'status': 'error', 'message': 'Введите номер телефона'}, status=400)

    request.session['auth_phone'] = phone
    request.session['auth_code'] = TESTING_CODE
    return JsonResponse({'status': 'ok', 'phone': phone})


@require_POST
def phone_confirm_view(request):
    code = (
        request.POST.get('num1', '')
        + request.POST.get('num2', '')
        + request.POST.get('num3', '')
        + request.POST.get('num4', '')
    )

    auth_code = request.session.get('auth_code')
    auth_phone = request.session.get('auth_phone')

    if not auth_phone:
        return JsonResponse({'status': 'error', 'message': 'Начните с ввода телефона'}, status=400)

    if code != auth_code:
        return JsonResponse({'status': 'error', 'message': 'Неверный код'}, status=400)

    login_by_phone(request, auth_phone)
    request.session.pop('auth_phone', None)
    request.session.pop('auth_code', None)
    return JsonResponse({'status': 'ok', 'phone': auth_phone})


def login_by_phone(request, phone):
    """Тихий вход по номеру телефона (без SMS-кода). Используется после создания записи."""
    user, created = User.objects.get_or_create(
        username=phone,
        defaults={'first_name': ''},
    )
    if created:
        CustomerProfile.objects.create(user=user, phone=phone)
    login(request, user)
    return user


def logout_view(request):
    logout(request)
    return redirect('index')
