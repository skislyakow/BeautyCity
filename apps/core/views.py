from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Salon, Procedure, Specialist, ProcedureOffering, SpecialistSalon, Booking
from .serializers import (
    SalonSerializer, ProcedureSerializer, SpecialistSerializer,
    ProcedureOfferingSerializer, BookingCreateSerializer, BookingSerializer
)
from .payment_views import create_payment
from .slots import get_available_slots


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
    specialists = Specialist.objects.all()
    procedure_id = request.GET.get('procedure')
    if procedure_id:
        specialists = specialists.filter(procedures__id=procedure_id)
    salon_id = request.GET.get('salon')
    if salon_id:
        specialists = specialists.filter(salons__id=salon_id)
    specialists = specialists.filter(is_active=True)
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
        salons__id=salon.id, is_active=True)
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
    salons = specialist.salons.all()
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
    booking = serializer.save()
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


def notes(request):
    """Личный кабинет"""
    return render(request, 'notes.html')


def admin_panel(request):
    """Админ-панель"""
    return render(request, 'admin.html')
