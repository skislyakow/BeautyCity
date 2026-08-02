from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Salon, Procedure, ProcedureOffering,
    Specialist, SpecialistSalon, WorkShift,
    PromoCode, ConsentDocument, ConsentAcceptance,
    CustomerProfile, Booking, SiteSettings, CallbackRequest
)


def image_preview(obj, field_name: str, size: int = 60):
    field = getattr(obj, field_name, None)
    if not field:
        return "—"
    try:
        url = field.url
    except Exception:
        return "—"
    return format_html(
        '<img src="{}" style="width:{}px;height:{}px;object-fit:cover;border-radius:8px;" />',
        url, size, size
    )


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ("preview", "name", "address", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "address")
    readonly_fields = ("preview_large",)

    def preview(self, obj):
        return image_preview(obj, "image", size=44)
    preview.short_description = "Фото"

    def preview_large(self, obj):
        return image_preview(obj, "image", size=180)
    preview_large.short_description = "Превью"



@admin.register(Procedure)
class ProcedureAdmin(admin.ModelAdmin):
    list_display = ("preview", "title", "duration_minutes", "base_price")
    search_fields = ("title",)
    readonly_fields = ("preview_large",)

    def preview(self, obj):
        return image_preview(obj, "image", size=44)
    preview.short_description = "Фото"

    def preview_large(self, obj):
        return image_preview(obj, "image", size=180)
    preview_large.short_description = "Превью"



@admin.register(ProcedureOffering)
class ProcedureOfferingAdmin(admin.ModelAdmin):
    list_display = ("salon", "procedure", "price")
    list_filter = ("salon",)
    search_fields = ("procedure__title", "salon__name")


@admin.register(Specialist)
class SpecialistAdmin(admin.ModelAdmin):
    list_display = ("preview", "full_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name",)
    readonly_fields = ("preview_large",)

    def preview(self, obj):
        return image_preview(obj, "photo", size=44)
    preview.short_description = "Фото"

    def preview_large(self, obj):
        return image_preview(obj, "photo", size=180)
    preview_large.short_description = "Превью"



@admin.register(SpecialistSalon)
class SpecialistSalonAdmin(admin.ModelAdmin):
    list_display = ("specialist", "salon")
    list_filter = ("salon", "specialist")
    search_fields = ("specialist__full_name", "salon__name")


@admin.register(WorkShift)
class WorkShiftAdmin(admin.ModelAdmin):
    list_display = ("date", "start_time", "end_time", "specialist", "salon")
    list_filter = ("salon", "specialist", "date")
    search_fields = ("specialist__full_name", "salon__name")
    date_hierarchy = "date"


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "is_active", "valid_from", "valid_to")
    list_filter = ("is_active",)
    search_fields = ("code",)


@admin.register(ConsentDocument)
class ConsentDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "uploaded_at")
    list_filter = ("is_active",)
    search_fields = ("title",)


@admin.register(ConsentAcceptance)
class ConsentAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("accepted_at", "user", "phone", "document")
    list_filter = ("document", "accepted_at")
    search_fields = ("phone", "user__username", "user__email")
    date_hierarchy = "accepted_at"


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "created_at")
    search_fields = ("user__username", "user__email", "phone")
    date_hierarchy = "created_at"


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("start_at", "salon", "procedure", "specialist", "phone", "status", "source", "price_final")
    list_filter = ("status", "source", "salon", "procedure")
    search_fields = ("phone", "customer_name", "specialist__full_name")
    date_hierarchy = "start_at"


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("manager_phone",)


@admin.register(CallbackRequest)
class CallbackRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "is_processed", "created_at")
    list_filter = ("is_processed",)
    search_fields = ("name", "phone")
    date_hierarchy = "created_at"