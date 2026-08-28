# Security Policy

## Reporting Security Issues

Do not disclose suspected vulnerabilities publicly until they have been reviewed. Open a private advisory or contact the repository maintainer through the configured private channel once the project has an approved public home.

## Secrets

This project must not contain passwords, API keys, SSH keys, cloud credentials, Vertica licenses, cookies, customer data, or private infrastructure details.

Benchmark scripts require credentials through environment variables and should be run only against disposable test buckets or explicitly approved lab environments.

## Vertica Safety

Generated SQL is a draft starting point. Review it before running it against any database.

The planner generates schema/table creation, external table, and `COPY` examples. It does not generate `DROP`, privilege changes, user changes, license workarounds, authentication bypasses, or destructive cleanup commands.

Use read-only or disposable environments for first tests.
