-- Draft bulk-load path. Prefer this for hot partitions and repeated analytics.
COPY vpp_e2e.events
FROM 's3://vpowerpack-demo/vpowerpacks/e2e-copy-proof/*'
DELIMITER ',' ENCLOSED BY '"' SKIP 1
REJECTED DATA AS TABLE vpp_e2e.events_rejects;
