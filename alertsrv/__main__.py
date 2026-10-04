from __future__ import annotations

import argparse
import logging
import threading
from http.server import ThreadingHTTPServer

from .api import create_server
from .engine import AlertEngine
from .models import SourceHealth
from .service import AlertService
from .storage import SQLiteAlertStore
from .adapters.mchs_rss import MchsRssAdapter

log = logging.getLogger("alertsrv")


def poll_once(service: AlertService, adapter: MchsRssAdapter) -> None:
    try:
        events = adapter.fetch()
        for event in events:
            service.accept(event)
        service.engine.set_source_health(adapter.source_id, SourceHealth.HEALTHY)
        service.expire()
        log.info("source=%s fetched=%d", adapter.source_id, len(events))
    except Exception:
        service.engine.set_source_health(adapter.source_id, SourceHealth.UNAVAILABLE)
        log.exception("source=%s poll failed", adapter.source_id)


def run_poller(service: AlertService, adapter: MchsRssAdapter, interval: float, stop: threading.Event) -> None:
    while not stop.wait(interval):
        poll_once(service, adapter)


def main() -> None:
    parser = argparse.ArgumentParser(description="AlertSRV local alert aggregation service")
    parser.add_argument("--db", default="alertsrv.sqlite3")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--interval", type=float, default=300.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = SQLiteAlertStore(args.db)
    service = AlertService(AlertEngine(store=store))
    adapter = MchsRssAdapter()
    stop = threading.Event()
    poll_once(service, adapter)
    poller = threading.Thread(target=run_poller, args=(service, adapter, args.interval, stop), daemon=True)
    poller.start()
    server: ThreadingHTTPServer = create_server(service, host=args.host, port=args.port)
    log.info("AlertSRV listening on %s:%d", args.host, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        poller.join(timeout=2)
        store.close()


if __name__ == "__main__":
    main()
