# Clean-Room Boundary

Vertica Power Packs may use public behavior, documentation, SQL interfaces, JDBC/ODBC behavior, object-store APIs, and benchmark observations.

Do:

- write original code;
- use standard libraries and clearly declared dependencies;
- use public Vertica interfaces such as SQL, `COPY`, JDBC/ODBC, `vsql`, Kafka integrations, and supported SDKs;
- document when a feature is a draft, workaround, or external wrapper;
- keep customer data and internal benchmark artifacts out of any public repository.

Do not:

- copy ClickHouse, StarRocks, Vertica, or other vendor source into this project without explicit license/legal review;
- paste benchmark data that could expose confidential information;
- embed credentials, tokens, hostnames, or private SSH material;
- represent wrapper functionality as a Vertica engine feature;
- publish without explicit approval.

Current private release-candidate license posture: MIT, pending final human/legal approval before any public visibility change.
