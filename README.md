# HomeLab Dashboard

A Django-based starting point for a LAN-only homelab network dashboard.

## Current slice

- Local username/password authentication.
- Separate admin portal at `/admin-portal/` with server-side staff authorization.
- Django admin at `/admin/` for managing the initial data models.
- SQLite persistence with migrations.
- Models for monitored endpoints, health-check results, discovered devices, scan targets, and incidents.
- Secure defaults for sessions, CSRF, clickjacking, and content sniffing.

Network discovery and background monitoring are the next implementation slice. They should run as bounded background jobs and never block a dashboard request.

## Local development

From this directory, use the workspace virtual environment or another Python 3.13+ environment:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`, then sign in with the local account. Staff users can open the admin portal and Django admin.

Run validation with:

```powershell
python manage.py check
python manage.py test dashboard
```

## Docker deployment

1. Copy `.env.example` to `.env`.
2. Set a long random `DJANGO_SECRET_KEY` and the LAN hostnames/IPs in `DJANGO_ALLOWED_HOSTS`.
3. Start the service:

```powershell
docker compose up -d --build
```

4. Create the first administrator:

```powershell
docker compose exec web python manage.py createsuperuser
```

SQLite is stored in the `homelab-data` volume. Back up that volume before upgrades. Keep the application LAN-only or place it behind an internal HTTPS reverse proxy; internet exposure is not part of this first slice.

## Planned integrations

- Home Assistant inventory provider.
- Explicitly configured ARP/local-subnet discovery with documented container network capabilities.
- URL polling with timeout, redirect, retry, latency, incident, and recovery handling.
- Email and Discord/Teams-compatible webhook notifications.
- Future OIDC authentication and PostgreSQL persistence.
