from .models import Booking


def account_name(request):
    """Имя клиента для шапки и личного кабинета: имя → имя из последней записи → телефон."""
    user = request.user
    if not user.is_authenticated:
        return {}

    if not user.first_name:
        latest = (
            Booking.objects
            .filter(phone=user.username)
            .exclude(customer_name='')
            .order_by('-created_at')
            .values_list('customer_name', flat=True)
            .first()
        )
        if latest:
            user.first_name = latest
            user.save(update_fields=['first_name'])

    return {'account_name': user.first_name or user.username}
