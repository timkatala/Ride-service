import pytest

from src.domain.state_machine import BookingStatus as S
from src.domain.state_machine import Decision, decide


@pytest.mark.parametrize(
    "current, target, expected",
    [
        (S.PENDING, S.SUBMITTED, Decision.APPLY),
        (S.SUBMITTED, S.ACCEPTED, Decision.APPLY),
        (S.SUBMITTED, S.COMPLETED, Decision.APPLY),
        (S.ACCEPTED, S.DRIVER_ASSIGNED, Decision.APPLY),
        (S.DRIVER_ASSIGNED, S.COMPLETED, Decision.APPLY),
        (S.ACCEPTED, S.ACCEPTED, Decision.DUPLICATE),
        (S.COMPLETED, S.COMPLETED, Decision.DUPLICATE),
        (S.DRIVER_ASSIGNED, S.ACCEPTED, Decision.STALE),
        (S.COMPLETED, S.DRIVER_ASSIGNED, Decision.STALE),
        (S.CANCELLED, S.ACCEPTED, Decision.STALE),
        (S.EXPIRED, S.DRIVER_ASSIGNED, Decision.STALE),
        (S.EXPIRED, S.CANCELLED, Decision.STALE),
        (S.COMPLETED, S.CANCELLED, Decision.REJECT),
        (S.CANCELLED, S.COMPLETED, Decision.REJECT),
        (S.EXPIRED, S.COMPLETED, Decision.REJECT),
        (S.DRIVER_ASSIGNED, S.EXPIRED, Decision.REJECT),
        (S.PENDING, S.DRIVER_ASSIGNED, Decision.REJECT),
    ],
)
def test_decide(current, target, expected):
    assert decide(current, target) == expected
