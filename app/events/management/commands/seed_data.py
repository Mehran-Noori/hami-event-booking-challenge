from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from events.models import Event
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                if not User.objects.filter(username="evaluator").exists():
                    User.objects.create_user(
                        username="evaluator", password="password123"
                    )
                    self.stdout.write(
                        self.style.SUCCESS("Created Test User: evaluator")
                    )
        except IntegrityError:
            self.stdout.write(
                self.style.WARNING("Test User already created by another container.")
            )

        try:
            with transaction.atomic():
                if not Event.objects.exists():
                    Event.objects.create(
                        title="Senior Backend Challenge Event",
                        capacity=5,
                        event_date=timezone.now() + timedelta(days=10),
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Created Test Event: Senior Backend Challenge Event"
                        )
                    )
        except IntegrityError:
            self.stdout.write(
                self.style.WARNING("Test Event already created by another container.")
            )
