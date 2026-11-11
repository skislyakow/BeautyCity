from django.templatetags.static import static

from .models import Booking
from .phone_auth import get_user_phone


def account_name(request):
    user = request.user
    default_avatar = static("img/avatars/user.svg")
    if not user.is_authenticated:
        return {"user_avatar": default_avatar}

    profile = getattr(user, "profile", None)
    phone = get_user_phone(user)
    name = (profile.first_name if profile else "") or user.first_name
    if not name and phone:
        latest = (
            Booking.objects.filter(phone=phone)
            .exclude(customer_name="")
            .order_by("-created_at")
            .values_list("customer_name", flat=True)
            .first()
        )
        if latest:
            name = latest
            user.first_name = latest
            user.save(update_fields=["first_name"])
            if profile:
                profile.first_name = latest
                profile.save(update_fields=["first_name"])

    return {
        "account_name": name or phone or user.username,
        "user_avatar": profile.get_avatar_url() if profile else default_avatar,
    }
