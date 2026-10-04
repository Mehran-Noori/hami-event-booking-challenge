from django.db import models
from django.db.models import Q
from core.models import BaseModel


class Event(BaseModel):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    capacity = models.PositiveIntegerField()
    event_date = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=Q(capacity__gt=0), name="capacity_positive_check"
            )
        ]
        indexes = [
            # Optimizes queries looking for active upcoming events
            models.Index(fields=["event_date", "is_active", "is_deleted"]),
        ]

    def __str__(self):
        return self.title
