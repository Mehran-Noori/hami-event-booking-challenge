from django.db import transaction, IntegrityError
from events.models import Event
from .models import Booking
from .enums import BookingStatus
from .exceptions import (
    CapacityExceededError,
    InvalidBookingStateError,
    DuplicateBookingError,
)
from .tasks import expire_booking_task


@transaction.atomic
def book_ticket(user, event_id, idempotency_key):
    existing_booking = Booking.objects.filter(idempotency_key=idempotency_key).first()
    if existing_booking:
        return existing_booking

    if Booking.objects.filter(
        user=user,
        event_id=event_id,
        status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED],
        is_deleted=False,
    ).exists():
        raise DuplicateBookingError()

    event = Event.active_objects.select_for_update().get(id=event_id)

    active_count = event.bookings.filter(
        status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED], is_deleted=False
    ).count()

    if active_count >= event.capacity:
        raise CapacityExceededError()

    try:
        with transaction.atomic():
            booking = Booking.objects.create(
                user=user,
                event=event,
                status=BookingStatus.PENDING,
                idempotency_key=idempotency_key,
            )
    except IntegrityError:
        raise DuplicateBookingError()

    expire_booking_task.apply_async((booking.id,), countdown=600)
    return booking


@transaction.atomic
def confirm_booking(booking_id, user):
    booking = Booking.active_objects.select_for_update().get(id=booking_id, user=user)
    if booking.status != BookingStatus.PENDING:
        raise InvalidBookingStateError()

    booking.status = BookingStatus.CONFIRMED
    booking.save()
    return booking


@transaction.atomic
def cancel_booking(booking_id, user):
    booking = Booking.active_objects.select_for_update().get(id=booking_id, user=user)
    if booking.status not in [BookingStatus.PENDING, BookingStatus.CONFIRMED]:
        raise InvalidBookingStateError()

    booking.status = BookingStatus.CANCELED
    booking.save()
    return booking
