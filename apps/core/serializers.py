from rest_framework import serializers
from .models import Salon, Procedure, ProcedureOffering, Specialist, SpecialistSalon, WorkShift, Booking, PromoCode
from .slots import get_available_slots


class SalonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salon
        fields = '__all__'


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = '__all__'


class SpecialistSerializer(serializers.ModelSerializer):
    procedures = ProcedureSerializer(many=True, read_only=True)

    class Meta:
        model = Specialist
        fields = '__all__'


class ProcedureOfferingSerializer(serializers.ModelSerializer):
    salon = SalonSerializer(read_only=True)
    procedure = ProcedureSerializer(read_only=True)

    class Meta:
        model = ProcedureOffering
        fields = ['id', 'salon', 'procedure', 'price']


class BookingSerializer(serializers.ModelSerializer):
    salon = SalonSerializer(read_only=True)
    procedure = ProcedureSerializer(read_only=True)
    specialist = SpecialistSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'customer_name', 'phone', 'question',
            'salon', 'procedure', 'specialist',
            'start_at', 'end_at',
            'status', 'source', 'price_final',
            'created_at'
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            'salon', 'procedure', 'specialist',
            'customer_name', 'phone', 'question',
            'start_at', 'end_at',
            'promo_code'
        ]

    def validate(self, data):
        specialist = data.get('specialist')
        salon = data.get('salon')
        start_at = data.get('start_at')

        if not specialist:
            raise serializers.ValidationError(f"Мастер не указан")

        if not salon:
            raise serializers.ValidationError(f"Салон не указан")

        if not start_at:
            raise serializers.ValidationError(f"Время не указано")

        if not specialist.salons.filter(id=salon.id).exists():
            raise serializers.ValidationError(
                f"Мастер {specialist.full_name} не работает в салоне {salon.name}")

        date = start_at.date()
        time = start_at.time()

        slots = get_available_slots(salon=salon, specialist=specialist, procedure=data.get('procedure'),
                                    date=date)

        if time not in slots:
            raise serializers.ValidationError(f"Время {time} уже занято")

        return data
