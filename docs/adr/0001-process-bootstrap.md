# ADR 0001: Process bootstrap

- Status: Accepted
- Date: 2026-10-07

## Context

Fieldshow is a new public repository. Later sessions need a design note, decisions with rejected alternatives, a TODO list, and open questions in the tree rather than only in chat.

## Decision

Keep `docs/DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/adr/`, `docs/TODO.md`, `docs/OPEN_QUESTIONS.md`, and `AGENTS.md`.

## Rejected alternatives

- Chat-only decisions. They disappear when the session ends.
- GitHub issues as the only log. The repo has to make sense when cloned offline.
- One giant `DECISIONS.md`. Individual files diff more cleanly and can be superseded one at a time.

## Consequences

New sessions read `AGENTS.md` first. A decision that changes a contract gets a new ADR.
