from django.db.models import Avg
from rest_framework import serializers

from .models import (
    Booking,
    Procedure,
    ProcedureOffering,
    PromoCode,
    Salon,
    Specialist,
    normalize_phone,
    phone_validator,
)
from .slots import get_available_slots


class SalonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Salon
        fields = "__all__"


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = "__all__"


class SpecialistSerializer(serializers.ModelSerializer):
    procedures = ProcedureSerializer(many=True, read_only=True)
    rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    class Meta:
        model = Specialist
        fields = [
            "id",
            "full_name",
            "photo",
            "bio",
            "experience",
            "is_active",
            "procedures",
            "rating",
            "reviews_count",
        ]

    def get_rating(self, obj):
        agg = obj.reviews.aggregate(avg=Avg("rating"))
        if agg["avg"] is None:
            return None
        return round(agg["avg"], 1)

    def get_reviews_count(self, obj):
        return obj.reviews.count()


class ProcedureOfferingSerializer(serializers.ModelSerializer):
    salon = SalonSerializer(read_only=True)
    procedure = ProcedureSerializer(read_only=True)

    class Meta:
        model = ProcedureOffering
        fields = ["id", "salon", "procedure", "price"]


class BookingSerializer(serializers.ModelSerializer):
    salon = SalonSerializer(read_only=True)
    procedure = ProcedureSerializer(read_only=True)
    specialist = SpecialistSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "customer_name",
            "phone",
            "question",
            "salon",
            "procedure",
            "specialist",
            "start_at",
            "end_at",
            "status",
            "source",
            "price_final",
            "created_at",
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(max_length=20)
    promo_code = serializers.CharField(
        write_only=True, required=False, allow_blank=True, allow_null=True
    )
    consent_accepted = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Booking
        fields = [
            "salon",
            "procedure",
            "specialist",
            "customer_name",
            "phone",
            "question",
            "start_at",
            "end_at",
            "promo_code",
            "consent_accepted",
        ]
        extra_kwargs = {"promo_code": {"required": False, "allow_null": True}}

    def validate_phone(self, value):
        normalized = normalize_phone(value)
        try:
            phone_validator(normalized or value)
        except Exception as err:
            raise serializers.ValidationError(
                "Телефон должен быть в формате +79998887766 (10–15 цифр)."
            ) from err
        return normalized or value

    def validate(self, data):
        specialist = data.get("specialist")
        salon = data.get("salon")
        start_at = data.get("start_at")
        if data.get("phone"):
            normalized = normalize_phone(data["phone"])
            if normalized:
                data["phone"] = normalized
        promo_code_input = data.pop("promo_code", None) or self.initial_data.get("promo_code")

        if promo_code_input:
            code = str(promo_code_input).strip().upper()
            try:
                promo = PromoCode.objects.get(code=code)
            except PromoCode.DoesNotExist as err:
                raise serializers.ValidationError("Промокод не найден") from err
            if not promo.is_valid_today():
                raise serializers.ValidationError("Промокод недействителен")
            data["promo_code_obj"] = promo
        elif promo_code_input == "":
            data["promo_code_obj"] = None

        if not specialist:
            raise serializers.ValidationError("Мастер не указан")

        if not salon:
            raise serializers.ValidationError("Салон не указан")

        if not start_at:
            raise serializers.ValidationError("Время не указано")

        procedure = data.get("procedure")
        if not specialist.salons.filter(salon=salon).exists():
            raise serializers.ValidationError(
                f"Мастер {specialist.full_name} не работает в салоне {salon.name}"
            )
        if procedure and not specialist.procedures.filter(pk=procedure.pk).exists():
            raise serializers.ValidationError(
                f"Мастер {specialist.full_name} не выполняет услугу {procedure.title}"
            )

        date = start_at.date()
        time = start_at.time()

        slots = get_available_slots(
            salon=salon, specialist=specialist, procedure=procedure, date=date
        )

        if time not in slots:
            raise serializers.ValidationError(f"Время {time} уже занято")

        return data
