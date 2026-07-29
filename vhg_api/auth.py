"""Challenge-password authentication helpers for the TDS JSON API."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable

from .config import ApiConfig
from .errors import AuthenticationError


DEFAULT_CHALLENGE_VALIDITY_SECONDS = 60


@dataclass(frozen=True)
class SecurityPayload:
    """Authentication fields added to secured TDS requests."""

    username: str
    dossier_id: str
    challenge: int
    challenge_password: str

    def as_dict(self) -> dict[str, str | int]:
        """Return fields in the format expected by the API."""
        return {
            "username": self.username,
            "dossier_id": self.dossier_id,
            "challenge": self.challenge,
            "challenge_password": self.challenge_password,
        }


def make_challenge(
    validity_seconds: int = DEFAULT_CHALLENGE_VALIDITY_SECONDS,
    *,
    time_provider: Callable[[], float] = time.time,
) -> int:
    """Return a UNIX expiry timestamp for a challenge password."""
    if validity_seconds <= 0:
        raise AuthenticationError("Challenge validity must be greater than zero seconds")
    return int(time_provider()) + validity_seconds


def calculate_challenge_password(encrypted_password: str, challenge: int | str) -> str:
    """Calculate SHA256(``encrypted_password + challenge``)."""
    password = str(encrypted_password).strip()
    challenge_text = str(challenge).strip()
    if not password:
        raise AuthenticationError("Encrypted password may not be empty")
    if not challenge_text.isdigit():
        raise AuthenticationError(f"Challenge must be an integer timestamp; got {challenge!r}")
    return hashlib.sha256(f"{password}{challenge_text}".encode("utf-8")).hexdigest()


def build_security_payload(
    api: ApiConfig,
    *,
    challenge: int | None = None,
    validity_seconds: int = DEFAULT_CHALLENGE_VALIDITY_SECONDS,
) -> SecurityPayload:
    """Build fresh security fields from an :class:`ApiConfig`."""
    resolved_challenge = challenge if challenge is not None else make_challenge(validity_seconds)
    return SecurityPayload(
        username=api.username,
        dossier_id=api.dossier_id,
        challenge=resolved_challenge,
        challenge_password=calculate_challenge_password(
            api.encrypted_password, resolved_challenge
        ),
    )
