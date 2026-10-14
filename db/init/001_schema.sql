CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE TABLE IF NOT EXISTS customers (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  region TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(id),
  status TEXT NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounts (
  id BIGSERIAL PRIMARY KEY,
  owner TEXT NOT NULL,
  balance NUMERIC(12,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS demo_scenario_state (
  scenario TEXT PRIMARY KEY,
  active BOOLEAN NOT NULL DEFAULT FALSE,
  metric_value DOUBLE PRECISION NOT NULL DEFAULT 0,
  detail TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO demo_scenario_state(scenario, active, metric_value, detail)
VALUES
  ('slow_query', FALSE, 0, 'inactive'),
  ('lock_contention', FALSE, 0, 'inactive'),
  ('workload_contention', FALSE, 0, 'inactive'),
  ('table_bloat', FALSE, 0, 'inactive'),
  ('execution_error', FALSE, 0, 'inactive')
ON CONFLICT (scenario) DO NOTHING;

INSERT INTO customers(name, region)
SELECT 'Customer ' || g, CASE WHEN g % 3 = 0 THEN 'north' WHEN g % 3 = 1 THEN 'central' ELSE 'south' END
FROM generate_series(1, 2000) g
ON CONFLICT DO NOTHING;

INSERT INTO orders(customer_id, status, amount, created_at)
SELECT (random() * 1999 + 1)::bigint,
       (ARRAY['new','paid','shipped','cancelled'])[floor(random()*4 + 1)],
       round((random() * 1000)::numeric, 2),
       now() - ((random() * 365)::int || ' days')::interval
FROM generate_series(1, 100000)
ON CONFLICT DO NOTHING;

INSERT INTO accounts(owner, balance)
SELECT 'Owner ' || g, 1000 FROM generate_series(1, 20) g
ON CONFLICT DO NOTHING;

ANALYZE;
