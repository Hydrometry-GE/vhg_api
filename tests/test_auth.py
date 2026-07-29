from __future__ import annotations

import pytest

from vhg_api.auth import calculate_challenge_password, make_challenge
from vhg_api.errors import AuthenticationError


def test_documented_challenge_password_vector() -> None:
    encrypted = "09da4e416785b0270a63e17e8b1313f4e29b814071892fe528060b17c1f0cf09"
    assert calculate_challenge_password(encrypted, 1546027813) == (
        "e171c40735aae045353f9ffb617c4307037c17c91263bcd02931e24de3c4613f"
    )


def test_make_challenge_uses_expiry_timestamp() -> None:
    assert make_challenge(60, time_provider=lambda: 1000.9) == 1060


def test_empty_password_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match="may not be empty"):
        calculate_challenge_password("", 123)
