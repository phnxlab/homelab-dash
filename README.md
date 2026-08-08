# HomeLab Dashboard

A Django-based starting point for a LAN-only homelab network dashboard.

## Current slice

- Local username/password authentication.
- Separate admin portal at `/admin-portal/` with server-side staff authorization.
- Django admin at `/admin/` for managing the initial data models.
- SQLite persistence with migrations.
- Models for monitored endpoints, health-check results, discovered devices, scan targets, and incidents.
- Home Assistant device-registry sync for devices with a valid IP address.
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

## Home Assistant discovery

1. In Home Assistant, open your profile menu, create a long-lived access token, and copy it immediately. Home Assistant only displays the token once.
2. Add the Home Assistant URL and token to the deployment `.env` file:

```env
HOME_ASSISTANT_URL=http://192.168.88.20:8123
HOME_ASSISTANT_TOKEN=your-long-lived-access-token
HOME_ASSISTANT_TIMEOUT_SECONDS=10
```

When Home Assistant is behind Nginx Proxy Manager, use its HTTPS hostname instead of the internal IP and port, for example `HOME_ASSISTANT_URL=https://homeassistant.example.local`. In the corresponding Nginx Proxy Manager Proxy Host, enable **Websockets Support**. Device and entity registry data is fetched through Home Assistant's WebSocket API at `/api/websocket`; the normal REST API is used only for current entity states.

3. Restart the container so it receives the updated environment:

```powershell
docker compose up -d
```

4. Sign in with a staff account and open `/admin-portal/`.
5. Select **Sync devices**, then inspect the imported records under Django admin at `/admin/`.

The sync uses Home Assistant's device registry and state APIs. It imports the device name, IP address, MAC address, manufacturer, model, area, and Home Assistant device ID. Devices without a valid IP address are reported as skipped because Home Assistant does not expose network addresses for every integration. The token is sent only as an API bearer header and is not stored in the database.

If the sync reports an API failure, check that the URL is reachable from the Docker container, the token is valid, and the Home Assistant API is available at `/api/`. Do not put the token in a committed file or share it in logs.

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
