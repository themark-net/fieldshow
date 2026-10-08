# Autonomous decisions, 2026-10-07

The session used the 2026-10-06 morning orchestrator contract (atg-framework finish run): pick a reversible default, write it down, keep going.

| Choice | Alternatives | Why |
| --- | --- | --- |
| Repository name `fieldshow` | `halftime`, `marchkit` | Says music and drill together. The GitHub user is `themark-net` (a user, not an org). |
| MIT, schema export, no OpenMarch fork | AGPL fork, CalChart | See ADR 0002. |
| Demo tune is an original 8-beat fanfare | A public-domain hymn | Short enough to assert every pitch, and it is not someone else's chart. |
| Listen on `0.0.0.0:8876` on maximum | A reverse proxy and a new domain | Nothing else in the lab claimed 8876. No TLS until the host already has a pattern for it. |
| No login on the LAN page | Basic auth with a generated password | OQ-0005. The host is already inside the lab network. |
