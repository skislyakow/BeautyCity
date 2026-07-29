from datetime import datetime, time, timedelta
from django.utils.timezone import make_aware, now, localtime
from .models import WorkShift, Booking

SLOT_STEP_MINUTES = 30


def get_available_slots(*, salon, specialist, procedure, date):
    """
    Возвращает список доступных времен (time) для:
    - салона
    - мастера
    - процедуры
    - конкретной даты
    """

    shifts = WorkShift.objects.filter(
        salon=salon,
        specialist=specialist,
        date=date,
    ).order_by("start_time")

    if not shifts.exists():
        return []

    duration = timedelta(minutes=procedure.duration_minutes)
    step = timedelta(minutes=SLOT_STEP_MINUTES)

    day_start = make_aware(datetime.combine(date, time.min))
    day_end = make_aware(datetime.combine(date, time.max))

    bookings = Booking.objects.filter(
        salon=salon,
        specialist=specialist,
        start_at__gte=day_start,
        start_at__lte=day_end,
    ).exclude(status=Booking.Status.CANCELED)

    booked_intervals = [(b.start_at, b.end_at) for b in bookings]

    now_dt = localtime(now())
    available_times = []

    for shift in shifts:
        if not isinstance(shift.start_time, time) or not isinstance(shift.end_time, time):
            continue
        if shift.start_time >= shift.end_time:
            continue

        current_start = make_aware(datetime.combine(date, shift.start_time))
        shift_end = make_aware(datetime.combine(date, shift.end_time))

        while current_start + duration <= shift_end:
            if current_start < now_dt:
                current_start += step
                continue

            current_end = current_start + duration

            conflict = any(
                not (current_end <= b_start or current_start >= b_end)
                for b_start, b_end in booked_intervals
            )

            if not conflict:
                available_times.append(current_start.time())

            current_start += step

    available_times.sort()
    return available_times