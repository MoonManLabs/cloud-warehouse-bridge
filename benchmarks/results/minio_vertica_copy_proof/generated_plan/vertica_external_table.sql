-- Draft external-table path. Validate syntax and credentials in the target Vertica version.
CREATE SCHEMA IF NOT EXISTS vpp_e2e;

CREATE EXTERNAL TABLE vpp_e2e.events_ext (
  event_id VARCHAR(1024),
  event_id_num INT,
  tenant_id VARCHAR(1024),
  event_date DATE,
  amount_cents INT
)
AS COPY FROM 's3://vpowerpack-demo/vpowerpacks/e2e-copy-proof/*'
DELIMITER ',' ENCLOSED BY '"' SKIP 1;
