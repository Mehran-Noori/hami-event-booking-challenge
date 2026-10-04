from django.db import models


class ActiveManager(models.Manager):
    """Custom manager to automatically filter out soft-deleted and inactive records."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False, is_active=True)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    # Managers
    objects = models.Manager()
    active_objects = ActiveManager()

    class Meta:
        abstract = True
