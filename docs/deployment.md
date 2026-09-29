# Hosting and database setup

## What is available now

The project runs locally with SQLite without a cloud account. Human sign-in and account-level plant ownership are implemented. Simulator readings are spooled locally during API outages, and local SQLite backup/restore scripts are included. A PostgreSQL adapter and schema are included, but no cloud database, domain, or public website has been created. No billing setting was enabled.

## Choosing a hosted setup

To make the dashboard available on the internet, choose a provider that can run the Python/FastAPI application and a PostgreSQL database. Static-only website hosting cannot run this backend. Provider free allowances, payment-card requirements, and pricing can change; review them before creating resources. A free tier is not a guarantee of zero charges. The application author has not selected a provider or approved enabling billing.

When you have selected a provider and want to proceed, the setup needs:

- A hosted PostgreSQL connection string, configured as `DATABASE_URL` in the hosting dashboard (never committed to GitHub).
- A private, random `DEVICE_API_KEY` configured in the host and matching the simulator or sensor configuration.
- A public HTTPS origin for the app; session cookies become Secure automatically when the request scheme is HTTPS.
- A deployment that serves both the frontend and API from the same origin, or a deliberately configured `ALLOWED_ORIGINS` value if separated.
- A persistent PostgreSQL database. The app creates its tables at startup; `cloud_schema.sql` is the matching schema reference.

For a local PostgreSQL trial, install `psycopg[binary]`, set `DATABASE_URL`, and start the app. SQLite stays the default when `DATABASE_URL` is blank. Do not paste credentials into chat or commit them. After selecting a provider, deployment-specific steps can be written for its dashboard and service settings.

## Keep billing off for the current project

If you want to guarantee that this project does not incur cloud charges, keep using the local SQLite instructions in the README and do not create hosted resources. The existing PostgreSQL code is preparation, not a live cloud connection or public deployment. Local backup scripts cover SQLite only; they are not managed-database backups.
