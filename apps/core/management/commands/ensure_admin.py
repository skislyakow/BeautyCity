from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.core.models import CustomerProfile


ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "Admin"
ADMIN_PHONE = "+79999999999"


class Command(BaseCommand):
    help = "Создаёт/обновляет системного администратора (Джанго-админка + админка сайта)"

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username=ADMIN_USERNAME,
            defaults={
                "first_name": "Системный администратор",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.is_staff = True
        user.is_superuser = True
        user.set_password(ADMIN_PASSWORD)
        user.save()

        profile, profile_created = CustomerProfile.objects.get_or_create(
            user=user,
            defaults={"phone": ADMIN_PHONE},
        )
        if profile.phone != ADMIN_PHONE:
            profile.phone = ADMIN_PHONE
            profile.save(update_fields=["phone"])

        if created:
            self.stdout.write(self.style.SUCCESS(f"Системный администратор создан: {ADMIN_USERNAME}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Системный администратор обновлён: {ADMIN_USERNAME}"))
        self.stdout.write(f"Логин: {ADMIN_USERNAME} / пароль: {ADMIN_PASSWORD} / телефон: {ADMIN_PHONE}")
