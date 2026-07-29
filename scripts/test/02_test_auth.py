"""Validate local challenge-password generation. Run with F5 in Spyder."""

from __future__ import annotations

from _bootstrap import PROJECT_ROOT
from vhg_api.auth import build_security_payload, calculate_challenge_password
from vhg_api.config import ConfigError, load_config
from vhg_api.console import print_error, print_header, print_success
from vhg_api.errors import AuthenticationError

SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yml"
ENV_FILE = PROJECT_ROOT / "config" / ".env"

# Published example from the TDS JSON API documentation.
EXAMPLE_ENCRYPTED_PASSWORD = (
    "09da4e416785b0270a63e17e8b1313f4e29b814071892fe528060b17c1f0cf09"
)
EXAMPLE_CHALLENGE = 1546027813
EXAMPLE_RESULT = "e171c40735aae045353f9ffb617c4307037c17c91263bcd02931e24de3c4613f"


def main() -> None:
    print_header("vhg_api - Authentication test")

    try:
        documented = calculate_challenge_password(
            EXAMPLE_ENCRYPTED_PASSWORD, EXAMPLE_CHALLENGE
        )
        if documented != EXAMPLE_RESULT:
            raise AuthenticationError("Published authentication test vector did not match")
        print_success("Published SHA256 test vector matches.")

        config = load_config(SETTINGS_FILE, ENV_FILE)
        security = build_security_payload(config.api)
    except (ConfigError, AuthenticationError) as exc:
        print_error(str(exc))
        return

    print(f"Username     : {security.username}")
    print(f"Dossier ID   : {security.dossier_id}")
    print(f"Challenge    : {security.challenge}")
    print(f"Password hash: {security.challenge_password[:8]}...{security.challenge_password[-8:]}")
    print_success("A fresh security payload was generated without exposing credentials.")
    print("\nNext manual test: scripts/test/03_test_ping.py")


if __name__ == "__main__":
    main()
