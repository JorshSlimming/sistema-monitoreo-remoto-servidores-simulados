# Attack Simulation

This document describes the authorized local attacker simulator, a security
hardening tool that validates the system's protocol-level defenses without
requiring external tooling or offensive capabilities.

## Overview

The attacker simulator (`attacker/attack_simulator.py`) is a self-contained
CLI tool that performs **7 controlled attacks** against the monitor server's
TCP protocol. It connects as a malicious client and verifies that each
security control correctly detects and rejects the attack.

All attacks target **localhost only** by default. Non-local targets require
an explicit environment override (see below).

## Attack catalog

| # | Attack key | What it does | Expected protection | Risk level |
|---|---|---|---|---|
| 1 | `plaintext-metric` | Sends a metric as plain JSON without completing the PSK handshake | Server rejects with `HANDSHAKE_REQUIRED` | MEDIUM |
| 2 | `unknown-node` | Initiates handshake with a `node_id` that has no configured PSK | Server rejects with `AUTH_FAILED` (unknown node) | HIGH |
| 3 | `bad-psk` | Responds to handshake challenge with an incorrect HMAC proof | Server rejects with `AUTH_FAILED` (invalid proof) | HIGH |
| 4 | `node-mismatch` | Authenticates as `node-01` but sends a metric claiming `node-02` | Server rejects with `AUTH_FAILED` (node mismatch) | HIGH |
| 5 | `invalid-metric` | Sends a metric with CPU=999 (out of valid range) | Server rejects with `INVALID_MESSAGE` | LOW |
| 6 | `tampered-frame` | Sends a secure frame with deliberately corrupted ciphertext/tag | Server detects invalid frame tag and closes connection | HIGH |
| 7 | `replay-frame` | Replays a previously seen sequence number in a new session | Server rejects duplicate seq with `invalid secure frame sequence` | HIGH |

## Usage

### Run all attacks against local server

```bash
python3 -m attacker.attack_simulator --attack all
```

### Run a single attack

```bash
python3 -m attacker.attack_simulator --attack bad-psk
```

### JSON output (for programmatic consumption)

```bash
python3 -m attacker.attack_simulator --attack all --json
```

### Custom target

```bash
python3 -m attacker.attack_simulator --host 127.0.0.1 --port 5000 --attack node-mismatch
```

### Via Makefile

```bash
make attack
```

### Generate attack evidence artifacts

```bash
make attack-evidence
```

## Security boundaries

### Local-only by default

The attacker enforces an allowlist by default:

- `127.0.0.1`
- `localhost`
- `::1`

Any other host raises a `ValueError` immediately.

### Opt-in non-local targeting

Set the environment variable to override:

```bash
ALLOW_NON_LOCAL_ATTACK_TARGET=1 python3 -m attacker.attack_simulator --host 10.0.0.5
```

This is intended only for controlled demo environments (e.g., two VMs on the
same isolated network).  Do not use against production or external systems.

### No offensive capabilities

The simulator is strictly read-only / protocol-level. It does not:

- Scan arbitrary networks or ports
- Perform brute-force attacks
- Exploit buffer overflows or injection vulnerabilities
- Execute arbitrary shell commands
- Exfiltrate data
- Target external hosts

## Result format

Each attack returns a JSON object with these fields:

| Field | Type | Description |
|---|---|---|
| `attack_id` | string | Sequential ID (`attack-001`…) |
| `name` | string | Human-readable attack name |
| `description` | string | What the attack does |
| `expected_result` | string | What the server should do |
| `success` | bool | `True` if the server correctly detected/rejected the attack |
| `server_response` | string or null | Raw server response if received |
| `observed_error` | string or null | Error message if attack execution failed |
| `timestamp` | string | ISO-8601 UTC timestamp |
| `duration_ms` | number | Attack execution time in milliseconds |
| `risk_level_demo` | string | Demo risk rating (LOW / MEDIUM / HIGH) |
| `authorized_scope` | string | Always `"local-authorized-testing"` |

## Dashboard integration

The dashboard exposes four attack-related API endpoints:

| Endpoint | Method | Description |
|---|---|---|
| `/api/attacks` | GET | List available attacks from the catalog |
| `/api/attack/run` | POST | Execute one or all attacks against the monitor server |
| `/api/attack/latest` | GET | Return the latest attack run artifact |
| `/api/attack/status` | GET | Attack subsystem status (available attacks, latest run summary) |

The `POST /api/attack/run` endpoint also enforces the local-only target
policy. Non-local hosts are rejected with HTTP 403 unless the
`ALLOW_NON_LOCAL_ATTACK_TARGET` environment variable is set.

## Integration with evidence pipeline

Running `make attack-evidence` generates:

1. Attack results JSON under `artifacts/demo/attack_results_<timestamp>.json`
2. Merged `evidence_index.json` with attack summary

`make evidence` now runs both the normal demo evidence pipeline and the attack
evidence pipeline, so a single command produces the complete artifact set for
the final demo. `make attack-evidence` remains available when only the attack
artifacts are needed against an already-running demo server.

## Tests

```bash
python3 -m unittest tests.test_attack_simulator -v
python3 -m unittest tests.test_dashboard_attack_api -v
```

Coverage includes:
- Result shape validation for each attack (even when server is down)
- Attack detection against a real server
- Non-persistence verification (tampered/replay metrics not saved)
- Cross-node ACK rejection
- Non-local host rejection
