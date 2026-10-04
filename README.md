# Event Booking System

A production-oriented backend implementation for the **Senior Backend Challenge – Event Booking System**.

The service is built with **Django** and **Django REST Framework (DRF)** and provides event creation, ticket reservations, booking confirmation, cancellation, event details, and reliable asynchronous reservation expiration.

The primary focus of the implementation is **correctness under concurrency**. The system is designed to ensure that concurrent booking requests can never cause the number of active reservations to exceed an event's capacity.

---

## 🎯 Challenge Requirements

The system implements the following core requirements:

* Create an event with:

  * Title
  * Description
  * Capacity
  * Event date
* Book a ticket for an event.
* Prevent active bookings from exceeding the event capacity.
* Allow only one active booking per user for each event.
* Make booking requests idempotent.
* Protect the booking flow against race conditions.
* Confirm pending bookings.
* Cancel pending or confirmed bookings.
* Automatically expire unconfirmed bookings after **10 minutes**.
* Release capacity when a booking is cancelled or expires.
* Provide event details including:

  * Total capacity
  * Active reservations (`PENDING + CONFIRMED`)
  * Confirmed reservations
  * Remaining capacity.

## The challenge specifically evaluates correctness, concurrency and transaction handling, code quality, architecture, database modeling, engineering trade-offs, scalability, and maintainability.

## 🏗️ Architecture

The project follows a layered architecture to keep HTTP concerns, validation, and business logic separated.

```text
┌──────────────────────────────┐
│           API Layer          │
│     Views / Serializers      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│        Service Layer         │
│       Business Logic         │
│  Booking / Confirmation /    │
│       Cancellation           │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         Domain Layer         │
│       Django Models          │
│     Events / Bookings        │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│          PostgreSQL          │
│ Transactions / Constraints   │
│       Row-level Locks        │
└──────────────────────────────┘

          Async Processing
                │
                ▼
       Celery + RabbitMQ
```

### Views

Views are intentionally thin.

They are responsible for:

* HTTP routing
* Authentication/authorization
* Passing validated data to the service layer
* Returning API responses

Business rules are not implemented directly inside views.

### Serializers

Serializers are responsible for:

* Request validation
* Input normalization
* Response serialization

They do not own the booking transaction or concurrency logic.

### Service Layer

The service layer contains the core business rules.

Examples include:

* Creating bookings
* Checking booking state
* Confirming bookings
* Cancelling bookings
* Handling capacity
* Managing idempotency
* Coordinating transactional operations

This keeps the business logic independent from the HTTP layer and makes it easier to test.

### Domain Models

The domain is separated into logical areas such as:

* `events`
* `bookings`
* `users`

This keeps the data model clear and maintainable.

---

# 🔒 Concurrency Strategy

Concurrency is the most critical part of the challenge.

The system must guarantee that:

```text
active bookings <= event capacity
```

even when many users attempt to reserve the same event concurrently.

The challenge explicitly allows approaches such as optimistic locking, pessimistic locking, database constraints, and `SELECT FOR UPDATE`, as long as the chosen strategy is documented.

## Pessimistic Row-Level Locking

The booking flow uses PostgreSQL row-level locking through Django's:

```python
select_for_update()
```

The important part of the booking transaction is conceptually:

```text
BEGIN TRANSACTION

        │
        ▼
Lock Event Row
(select_for_update)
        │
        ▼
Calculate Active Bookings
(PENDING + CONFIRMED)
        │
        ▼
Check Capacity
        │
   ┌────┴────┐
   │         │
Available   Full
   │         │
   ▼         ▼
Create      Reject
Booking     Booking
   │
   ▼
COMMIT
```

### Why pessimistic locking?

Booking systems can experience very high contention when many users attempt to reserve the same event simultaneously.

Without locking, two requests could both perform:

```text
Request A: active bookings = 99
Request B: active bookings = 99

Capacity = 100

A sees one available slot
B sees one available slot

A creates booking
B creates booking

Result: 101 active bookings
```

With row-level locking, only one transaction can perform the capacity check and modification for the event at a time.

The second transaction waits until the first transaction completes and then reads the latest state.

Therefore:

```text
Request A
    │
    ├── lock event
    ├── check capacity
    ├── create booking
    └── commit
             │
             ▼
Request B
    │
    ├── acquire lock
    ├── read updated state
    ├── check capacity
    └── reject if capacity is exhausted
```

This provides a strong consistency guarantee without introducing a separate distributed locking mechanism.

---

# 🛡️ Database Constraints

Application-level validation alone is not sufficient for correctness.

The service layer performs fail-fast validation, while PostgreSQL constraints provide an additional integrity boundary.

The booking rules include:

* A user cannot have multiple active bookings for the same event.
* Booking identifiers used for idempotency are unique.
* Invalid booking states cannot be transitioned through the normal service flow.

The combination of:

```text
Application validation
        +
Database constraints
        +
Transactional locking
```

provides multiple layers of protection against invalid state and concurrent requests.

---

# 🔄 Idempotency

The booking endpoint is idempotent.

The client provides an:

```http
Idempotency-Key: <unique-key>
```

