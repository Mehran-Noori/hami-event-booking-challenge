from celery import shared_task
from django.db import OperationalError, transaction

from .models import Booking, BookingStatus


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
)
def expire_booking_task(self, booking_id):
    try:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(id=booking_id)

            if booking.status != BookingStatus.PENDING:
                return

            booking.status = BookingStatus.EXPIRED
            booking.save(update_fields=["status"])

    except OperationalError as exc:
        raise self.retry(
            exc=exc,
            countdown=min(2**self.request.retries, 60),
        )
