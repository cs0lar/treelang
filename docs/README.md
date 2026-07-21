# Treelang Documentation

- [Supported API reference](api.md) — generated from `treelang.__all__`.
- [Migration guide](migration-0.10.md) — compatibility guidance for the 0.10 series.
- Architecture decisions:
  - [ADR 0001: Version the serialized AST schema](adr/0001-schema-versioning.md)
  - [ADR 0002: Execute ASTs with isolated async contexts](adr/0002-execution-semantics.md)
  - [ADR 0003: Separate provider and model transports](adr/0003-provider-contracts.md)

Run `make docs` after changing the supported public API. `make check` and CI
verify that the committed reference is current.
