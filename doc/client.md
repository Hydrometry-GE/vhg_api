# TDS client

## Authentication

All operations except `ping` receive these fields:

- `username`
- `dossier_id`
- `challenge`: UNIX expiry timestamp
- `challenge_password`: SHA256 of `encrypted_password + challenge`

A fresh challenge is generated for each secured request.

## Proxy behavior

Proxy use is controlled only by `proxy.enabled` in `settings.yml`. The HTTP client sets `Session.trust_env = False`, so machine-level `HTTP_PROXY` or `HTTPS_PROXY` variables cannot silently activate a proxy when configuration says it is disabled.

## TLS certificate verification

TLS verification is enabled by default. With `tls.verify: true` and an empty
`tls.ca_bundle`, Requests uses its normal CA trust store. With verification
enabled and a CA bundle configured, the session uses that PEM bundle as its
verification trust store. Setting `tls.verify: false` explicitly sets the
Requests session to `verify=False`; this is intended only for controlled
environments where certificate verification cannot be used. An empty CA bundle
never disables verification automatically.

## Manual test sequence

1. `00_project_info.py`
2. `01_test_config.py`
3. `02_test_auth.py`
4. `03_test_ping.py`
5. `04_test_access.py`

`03` checks that the configured server answers `pong`. `04` validates credentials and displays view, manage, import, and export rights.
