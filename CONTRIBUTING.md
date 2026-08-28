# Contributing

Contributions should preserve the clean-room boundary.

## Requirements

- Use original code.
- Use only public interfaces and public documentation.
- Do not include customer data, private logs, internal URLs, credentials, screenshots with private information, or proprietary source code.
- Include focused tests for behavior changes.
- Keep benchmark claims bounded to the documented lab configuration.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Benchmark Claims

Separate measured results from observations, inferences, and hypotheses. Failed tests should be recorded as evidence rather than hidden.
