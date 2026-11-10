# ADR-0001: One monorepo and the overall stack

- Status: accepted
- Date: 2026-11-10
- Decided by: Daniel Owusu Mensah

## Context

The 2022 "Keep" project (Smart-Power-Monitoring-Inc) spread hardware, backend and app across three repositories with no shared contract. None of its code is reused; it stays archived as a reference.

## Decision

One repository, `smart-wall-socket`, holds every layer:

```
firmware/    ESP-IDF firmware: portable core (host-tested), app, tools
hardware/    KiCad 8 projects, BOM, test-jig designs           (EVT)
services/    Go: MQTT ingest, API, workers                     (later)
apps/        Next.js web dashboard, Expo mobile app            (later)
intelligence/ tariff engine, forecasts, anomaly models, assistant + evals (later)
docs/        protocol.md, ADRs, bench and test guides
```

The stack follows the revival roadmap: ESP-IDF and Matter on the device; Mosquitto with certificate auth, Go services and PostgreSQL with TimescaleDB in the cloud; Next.js with shadcn/ui and Expo for the apps.

Rules that apply across the repo:

- `docs/protocol.md` is the contract between device and cloud. Change it first.
- Safety logic lives on the device and never waits for the network.
- Commits are authored by Daniel only. No assistant co-author lines, no committed CLAUDE.md.
- No credentials in git (`.gitignore` blocks keys, certificates and factory images).

## Consequences

- One place for CI, one version history across firmware and cloud.
- The repo is private while the product name and certification route are open.
