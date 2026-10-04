from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Event
from .serializers import EventSerializer, EventDetailSerializer
from . import services


class EventViewSet(viewsets.ModelViewSet):

    def get_permissions(self):

        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        if self.action == "retrieve":
            return services.get_events_with_stats()
        return Event.active_objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return EventDetailSerializer
        return EventSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event = services.create_event(serializer.validated_data)

        response_serializer = self.get_serializer(event)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
