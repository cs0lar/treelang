# ADR 0001: Version the serialized AST schema

- Status: Accepted
- Date: 2026-07-21

## Context

Treelang programs are serialized, cached, evaluated later, and may cross process
or package-version boundaries. An unversioned schema would make compatibility
ambiguous and allow model or library changes to silently reinterpret stored trees.

## Decision

The supported schema lives in `treelang.trees.schemas.v1` and serializes
`schema_version` as the literal `"1.0"` on program nodes. `CURRENT_SCHEMA_VERSION`
identifies the version emitted by current helpers. Root-level imports remain the
stable public surface; internal module locations are not a compatibility promise.

Changes within version 1 must preserve the meaning of already-valid serialized
programs. A change that removes a node or field, changes evaluation meaning, or
otherwise cannot preserve version 1 data requires a new schema module and an
explicit migration path. The generated JSON Schema and examples must come from
the same Pydantic models used for runtime validation.

## Consequences

- Stored version 1 programs remain interpretable across compatible releases.
- Schema and runtime validation cannot drift independently.
- Breaking schema work requires parallel version support or documented migration,
  rather than modifying `v1.py` in place.
