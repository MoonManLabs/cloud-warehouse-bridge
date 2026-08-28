-- Draft COPY batch plan. Validate credentials, parser options, and resource pools before execution.

-- Batches: 1

-- Batch 1: 3 file(s)
COPY vpp_e2e.events
FROM
  's3://vpowerpack-demo/vpowerpacks/e2e-copy-proof/invalid.csv',
  's3://vpowerpack-demo/vpowerpacks/e2e-copy-proof/medium.csv',
  's3://vpowerpack-demo/vpowerpacks/e2e-copy-proof/small.csv'
DELIMITER ',' ENCLOSED BY '"' SKIP 1
REJECTED DATA AS TABLE vpp_e2e.events_rejects;
