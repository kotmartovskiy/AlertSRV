## Linux deployment

The repository contains `deploy/alertsrv.service` for a Linux/systemd deployment.

The intended layout is:

- application: `/opt/alertsrv`
- state/database: `/var/lib/alertsrv/alertsrv.sqlite3`
- listener: `127.0.0.1:8090`
- polling: all discovered regional MChS sites, 8 concurrent workers, 15-minute interval

Create a dedicated `alertsrv` system user, install the project under `/opt/alertsrv`, install the unit under `/etc/systemd/system/`, then enable/start the service. The unit deliberately keeps the API on localhost until an authentication/access-control layer is implemented.

Do not expose port 8090 directly to the Internet.
