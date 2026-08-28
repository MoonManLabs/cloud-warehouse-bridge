CREATE SCHEMA IF NOT EXISTS vpp_e2e;

CREATE TABLE IF NOT EXISTS vpp_e2e.events (
  event_id VARCHAR(1024),
  event_id_num INT,
  tenant_id VARCHAR(1024),
  event_date DATE,
  amount_cents INT
);
