from rest_framework import serializers
from .models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["id", "title", "description", "capacity", "event_date"]


class EventDetailSerializer(serializers.ModelSerializer):
    total_capacity = serializers.IntegerField(source="capacity", read_only=True)
    active_bookings = serializers.IntegerField(
        source="active_bookings_count", read_only=True
    )
    confirmed_bookings = serializers.IntegerField(
        source="confirmed_bookings_count", read_only=True
    )
    remaining_capacity = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "total_capacity",
            "active_bookings",
            "confirmed_bookings",
            "remaining_capacity",
        ]
