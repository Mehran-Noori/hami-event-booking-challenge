from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.db.utils import IntegrityError
from .models import Event
from bookings.models import Booking
from bookings.enums import BookingStatus

User = get_user_model()


class EventTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="admin", password="password123")
        self.client.force_authenticate(user=self.user)
        self.event_date = timezone.now() + timedelta(days=5)

    def test_create_event_success(self):
        """Tests that an event can be created with a positive capacity."""
        payload = {
            "title": "Test Event",
            "description": "A description",
            "capacity": 100,
            "event_date": self.event_date.isoformat(),
        }
        response = self.client.post("/api/events/", payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.count(), 1)

    def test_create_event_negative_capacity_fails(self):
        """Tests that database constraints prevent negative capacity[cite: 1]."""
        with self.assertRaises(IntegrityError):
            Event.objects.create(
                title="Bad Event", capacity=-5, event_date=self.event_date
            )

    def test_get_event_detail_stats(self):
        """Tests that the detail API correctly aggregates capacity and bookings[cite: 2]."""
        event = Event.objects.create(
            title="Stats Event", capacity=10, event_date=self.event_date
        )

        user2 = User.objects.create_user(username="user2", password="password123")
        user3 = User.objects.create_user(username="user3", password="password123")

        import uuid

        Booking.objects.create(
            user=self.user,
            event=event,
            status=BookingStatus.PENDING,
            idempotency_key=uuid.uuid4(),
        )
        Booking.objects.create(
            user=user2,
            event=event,
            status=BookingStatus.PENDING,
            idempotency_key=uuid.uuid4(),
        )
        Booking.objects.create(
            user=user3,
            event=event,
            status=BookingStatus.CONFIRMED,
            idempotency_key=uuid.uuid4(),
        )

        response = self.client.get(f"/api/events/{event.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertEqual(data["total_capacity"], 10)
        self.assertEqual(data["active_bookings"], 3)  
        self.assertEqual(data["confirmed_bookings"], 1)
        self.assertEqual(data["remaining_capacity"], 7)  
