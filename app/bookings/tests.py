import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.db import connection, IntegrityError
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from events.models import Event
from .models import Booking
from .enums import BookingStatus
from .tasks import expire_booking_task
from .exceptions import CapacityExceededError

User = get_user_model()


class BookingBusinessLogicTests(TestCase):
    def setUp(self):
        patcher = patch("bookings.services.expire_booking_task.apply_async")
        self.mock_expire = patcher.start()
        self.addCleanup(patcher.stop)

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="testuser", password="password123"
        )
        self.client.force_authenticate(user=self.user)
        self.event = Event.objects.create(
            title="Concert", capacity=5, event_date=timezone.now() + timedelta(days=2)
        )
        self.idempotency_key = str(uuid.uuid4())

    def test_idempotent_booking_creation(self):
        payload = {"event_id": self.event.id}
        headers = {"HTTP_IDEMPOTENCY_KEY": self.idempotency_key}

        res1 = self.client.post("/api/bookings/", payload, **headers)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.count(), 1)

        res2 = self.client.post("/api/bookings/", payload, **headers)
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(res1.json()["id"], res2.json()["id"])

    def test_one_active_booking_per_user(self):
        payload = {"event_id": self.event.id}

        self.client.post(
            "/api/bookings/", payload, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )

        res = self.client.post(
            "/api/bookings/", payload, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already have an active booking", res.json()["error"])

    def test_confirm_and_cancel_state_rules(self):
        booking = Booking.objects.create(
            user=self.user,
            event=self.event,
            idempotency_key=self.idempotency_key,
            status=BookingStatus.PENDING,
        )

        res = self.client.post(f"/api/bookings/{booking.id}/confirm/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CONFIRMED)

        res2 = self.client.post(f"/api/bookings/{booking.id}/confirm/")
        self.assertEqual(res2.status_code, status.HTTP_409_CONFLICT)

        res3 = self.client.post(f"/api/bookings/{booking.id}/cancel/")
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.CANCELED)

    def test_celery_expiration_task(self):
        booking = Booking.objects.create(
            user=self.user,
            event=self.event,
            idempotency_key=self.idempotency_key,
            status=BookingStatus.PENDING,
        )

        expire_booking_task(booking.id)

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingStatus.EXPIRED)


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        patcher = patch("bookings.services.expire_booking_task.apply_async")
        self.mock_expire = patcher.start()
        self.addCleanup(patcher.stop)

        self.capacity = 3
        self.event = Event.objects.create(
            title="High Demand Event",
            capacity=self.capacity,
            event_date=timezone.now() + timedelta(days=2),
        )
        self.users = [
            User.objects.create_user(username=f"user{i}", password="password123")
            for i in range(10)
        ]

    def test_prevent_overselling_under_race_condition(self):
        # Skip if SQLite because it ignores row-level locks
        if "sqlite" in settings.DATABASES["default"]["ENGINE"]:
            self.skipTest(
                "SQLite does not support select_for_update locking. Skipping concurrency test."
            )

        from bookings.services import book_ticket

        def attempt_booking(user):
            connection.close()
            try:
                book_ticket(
                    user=user, event_id=self.event.id, idempotency_key=str(uuid.uuid4())
                )
                return True
            except CapacityExceededError:
                return False
            except Exception:
                return False
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(attempt_booking, self.users))

        successful_bookings = results.count(True)
        self.assertEqual(successful_bookings, self.capacity)
