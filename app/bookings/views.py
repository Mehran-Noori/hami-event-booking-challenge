from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ObjectDoesNotExist

from . import services
from .serializers import BookingSerializer
from .exceptions import BookingException, MissingIdempotencyKeyError


class BookingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        try:
            idempotency_key = request.headers.get("Idempotency-Key")
            if not idempotency_key:
                raise MissingIdempotencyKeyError()

            booking = services.book_ticket(
                user=request.user,
                event_id=request.data.get("event_id"),
                idempotency_key=idempotency_key,
            )
            return Response(
                BookingSerializer(booking).data, status=status.HTTP_201_CREATED
            )
        except BookingException as e:
            return Response({"error": e.message}, status=e.status_code)
        except ObjectDoesNotExist:
            return Response(
                {"error": "Event not found."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        try:
            booking = services.confirm_booking(booking_id=pk, user=request.user)
            return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)
        except BookingException as e:
            return Response({"error": e.message}, status=e.status_code)
        except ObjectDoesNotExist:
            return Response(
                {"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            booking = services.cancel_booking(booking_id=pk, user=request.user)
            return Response(BookingSerializer(booking).data, status=status.HTTP_200_OK)
        except BookingException as e:
            return Response({"error": e.message}, status=e.status_code)
        except ObjectDoesNotExist:
            return Response(
                {"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND
            )
