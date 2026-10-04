from django.db.models import Count, Q, F
from .models import Event
from bookings.enums import BookingStatus


def create_event(validated_data):
    """
    Handles the business logic for creating a new event.
    Keeps the viewset clean and allows for future business rule additions.
    """
    # The database constraints will automatically enforce that capacity > 0
    return Event.objects.create(**validated_data)


def get_events_with_stats():
    return Event.active_objects.annotate(
        active_bookings_count=Count(
            "bookings",
            filter=Q(
                bookings__status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED],
                bookings__is_deleted=False,
            ),
        ),
        confirmed_bookings_count=Count(
            "bookings",
            filter=Q(
                bookings__status=BookingStatus.CONFIRMED, bookings__is_deleted=False
            ),
        ),
    ).annotate(remaining_capacity=F("capacity") - F("active_bookings_count"))
