from rest_framework import status


class BookingException(Exception):
    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class CapacityExceededError(BookingException):
    def __init__(self):
        super().__init__("Event is fully booked.", status.HTTP_409_CONFLICT)


class InvalidBookingStateError(BookingException):
    def __init__(self, message="Invalid state transition."):
        super().__init__(message, status.HTTP_409_CONFLICT)


class DuplicateBookingError(BookingException):
    def __init__(self):
        super().__init__(
            "You already have an active booking.", status.HTTP_409_CONFLICT
        )


class MissingIdempotencyKeyError(BookingException):
    def __init__(self):
        super().__init__(
            "Idempotency-Key header is required.", status.HTTP_400_BAD_REQUEST
        )
