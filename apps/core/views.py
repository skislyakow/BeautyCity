from datetime import timedelta
from decimal import Decimal
from random import uniform
from time import sleep

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import ProfileForm
from .models import (
    Booking,
    CallbackRequest,
    CustomerProfile,
    Procedure,
    ProcedureOffering,
    PromoCode,
    Review,
    Salon,
    Specialist,
    Tip,
    record_consent_acceptance,
)
from .payment_views import create_payment
from .phone_auth import get_guest_booking_ids, get_user_phone
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    ProcedureOfferingSerializer,
    ProcedureSerializer,
    SalonSerializer,
    SpecialistSerializer,
)
from .slots import get_available_slots, is_slot_available


@api_view(["GET"])
def salon_list(request):
    salons = Salon.objects.filter(is_active=True)
    serializer = SalonSerializer(salons, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def procedure_list(request):
    procedures = Procedure.objects.all()
    serializer = ProcedureSerializer(procedures, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def specialist_list(request):
    specialists = Specialist.objects.filter(is_active=True)

    procedure_id = request.GET.get("procedure")
    if procedure_id:
        specialists = specialists.filter(procedures__id=procedure_id)

    salon_id = request.GET.get("salon")
    if salon_id:
        specialists = specialists.filter(salons__salon=salon_id)

    specialists = specialists.distinct()
    serializer = SpecialistSerializer(specialists, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def procedure_offering_list(request):
    procedure_offerings = ProcedureOffering.objects.all()
    serializer = ProcedureOfferingSerializer(procedure_offerings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def salon_procedures(request, pk):
    salon = get_object_or_404(Salon, id=pk)
    offerings = ProcedureOffering.objects.filter(salon=salon)
    serializer = ProcedureOfferingSerializer(offerings, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def salon_specialists(request, pk):
    salon = get_object_or_404(Salon, id=pk)
    specialists = Specialist.objects.filter(salons__salon_id=salon.id, is_active=True)
    serializer = SpecialistSerializer(specialists, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def specialist_procedures(request, pk):
    specialist = get_object_or_404(Specialist, id=pk)
    procedures = specialist.procedures.all()
    serializer = ProcedureSerializer(procedures, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def specialist_salons(request, pk):
    specialist = get_object_or_404(Specialist, id=pk)
    salon_ids = specialist.salons.values_list("salon_id", flat=True)
    salons = Salon.objects.filter(id__in=list(salon_ids))
    serializer = SalonSerializer(salons, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def available_slots(request):
    salon_id = request.GET.get("salon")
    specialist_id = request.GET.get("specialist")
    procedure_id = request.GET.get("procedure")
    date_str = request.GET.get("date")

    if not all([salon_id, specialist_id, procedure_id, date_str]):
        return Response(
            {"error": "Необходимы параметры: salon, specialist, procedure, date"}, status=400
        )

    salon = get_object_or_404(Salon, id=salon_id)
    specialist = get_object_or_404(Specialist, id=specialist_id)
    procedure = get_object_or_404(Procedure, id=procedure_id)

    from datetime import datetime

    date = datetime.strptime(date_str, "%Y-%m-%d").date()

    slots = get_available_slots(salon=salon, specialist=specialist, procedure=procedure, date=date)

    return Response({"slots": slots})


def _record_booking_consent(request, booking, consent_accepted):
    record_consent_acceptance(
        user=request.user,
        phone=booking.phone,
        accepted=consent_accepted,
    )


def _create_booking_once(request):
    serializer = BookingCreateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    salon = serializer.validated_data.get("salon")
    procedure = serializer.validated_data.get("procedure")
    specialist = serializer.validated_data.get("specialist")
    start_at = serializer.validated_data.get("start_at")
    promo = serializer.validated_data.pop("promo_code_obj", None)
    consent_accepted = serializer.validated_data.pop("consent_accepted", False)

    offering = ProcedureOffering.objects.filter(salon=salon, procedure=procedure).first()
    if not offering:
        return Response(
            {"error": "Данная услуга не предоставляется в выбранном салоне"}, status=400
        )
    end_at = start_at + timedelta(minutes=procedure.duration_minutes)

    price_original = offering.price
    price_final = offering.price
    if promo:
        discount = Decimal(promo.discount_percent)
        price_final = (price_original * (Decimal(100) - discount) / Decimal(100)).quantize(
            Decimal("0.01")
        )

    try:
        with transaction.atomic():
            # UPDATE строки мастера сериализует конкурентные бронирования:
            # на PostgreSQL это блокировка строки, на SQLite — блокировка записи.
            # select_for_update() на SQLite не работает, поэтому нужен реальный UPDATE.
            locked = Specialist.objects.filter(pk=specialist.pk).update(
                booking_version=F("booking_version") + 1
            )
            if not locked:
                return Response({"error": "Мастер не найден"}, status=400)

            # Повторная проверка уже под блокировкой: между валидацией
            # сериализатора и этой транзакцией слот мог занять другой запрос.
            if not is_slot_available(specialist=specialist, start_at=start_at, end_at=end_at):
                return Response({"error": "Время уже занято"}, status=409)

            booking = serializer.save(
                promo_code=promo,
                price_original=price_original,
                price_final=price_final,
                end_at=end_at,
            )
            _record_booking_consent(request, booking, consent_accepted)
    except IntegrityError:
        return Response({"error": "Время уже занято"}, status=409)

    return booking


@api_view(["POST"])
def create_booking(request):
    result = None
    for attempt in range(5):
        try:
            result = _create_booking_once(request)
            break
        except OperationalError as exc:
            # SQLite может вернуть блокировку сразу (особенно в shared-cache).
            # Повторяем запрос: конкурирующая транзакция успеет завершиться.
            if "locked" not in str(exc).lower():
                raise
            if attempt == 4:
                return Response(
                    {"error": "Не удалось создать запись, попробуйте ещё раз"},
                    status=503,
                )
            sleep(0.05 * (attempt + 1) + uniform(0, 0.02))

    if isinstance(result, Response):
        return result

    booking = result

    if booking.customer_name:
        request.session["guest_customer_name"] = booking.customer_name
        if request.user.is_authenticated:
            profile = getattr(request.user, "profile", None)
            if profile and not profile.first_name:
                profile.first_name = booking.customer_name
                profile.save(update_fields=["first_name"])
            if not request.user.first_name:
                request.user.first_name = booking.customer_name
                request.user.save(update_fields=["first_name"])

    # Не входим в аккаунт по телефону из формы: код не подтверждён.
    # Даём текущей сессии доступ только к этой записи.
    guest_booking_ids = get_guest_booking_ids(request)
    if booking.id not in guest_booking_ids:
        guest_booking_ids.append(booking.id)
    request.session["guest_booking_ids"] = guest_booking_ids[-10:]

    return Response(BookingSerializer(booking).data, status=201)


@api_view(["POST"])
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if (
        request.user.is_authenticated
        and request.user.is_staff
        or request.user.is_authenticated
        and get_user_phone(request.user) == booking.phone
    ):
        allowed = True
    else:
        allowed = booking.id in get_guest_booking_ids(request)
    if not allowed:
        return Response({"error": "Нет доступа к записи"}, status=403)
    if booking.status == Booking.Status.CANCELED:
        return Response({"status": "already_canceled"})
    booking.status = Booking.Status.CANCELED
    booking.save(update_fields=["status"])
    return Response({"status": "canceled"})


@api_view(["POST"])
def create_review(request):
    specialist_id = request.data.get("specialist") or request.data.get("specialist_id")
    if not specialist_id:
        return Response({"error": "Укажите мастера"}, status=400)
    specialist = get_object_or_404(Specialist, id=specialist_id)
    author_name = (request.data.get("author_name") or request.data.get("name") or "").strip()
    text = (request.data.get("text") or request.data.get("comment") or "").strip()
    try:
        rating = int(request.data.get("rating", 5))
    except TypeError, ValueError:
        rating = 5
    rating = max(1, min(5, rating))
    review = Review.objects.create(
        specialist=specialist,
        author_name=author_name,
        rating=rating,
        text=text,
    )
    consent_raw = request.data.get("consent_accepted", request.data.get("consent"))
    record_consent_acceptance(
        user=request.user,
        phone=get_user_phone(request.user) if request.user.is_authenticated else "",
        accepted=consent_raw in (True, "1", "true", "True", "on"),
    )
    return Response({"id": review.id, "status": "created"}, status=201)


@api_view(["POST"])
def create_tip(request):
    booking_id = request.data.get("booking") or request.data.get("booking_id")
    if not booking_id:
        return Response({"error": "Укажите запись"}, status=400)
    booking = get_object_or_404(Booking, id=booking_id)
    if (
        request.user.is_authenticated
        and request.user.is_staff
        or request.user.is_authenticated
        and get_user_phone(request.user) == booking.phone
    ):
        allowed = True
    else:
        allowed = booking.id in get_guest_booking_ids(request)
    if not allowed:
        return Response({"error": "Нет доступа к записи"}, status=403)
    try:
        amount = Decimal(str(request.data.get("amount", "0")).replace(",", "."))
    except Exception:
        return Response({"error": "Некорректная сумма"}, status=400)
    if amount <= 0:
        return Response({"error": "Сумма должна быть больше 0"}, status=400)
    tip = Tip.objects.create(booking=booking, amount=amount)
    return Response({"id": tip.id, "status": "created"}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    phone = get_user_phone(request.user)
    if not phone:
        return Response({"error": "Телефон не указан"}, status=400)
    bookings = Booking.objects.filter(phone=phone).order_by("-start_at")
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def check_promo(request):
    code = request.data.get("code") or request.data.get("promo_code") or ""
    if not code:
        return Response({"valid": False, "error": "Укажите промокод"}, status=400)
    code = str(code).strip().upper()
    try:
        promo = PromoCode.objects.get(code=code)
    except PromoCode.DoesNotExist:
        return Response({"valid": False, "error": "Промокод не найден"}, status=404)
    if not promo.is_valid_today():
        return Response({"valid": False, "error": "Промокод недействителен"}, status=400)
    return Response(
        {
            "valid": True,
            "code": promo.code,
            "discount_percent": promo.discount_percent,
            "description": promo.description,
        }
    )


@api_view(["POST"])
def initiate_payment(request, booking_id):
    return create_payment(request, booking_id)


@api_view(["GET"])
def admin_stats(request):
    total_bookings = Booking.objects.count()
    current_time = timezone.now()
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0)
    bookings_this_month = Booking.objects.filter(created_at__gte=month_start).count()
    total_revenue = (
        Booking.objects.filter(
            created_at__gte=month_start, status=Booking.Status.CONFIRMED
        ).aggregate(total=Sum("price_final"))["total"]
        or 0
    )

    return Response(
        {
            "total_bookings": total_bookings,
            "bookings_this_month": bookings_this_month,
            "revenue_this_month": total_revenue,
        }
    )


def index(request):
    """Главная страница"""
    reviews = (
        Review.objects.exclude(text="").select_related("specialist").order_by("-created_at")[:12]
    )
    return render(request, "index.html", {"reviews": reviews})


def service(request):
    """Страница записи"""
    return render(request, "service.html")


def _get_booking_prefill(request):
    """Имя и телефон для формы записи из профиля или прошлых записей."""
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        phone = get_user_phone(request.user)
        name = (profile.first_name if profile else "") or request.user.first_name
        if not name and phone:
            name = (
                Booking.objects.filter(phone=phone)
                .exclude(customer_name="")
                .order_by("-created_at")
                .values_list("customer_name", flat=True)
                .first()
                or ""
            )
        return {
            "prefill_name": name,
            "prefill_phone": (profile.phone if profile else "") or phone,
        }

    latest = (
        Booking.objects.filter(id__in=get_guest_booking_ids(request))
        .exclude(customer_name="")
        .order_by("-created_at")
        .first()
    )
    if latest:
        return {"prefill_name": latest.customer_name, "prefill_phone": latest.phone}
    return {
        "prefill_name": request.session.get("guest_customer_name", ""),
        "prefill_phone": "",
    }


def service_finally(request):
    """Страница подтверждения записи"""
    return render(request, "serviceFinally.html", _get_booking_prefill(request))


@login_required
def profile_view(request):
    """Просмотр и редактирование профиля клиента."""
    profile, _ = CustomerProfile.objects.get_or_create(
        user=request.user,
        defaults={"phone": get_user_phone(request.user)},
    )

    if request.method == "POST":
        old_avatar_name = profile.avatar.name if profile.avatar else ""
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            if form.cleaned_data.get("remove_avatar") and profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
            profile.save()
            new_avatar_name = profile.avatar.name if profile.avatar else ""
            if old_avatar_name and old_avatar_name != new_avatar_name:
                profile.avatar.storage.delete(old_avatar_name)
            request.user.first_name = profile.first_name
            request.user.save(update_fields=["first_name"])
            messages.success(request, "Профиль сохранён")
            return redirect("profile")
    else:
        form = ProfileForm(instance=profile)

    return render(
        request,
        "profile.html",
        {
            "form": form,
            "profile": profile,
        },
    )


def notes(request):
    guest_booking_ids = get_guest_booking_ids(request)

    if request.user.is_authenticated:
        access_filter = Q(phone=get_user_phone(request.user))
        if guest_booking_ids:
            access_filter |= Q(id__in=guest_booking_ids)
        bookings = Booking.objects.filter(access_filter)
    else:
        if not guest_booking_ids:
            return redirect("/")
        bookings = Booking.objects.filter(id__in=guest_booking_ids)
        if not bookings.exists():
            return redirect("/")

    current_time = now()
    upcoming_bookings = (
        bookings.filter(start_at__gte=current_time)
        .exclude(status=Booking.Status.CANCELED)
        .order_by("start_at")
    )
    past_bookings = (
        bookings.filter(start_at__lt=current_time)
        .exclude(status=Booking.Status.CANCELED)
        .order_by("-start_at")
    )

    unpaid_sum = sum(
        b.price_final for b in upcoming_bookings if b.status != Booking.Status.CONFIRMED
    )
    is_guest = not request.user.is_authenticated
    guest_phone = ""
    if is_guest:
        guest_phone = bookings.order_by("start_at").values_list("phone", flat=True).first() or ""

    context = {
        "upcoming_bookings": upcoming_bookings,
        "past_bookings": past_bookings,
        "unpaid_sum": unpaid_sum,
        "is_guest": is_guest,
        "guest_phone": guest_phone,
    }
    return render(request, "notes.html", context)


@staff_member_required(login_url="/")  # Пускаем только персонал, остальных на главную
def admin_panel(request):
    current_date = now()

    bookings_this_month = Booking.objects.filter(
        start_at__year=current_date.year, start_at__month=current_date.month
    ).exclude(status=Booking.Status.CANCELED)
    payments_month_dict = bookings_this_month.filter(status=Booking.Status.CONFIRMED).aggregate(
        Sum("price_final")
    )
    payments_month = payments_month_dict["price_final__sum"] or 0

    past_month = bookings_this_month.filter(start_at__lt=current_date)
    confirmed_past_month = past_month.filter(status=Booking.Status.CONFIRMED)
    visits_month = confirmed_past_month.count()
    total_past_month = past_month.count()
    visit_percentage = round(visits_month / total_past_month * 100) if total_past_month else 0

    visits_year = Booking.objects.filter(
        start_at__year=current_date.year,
        start_at__lt=current_date,
        status=Booking.Status.CONFIRMED,
    ).count()

    context = {
        "payments_month": payments_month,
        "visits_month": visits_month,
        "visits_year": visits_year,
        "visit_percentage": visit_percentage,
        "callback_requests": CallbackRequest.objects.filter(is_processed=False).order_by(
            "-created_at"
        ),
    }
    return render(request, "admin.html", context)


@require_POST
def callback_request(request):
    """Публичная заявка «Перезвоните мне»."""
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()

    if not phone:
        return JsonResponse({"status": "error", "message": "Введите номер телефона"}, status=400)

    try:
        request_obj = CallbackRequest(name=name, phone=phone)
        request_obj.full_clean()
    except Exception:
        return JsonResponse(
            {"status": "error", "message": "Проверьте корректность номера телефона"}, status=400
        )

    request_obj.save()
    consent_raw = request.POST.get("consent_accepted", request.POST.get("consent"))
    record_consent_acceptance(
        user=request.user,
        phone=phone,
        accepted=consent_raw in (True, "1", "true", "True", "on"),
    )
    return JsonResponse({"status": "ok"})


@staff_member_required(login_url="/")
@require_POST
def callback_done(request, pk):
    """Пометить заявку обработанной (только для персонала)."""
    request_obj = get_object_or_404(CallbackRequest, pk=pk)
    request_obj.is_processed = True
    request_obj.save(update_fields=["is_processed"])
    return JsonResponse({"status": "ok"})
