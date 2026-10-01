from enum import StrEnum


class BookingStatus(StrEnum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    DRIVER_ASSIGNED = "driver_assigned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Decision(StrEnum):
    APPLY = "applied"
    DUPLICATE = "duplicate"
    STALE = "stale"
    REJECT = "rejected"


S = BookingStatus

TERMINAL = frozenset({S.COMPLETED, S.CANCELLED, S.EXPIRED})

ALLOWED_TRANSITIONS: dict[BookingStatus, frozenset[BookingStatus]] = {
    S.PENDING: frozenset({S.SUBMITTED, S.CANCELLED, S.EXPIRED}),
    S.SUBMITTED: frozenset({S.ACCEPTED, S.DRIVER_ASSIGNED, S.COMPLETED, S.CANCELLED, S.EXPIRED}),
    S.ACCEPTED: frozenset({S.DRIVER_ASSIGNED, S.COMPLETED, S.CANCELLED, S.EXPIRED}),
    S.DRIVER_ASSIGNED: frozenset({S.COMPLETED, S.CANCELLED}),
    S.COMPLETED: frozenset(),
    S.CANCELLED: frozenset(),
    S.EXPIRED: frozenset(),
}

HAPPY_PATH = [S.PENDING, S.SUBMITTED, S.ACCEPTED, S.DRIVER_ASSIGNED, S.COMPLETED]

IN_FLIGHT = frozenset({S.SUBMITTED, S.ACCEPTED, S.DRIVER_ASSIGNED})
WAITING_FOR_DRIVER = frozenset({S.PENDING, S.SUBMITTED, S.ACCEPTED})


def decide(current: BookingStatus, target: BookingStatus) -> Decision:
    if target == current:
        return Decision.DUPLICATE
    if target in ALLOWED_TRANSITIONS[current]:
        return Decision.APPLY
    if _already_passed(current, target):
        return Decision.STALE
    return Decision.REJECT


def _already_passed(current: BookingStatus, target: BookingStatus) -> bool:
    if current == S.EXPIRED and target == S.CANCELLED:
        return True
    if target in TERMINAL:
        return False
    if current in TERMINAL:
        return True
    return HAPPY_PATH.index(target) < HAPPY_PATH.index(current)
