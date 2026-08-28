# License Recommendation

Recommended and currently applied candidate: MIT, subject to final human/legal approval before public release.

## Why MIT Fits This Release Candidate

- The current core package has no required runtime dependencies.
- The project is a small interoperability helper and demonstration, not a database engine.
- A permissive license lowers friction for Vertica users, partners, and engineering teams to inspect, adapt, or replace the wrapper.
- It avoids copyleft obligations that could complicate review by internal product teams or customers.

## Dependency Notes

- Python standard library: used by the core package.
- `boto3` optional extra: Apache-2.0, used only if future S3 integration is enabled.
- `pyarrow` optional extra: Apache-2.0, used only for local Parquet metadata inspection.
- `pytest` optional development extra: MIT, used only for test/development workflows.
- MinIO client container image: used by an optional benchmark script, not vendored or redistributed.

## Approval Boundary

A standard MIT `LICENSE` file is present in this private release candidate using the pseudonymous project identity `Moon Man Labs`. Do not make the repository public under this license until the human publication checkpoint approves public visibility.