when creating a booking.

If the client does not receive a response because of a network failure, it can safely retry the same request with the same idempotency key.

Instead of creating another booking, the system returns the existing booking associated with that key.

### Example

```text
First request
─────────────

Idempotency-Key: abc-123

Create Booking
      │
      ▼
Booking #1


Network timeout
      │
      ▼

Client retries
─────────────

Idempotency-Key: abc-123

      │
      ▼
Existing Booking #1
      │
      ▼
Return Booking #1
```

This prevents duplicate reservations caused by client retries or network failures.

---

# ⏱️ Reservation Lifecycle

A newly created booking starts in:

```text
PENDING
```

The user has **10 minutes** to confirm it.

The main lifecycle is:

```text
             ┌──────────────┐
             │    PENDING   │
             └──────┬───────┘
                    │
          ┌─────────┼─────────┐
          │         │         │
          ▼         ▼         ▼
      CONFIRMED   CANCELLED  EXPIRED
```

### PENDING → CONFIRMED

Only a `PENDING` booking can be confirmed.

After successful confirmation:

```text
PENDING
   │
   ▼
CONFIRMED
```

### PENDING → CANCELLED

A pending booking can be cancelled.

### CONFIRMED → CANCELLED

A confirmed booking can also be cancelled.

### PENDING → EXPIRED

If the booking is not confirmed within 10 minutes:

```text
PENDING
   │
   │ 10 minutes
   ▼
EXPIRED
```

When a booking expires, its capacity becomes available again.

## These lifecycle rules follow the challenge requirements.

# ⚙️ Asynchronous Expiration

Reservation expiration is handled asynchronously using:

* **Celery**
* **RabbitMQ**

When a booking is created, an expiration task is scheduled.

The task checks the current booking state before modifying it.

Conceptually:

```text
Booking Created
      │
      ▼
   PENDING
      │
      ├───────────────┐
      │               │
      ▼               ▼
 Confirmed        10 minutes
      │               │
      ▼               ▼
 CONFIRMED         Task runs
                      │
                      ▼
              Is booking still
                  PENDING?
                  /      \
                Yes       No
                 │         │
                 ▼         ▼
              EXPIRED   Do nothing
```

## Retry Safety

The expiration task is intentionally retry-safe.

A delayed or retried task must not accidentally expire a booking that has already been confirmed or cancelled.

Therefore, the task verifies that the booking is still in the expected `PENDING` state before transitioning it to `EXPIRED`.

This is important for worker restarts, delayed tasks, and message redelivery.

The challenge explicitly requires expiration to be reliable, restart-safe, and retry-safe.

---

# 💳 Booking Confirmation

Confirmation simulates the payment/confirmation step required by the challenge.

Only bookings in the `PENDING` state can be confirmed.

```text
PENDING
   │
   │ confirm
   ▼
CONFIRMED
```

A booking in any other state cannot be confirmed.

---

# ❌ Booking Cancellation

Users can cancel active bookings.

Allowed states:

```text
PENDING
CONFIRMED
```

After cancellation:

```text
PENDING ──────┐
              │
              ▼
           CANCELLED

CONFIRMED ────┘
```

The capacity previously occupied by the booking becomes available again.

This follows the challenge requirement that cancelling an active booking releases its capacity.

---

# 📊 Event Details

The event detail endpoint exposes the capacity information required by the challenge.

The response includes:

```text
Total Capacity
Active Reservations
Confirmed Reservations
Remaining Capacity
```

Where:

```text
Active Reservations =
    PENDING + CONFIRMED
```

and:

```text
Remaining Capacity =
    Total Capacity - Active Reservations
```

This makes the current availability of an event directly observable.

---

# 🗄️ Transaction Management

Operations that modify booking state are executed inside database transactions.

The booking flow is particularly important:

```text
BEGIN
  │
  ├── Lock event
  ├── Check existing idempotency key
  ├── Validate booking state
  ├── Check capacity
  ├── Create booking
  │
COMMIT
```

If any operation fails, the transaction is rolled back.

This ensures that the event state and booking state cannot be partially updated.

Correct transaction management is one of the explicit design expectations of the challenge.

---

# ⚖️ Engineering Trade-offs

## PostgreSQL Locking vs Redis Distributed Locks

The implementation uses PostgreSQL row-level locking instead of implementing a distributed lock with Redis.

The reason is that the critical resource being protected is already stored in PostgreSQL.

Using:

```python
select_for_update()
```

allows the database transaction to provide:

* Lock acquisition
* Transactional consistency
* Automatic lock release
* Atomic state changes

This avoids introducing another distributed coordination mechanism for the core booking transaction.

---

## Pessimistic vs Optimistic Locking

For this use case, pessimistic locking was selected because booking a limited-capacity event can create high contention on a single event.

Optimistic locking can be useful when conflicts are relatively rare and reads dominate writes.

For a high-contention ticket reservation scenario, however, pessimistic locking provides a straightforward consistency model:

```text
One event
    │
    ▼
One database row
    │
    ▼
One lock
    │
    ▼
Serialized capacity decisions
```

This makes the correctness argument easier to reason about and test.

---

