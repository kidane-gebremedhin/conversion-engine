# Infra

Local infrastructure for the Conversion Engine dev loop.

## Contents

- `docker-compose.yml` — Cal.com self-hosted + Postgres.
- `smoke_test.sh` — five-green-check readiness test (`make smoke`).
- `acknowledgement_signed.txt` — UTC timestamp of policy acknowledgement (written by `make ack`).

## First-boot

```bash
make ack                                     # drop acknowledgement timestamps
cp .env.calcom.example .env.calcom           # fill NEXTAUTH_SECRET, CALENDSO_ENCRYPTION_KEY
docker compose -f infra/docker-compose.yml up -d
make smoke
```

## Kill-switch invariants (enforced by `smoke_test.sh`)

1. Acknowledgement filed in `infra/` and `policy/`.
2. `TENACIOUS_OUTBOUND_ENABLED` unset in `.env`.
3. `deliver()` on every channel routes to the staff sink when the switch is unset.

Flipping the kill switch is a three-step approval process per
[`__specs/16-data-handling-and-kill-switch.md`](../__specs/16-data-handling-and-kill-switch.md).
