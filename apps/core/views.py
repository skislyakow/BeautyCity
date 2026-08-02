from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.timezone import now
from django.db.models import Sum, Count
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Salon, Procedure, Specialist, ProcedureOffering, SpecialistSalon, Booking, CallbackRequest
from .serializers import (
    SalonSerializer, ProcedureSerializer, SpecialistSerializer,
    ProcedureOfferingSerializer, BookingCreateSerializer, BookingSerializer
)
from .payment_views import create_payment
from .slots import get_available_slots
from datetime import timedelta


@api_view(['GET'])
def salon_list(request):
    salons = Salon.objects.filter(is_active=True)
    serializer = SalonSerializer(salons, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def procedure_list(request):
    procedures = Procedure.objects.all()
    serializer = ProcedureSerializer(procedures, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def specialist_list(request):
    specialists = Specialist.objects.filter(is_active=True)

    procedure_id = request.GET.get('procedure')
    if procedure_id:
        specialists = specialists.filter(procedures__id=procedure_id)

    salon_id = request.GET.get('salon')
    if salon_id:
        specialists = specialists.filter(salons__salon=salon_id)

    specialists = specialists.distinct()
    serializer = SpecialistSerializer(specialists, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def procedure_offering_list(request):
    procedure_offerings = ProcedureOffering.objects.all()
    serializer = ProcedureOfferingSerializer(procedure_offerings, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def salon_procedures(request, pk):
    salon = get_object_or_404(Salon, id=pk)
    offerings = ProcedureOffering.objects.filter(salon=salon)
    serializer = ProcedureOfferingSerializer(offerings, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def salon_specialists(request, pk):
    salon = get_object_or_404(Salon, id=pk)
    specialists = Specialist.objects.filter(
        salons__salon_id=salon.id, is_active=True)
    serializer = SpecialistSerializer(specialists, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def specialist_procedures(request, pk):
    specialist = get_object_or_404(Specialist, id=pk)
    procedures = specialist.procedures.all()
    serializer = ProcedureSerializer(procedures, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def specialist_salons(request, pk):
    specialist = get_object_or_404(Specialist, id=pk)
    salon_ids = specialist.salons.values_list('salon_id', flat=True)
    salons = Salon.objects.filter(id__in=list(salon_ids))
    serializer = SalonSerializer(salons, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def available_slots(request):
    salon_id = request.GET.get('salon')
    specialist_id = request.GET.get('specialist')
    procedure_id = request.GET.get('procedure')
    date_str = request.GET.get('date')

    if not all([salon_id, specialist_id, procedure_id, date_str]):
        return Response(
            {'error': 'Необходимы параметры: salon, specialist, procedure, date'},
            status=400
        )

    salon = get_object_or_404(Salon, id=salon_id)
    specialist = get_object_or_404(Specialist, id=specialist_id)
    procedure = get_object_or_404(Procedure, id=procedure_id)

    from datetime import datetime
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    slots = get_available_slots(
        salon=salon,
        specialist=specialist,
        procedure=procedure,
        date=date
    )

    return Response({'slots': slots})


@api_view(['POST'])
def create_booking(request):
    data = request.data
    serializer = BookingCreateSerializer(data=data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    salon = serializer.validated_data.get('salon')
    procedure = serializer.validated_data.get('procedure')
    start_at = serializer.validated_data.get('start_at')

    offering = ProcedureOffering.objects.filter(salon=salon, procedure=procedure).first()
    if not offering:
        return Response({'error': 'Данная услуга не предоставляется в выбранном салоне'}, status=400)
    end_at = start_at + timedelta(minutes=procedure.duration_minutes)

    booking = serializer.save(
        price_original=offering.price,
        price_final=offering.price,
        end_at=end_at,
        # status='new',  <-- Раскомментируй, если status не имеет default в модели
        # source='web'   <-- Раскомментируй, если source не имеет default в модели
    )
    return Response(BookingSerializer(booking).data, status=201)


@api_view(['GET'])
def my_bookings(request):
    phone = request.GET.get('phone')
    if not phone:
        return Response({'error': 'Укажите телефон'}, status=400)
    bookings = Booking.objects.filter(phone=phone).order_by('-start_at')
    serializer = BookingSerializer(bookings, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def initiate_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return create_payment(request, booking_id)


@api_view(['GET'])
def admin_stats(request):
    total_bookings = Booking.objects.count()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    bookings_this_month = Booking.objects.filter(
        created_at__gte=month_start).count()
    total_revenue = Booking.objects.filter(
        created_at__gte=month_start,
        status='confirmed'
    ).aggregate(total=Sum('price_final'))['total'] or 0

    return Response({
        'total_bookings': total_bookings,
        'bookings_this_month': bookings_this_month,
        'revenue_this_month': total_revenue,
    })


def index(request):
    """Главная страница"""
    return render(request, 'index.html')


def service(request):
    """Страница записи"""
    return render(request, 'service.html')


def service_finally(request):
    """Страница подтверждения записи"""
    return render(request, 'serviceFinally.html')


@login_required(login_url='/')  # Перенаправляем на главную, если пользователь не авторизован
def notes(request):
    """Личный кабинет пользователя"""
    user_phone = request.user.username
    current_time = now()

    upcoming_bookings = Booking.objects.filter(
        phone=user_phone,
        start_at__gte=current_time
    ).exclude(status='canceled').order_by('start_at')  # Если статус хранится через Choices, используй Booking.Status.CANCELED

    past_bookings = Booking.objects.filter(
        phone=user_phone,
        start_at__lt=current_time
    ).exclude(status='canceled').order_by('-start_at')

    unpaid_sum = sum(b.price_final for b in upcoming_bookings if b.status != 'confirmed')

    context = {
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        'unpaid_sum': unpaid_sum,
    }
    return render(request, 'notes.html', context)


@staff_member_required(login_url='/')  # Пускаем только персонал, остальных на главную
def admin_panel(request):
    """Панель администратора со статистикой"""
    current_date = now()

    bookings_this_month = Booking.objects.filter(
        start_at__year=current_date.year,
        start_at__month=current_date.month
    ).exclude(status='canceled')
    payments_month_dict = bookings_this_month.filter(status='confirmed').aggregate(Sum('price_final'))
    payments_month = payments_month_dict['price_final__sum'] or 0

    visits_month = bookings_this_month.count()

    visits_year = Booking.objects.filter(
        start_at__year=current_date.year
    ).exclude(status='canceled').count()

    context = {
        'payments_month': payments_month,
        'visits_month': visits_month,
        'visits_year': visits_year,
        'visit_percentage': 100,  # Заглушка, пока не решим, как это считать
        'callback_requests': CallbackRequest.objects.filter(is_processed=False).order_by('-created_at'),
    }
    return render(request, 'admin.html', context)


@require_POST
def callback_request(request):
    """Публичная заявка «Перезвоните мне»."""
    name = request.POST.get('name', '').strip()
    phone = request.POST.get('phone', '').strip()

    if not phone:
        return JsonResponse({'status': 'error', 'message': 'Введите номер телефона'}, status=400)

    try:
        request_obj = CallbackRequest(name=name, phone=phone)
        request_obj.full_clean()
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Проверьте корректность номера телефона'}, status=400)

    request_obj.save()
    return JsonResponse({'status': 'ok'})


@staff_member_required(login_url='/')
@require_POST
def callback_done(request, pk):
    """Пометить заявку обработанной (только для персонала)."""
    request_obj = get_object_or_404(CallbackRequest, pk=pk)
    request_obj.is_processed = True
    request_obj.save(update_fields=['is_processed'])
    return JsonResponse({'status': 'ok'})
