# Acme Retail SAM — Grading Framework

Test harness for verifying OrderFulfillmentAgent (and future agents) behavior
against live broker and database.

## Directory structure

```
grading/
├── smoke_test.py               # Run first — confirms broker + DB are reachable
├── framework/
│   ├── broker.py               # BrokerClient: publish / wait_for_message
│   ├── database.py             # PostgreSQL query + assertion helpers
│   ├── seeder.py               # full_reset() — restore DB to seed state
│   └── result.py               # ResultCollector + HMAC-signed payload
└── tests/
    └── test_order_fulfillment.py   # Course 300 OrderFulfillmentAgent tests
```

## Prerequisites

- Docker containers running: `docker-compose up -d`
- SAM running: `cd 300/sam && sam run`
- Database seeded: `python acme-retail/scripts/seed_orders_db.py`

## Run the smoke test first

```bash
cd /workspaces/Solace_Academy_SAM_Dev_Demo/acme-retail/grading
python smoke_test.py
```

Expected output:
```
✅  Broker: connected
✅  Broker: publish/subscribe round-trip OK
✅  Database: connected
✅  Database: orders table has 10 rows
...
🟢  All systems ready. Safe to run tests.
```

## Run the Order Fulfillment tests

```bash
python -m tests.test_order_fulfillment
```

Or with your email (for grading submission):
```bash
python -m tests.test_order_fulfillment your@email.com
```

## Environment variables

| Variable                     | Default                                  | Description                  |
|------------------------------|------------------------------------------|------------------------------|
| `SOLACE_BROKER_URL`          | `tcp://localhost:55555`                  | Broker SMF TCP URL           |
| `SOLACE_BROKER_VPN`          | `default`                                | Message VPN name             |
| `SOLACE_BROKER_USERNAME`     | `default`                                | Broker username              |
| `SOLACE_BROKER_PASSWORD`     | `default`                                | Broker password              |
| `ORDERS_DB_CONNECTION_STRING`| `postgresql://acme:acme@localhost:5432/orders` | PostgreSQL DSN         |
| `ACME_SEEDER_PATH`           | `.../scripts/seed_orders_db.py`          | Path to seeder script        |
| `GRADING_HMAC_SECRET`        | `dev-secret`                             | HMAC key for result signing  |

## What the tests verify

| Test | Trigger | Expected outcome |
|------|---------|-----------------|
| t1 | `acme/orders/created` with in-stock SKU | Message on `fulfillment-result/validated` |
| t2 | `acme/orders/created` with OOS SKU | Message on `fulfillment-result/blocked` |
| t3 | `acme/inventory/updated` (OOS SKU restocked) | Blocked order re-validated |
| t4 | `acme/logistics/shipment-delayed` | Message on `acme/incidents/created` |
