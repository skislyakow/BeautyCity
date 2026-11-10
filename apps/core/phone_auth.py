import logging
from datetime import datetime, timedelta

from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import CustomerProfile, normalize_phone, record_consent_acceptance

TESTING_CODE = "1234"
SMS_CODE_TTL = timedelta(minutes=5)
SMS_MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)


def get_user_phone(user):
    """Телефон пользователя: профиль, затем username для старых phone-аккаунтов."""
    profile = getattr(user, "profile", None)
    phone = ((profile.phone if profile else "") or user.username or "").strip()
    return normalize_phone(phone) or phone


def get_guest_booking_ids(request):
    """ID записей, созданных в текущей сессии без входа в аккаунт."""
    raw = request.session.get("guest_booking_ids", [])
    if not isinstance(raw, list):
        return []
    return [int(item) for item in raw if str(item).isdigit()]


@require_POST
def phone_login_view(request):
    phone = normalize_phone(request.POST.get("tel", "").strip())
    if not phone:
        return JsonResponse({"status": "error", "message": "Введите номер телефона"}, status=400)

    consent_raw = request.POST.get("consent_accepted", request.POST.get("consent"))
    record_consent_acceptance(
        user=request.user,
        phone=phone,
        accepted=consent_raw in (True, "1", "true", "True", "on"),
    )

    code = TESTING_CODE
    request.session["auth_phone"] = phone
    request.session["auth_code"] = code
    request.session["auth_code_created_at"] = timezone.now().isoformat()
    request.session["auth_attempts"] = 0
    logger.info("SMS-код для %s: %s (dev-заглушка)", phone, code)
    print(f"[SMS] Код для {phone}: {code}")
    return JsonResponse({"status": "ok", "phone": phone})


@require_POST
def phone_confirm_view(request):
    code = (
        request.POST.get("num1", "")
        + request.POST.get("num2", "")
        + request.POST.get("num3", "")
        + request.POST.get("num4", "")
    )

    auth_code = request.session.get("auth_code")
    auth_phone = request.session.get("auth_phone")
    created_at = request.session.get("auth_code_created_at")
    attempts = request.session.get("auth_attempts", 0)

    if not auth_phone or not auth_code:
        return JsonResponse({"status": "error", "message": "Начните с ввода телефона"}, status=400)

    if created_at:
        try:
            created = datetime.fromisoformat(created_at)
            if timezone.is_naive(created):
                created = timezone.make_aware(created)
            if timezone.now() - created > SMS_CODE_TTL:
                request.session.pop("auth_code", None)
                request.session.pop("auth_code_created_at", None)
                return JsonResponse(
                    {"status": "error", "message": "Код истёк, запросите новый"}, status=400
                )
        except ValueError:
            pass

    if attempts >= SMS_MAX_ATTEMPTS:
        request.session.pop("auth_code", None)
        request.session.pop("auth_code_created_at", None)
        return JsonResponse(
            {"status": "error", "message": "Слишком много попыток, запросите новый код"}, status=400
        )

    if code != auth_code:
        request.session["auth_attempts"] = attempts + 1
        return JsonResponse({"status": "error", "message": "Неверный код"}, status=400)

    login_by_phone(request, auth_phone)
    guest_name = request.session.get("guest_customer_name", "")
    if guest_name:
        profile = getattr(request.user, "profile", None)
        if profile and not profile.first_name:
            profile.first_name = guest_name
            profile.save(update_fields=["first_name"])
    request.session.pop("auth_phone", None)
    request.session.pop("auth_code", None)
    request.session.pop("auth_code_created_at", None)
    request.session.pop("auth_attempts", None)
    request.session.pop("guest_booking_ids", None)
    return JsonResponse({"status": "ok", "phone": auth_phone})


def login_by_phone(request, phone):
    """Вход по номеру телефона после успешной проверки SMS-кода."""
    phone = normalize_phone(phone)

    profile = CustomerProfile.objects.filter(phone=phone).select_related("user").first()
    if profile:
        user = profile.user
    else:
        user, created = User.objects.get_or_create(
            username=phone,
            defaults={"first_name": ""},
        )
        if created:
            CustomerProfile.objects.create(user=user, phone=phone)

    login(request, user)
    return user


def logout_view(request):
    logout(request)
    return redirect("index")
