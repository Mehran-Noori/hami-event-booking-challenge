from django.db import models


class BookingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    CONFIRMED = "CONFIRMED", "Confirmed"
    CANCELED = "CANCELED", "Canceled"
    EXPIRED = "EXPIRED", "Expired"
