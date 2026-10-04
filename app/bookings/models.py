from django.db import models
from users.models import User
from django.db.models import Q
from core.models import BaseModel
from events.models import Event
from .enums import BookingStatus


class Booking(BaseModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT, db_index=True)
    event = models.ForeignKey(
        Event, on_delete=models.PROTECT, related_name="bookings", db_index=True
    )
    status = models.CharField(
        max_length=15,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
        db_index=True,
    )
    idempotency_key = models.UUIDField(
        unique=True, help_text="Ensures idempotent requests"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=Q(status__in=["PENDING", "CONFIRMED"], is_deleted=False),
                name="unique_active_booking_per_user",
            )
        ]
        indexes = [
            models.Index(fields=["event", "status", "is_deleted"]),
            models.Index(fields=["user", "status", "is_deleted"]),
        ]
