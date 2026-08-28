# Provenance

This repository is intended as an independently written interoperability project for Vertica.

## Allowed Inputs

- Public Vertica SQL behavior and public Vertica documentation.
- Public object-store interfaces such as S3-compatible URI conventions and MinIO client behavior.
- Public Python standard-library behavior.
- Optional third-party packages declared in `pyproject.toml`.
- Synthetic data generated specifically for this project.
- Original code written in this repository.

## Clean-Room Boundaries

The implementation must not include source code copied from Vertica, Rocket Software, ClickHouse, StarRocks, MinIO, cloud vendors, customer environments, private repositories, internal engineering documents, or support material.

Benchmark results, examples, and docs must not disclose customer data, private infrastructure, credentials, internal roadmaps, unreleased product information, or confidential sales material.

## Current Source Review

As of the release-gate review, implementation files under `src/`, tests, examples, and benchmark helper scripts appear to be original project code. No vendored source files or copied third-party source components are present.

## Publication Rule

No public GitHub push, public release, or package publication is authorized by this file. Human approval is required before publication.