## Application Validation vs Database Constraints

Application validation provides fast and clear error handling.

Database constraints provide a final integrity boundary.

The system therefore does not rely exclusively on Python code for critical uniqueness guarantees.

The design intentionally combines:

```text
Service-layer validation
        +
Database constraints
        +
Transactions
        +
Row-level locking
```

---

# 🧪 Testing

The test suite focuses particularly on the concurrency and transactional requirements of the challenge.

Important scenarios include:

* Event creation
* Booking creation
* Capacity enforcement
* Duplicate active booking prevention
* Idempotent booking requests
* Booking confirmation
* Booking cancellation
* Reservation expiration
* Concurrent booking requests
* Transactional integrity

## Concurrency Testing

The concurrency tests use multiple requests executing simultaneously against the same event.

The objective is to reproduce the condition described in the challenge:

```text
N concurrent booking requests
          │
          ▼
     Same Event
          │
          ▼
Never exceed Event.capacity
```

The tests therefore verify the most important invariant:

```text
active_bookings <= event.capacity
```

The challenge explicitly states that concurrency will be simulated during evaluation.

---

# 🚀 Getting Started

The project is containerized to make local setup and evaluation straightforward.

## 1. Configure Environment Variables

Create the local environment file from the provided example:

```bash
cp .env.example .env
```

Review the values in `.env` before starting the application.

## 2. Start the Application

Build and start the complete stack:

```bash
docker-compose up --build
```

The stack includes the required application and infrastructure services, including PostgreSQL, Redis, RabbitMQ, Django, and Celery.

Database migrations and the project's initial seed/setup process are executed as part of the application startup.

## 3. Access the API

The Django API is available at:

```text
http://localhost:8000
```

---

# 📖 API Documentation / Postman

A Postman collection is included in the repository:

```text
Documents/Postman/postman_collection
```

It can be imported into Postman to test the API endpoints.

The collection includes support for the authentication and booking flows.

### Authentication

The login request can automatically extract the authentication token and use it as a Bearer token for subsequent requests.

### Idempotency Testing

The booking request uses Postman's unique ID generation for the `Idempotency-Key`.

For example:

```text
Idempotency-Key: {{$guid}}
```

To test idempotency manually, send the same booking request twice while keeping the same `Idempotency-Key`.

The expected result is that the second request does not create another booking.

---

# 📁 Project Structure

The project is organized around clear domain and responsibility boundaries.

```text
.
├── events/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── ...
│
├── bookings/
│   ├── models.py
│   ├── serializers.py
│   ├── services.py
│   ├── tasks.py
│   ├── views.py
│   └── ...
│
├── users/
│   └── ...
│
├── Documents/
│   └── Postman/
│       └── postman_collection
│
├── .env.example
├── docker-compose.yml
└── README.md
```

The exact module organization may evolve, but the important architectural boundary is maintained:

```text
HTTP
 │
 ▼
Views / Serializers
 │
 ▼
Services
 │
 ▼
Models / Database
```

---

# 🔍 Key Design Decisions

| Requirement              | Design                                             |
| ------------------------ | -------------------------------------------------- |
| Prevent overselling      | PostgreSQL transaction + `select_for_update()`     |
| Concurrent bookings      | Pessimistic row-level locking                      |
| Duplicate active booking | Application validation + database constraints      |
| Retry-safe booking       | Idempotency key                                    |
| Booking confirmation     | Explicit booking state transition                  |
| Cancellation             | Explicit state transition + capacity release       |
| Reservation expiration   | Celery asynchronous task                           |
| Message delivery         | RabbitMQ                                           |
| Expiration retry safety  | Verify booking state before expiration             |
| Data consistency         | Database transactions                              |
| Maintainability          | Views, serializers, services, and models separated |

---

# 📈 Scalability Considerations

The critical booking operation is intentionally serialized **per event**, rather than globally.

For example:

```text
Event A ──► Lock Event A ──► Booking
Event B ──► Lock Event B ──► Booking
Event C ──► Lock Event C ──► Booking
```

Requests for different events do not need to wait for each other.

Only concurrent operations against the same event contend for the same database row.

This provides a practical scaling model while preserving the consistency required by the challenge.

The architecture also separates synchronous API operations from asynchronous expiration processing, allowing background work to be handled independently.

---

# ✅ Evaluation Focus

The implementation is specifically designed around the evaluation criteria described in the challenge:

### Correctness

* No overselling
* Correct booking state transitions
* Correct expiration behavior
* Correct capacity release

### Concurrency & Transactions

* Race-condition protection
* Transactional booking flow
* Explicit locking strategy

### Code Quality

* Clear project structure
* Separation of responsibilities
* Maintainable business logic
* Clean service boundaries

### Architecture & Design

* Database modeling
* Engineering trade-offs
* Scalability considerations
* Maintainability

These are the areas explicitly identified by the challenge as evaluation criteria.

---

# 📌 Challenge Deliverables

The challenge requires the source code to be provided in a GitHub repository together with a README documenting:

* How to run the project
* Architecture
* Design decisions
* Engineering trade-offs

This README provides that documentation alongside the implementation.
