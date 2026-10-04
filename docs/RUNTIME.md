# Runtime service

AlertSRV can now run as a local service with:

```text
python -m alertsrv --db alertsrv.sqlite3 --port 8090 --interval 900 --regions all --workers 8
```

Startup performs one synchronous source poll before the HTTP server is exposed. Subsequent polls run in a background thread. Source failures set source health to `UNAVAILABLE`; they do not resolve existing alerts.

The HTTP listener remains localhost-only by default.

SQLite persistence is thread-safe for the service runtime: the connection is explicitly shared between the HTTP and polling threads and serialized with a store-level reentrant lock.

The default runtime discovers the official regional MChS sites and polls all discovered regions. `--regions ivanovo` remains available as a low-load development mode. The default poll interval is 15 minutes and up to 8 regional fetches run concurrently.
