from __future__ import annotations

import argparse
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer

from .api import create_server
from .engine import AlertEngine
from .models import SourceHealth
from .service import AlertService
from .storage import SQLiteAlertStore
from .adapters.mchs_catalog import MchsRegionalCatalog
from .adapters.mchs_rss import GENERAL_RSS_TEMPLATE, MchsRssAdapter

log = logging.getLogger("alertsrv")


def poll_once(service: AlertService, adapters: list[MchsRssAdapter], workers: int = 8) -> None:
    def fetch(adapter: MchsRssAdapter) -> tuple[str, list, bool]:
        try:
            return adapter.source_id, adapter.fetch(), True
        except Exception:
            log.exception("source=%s poll failed", adapter.source_id)
            return adapter.source_id, [], False

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch, adapter) for adapter in adapters]
        for adapter, future in zip(adapters, futures):
            source_id, events, ok = future.result()
            if ok:
                for event in events:
                    service.accept(event)
                service.engine.set_source_health(source_id, SourceHealth.HEALTHY)
            else:
                service.engine.set_source_health(source_id, SourceHealth.UNAVAILABLE)
            log.info("source=%s fetched=%d", source_id, len(events))
    service.expire()


def run_poller(service: AlertService, adapters: list[MchsRssAdapter], interval: float, workers: int, stop: threading.Event) -> None:
    while not stop.wait(interval):
        poll_once(service, adapters, workers)


def main() -> None:
    parser = argparse.ArgumentParser(description="AlertSRV local alert aggregation service")
    parser.add_argument("--db", default="alertsrv.sqlite3")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--interval", type=float, default=900.0)
    parser.add_argument("--regions", choices=("all", "ivanovo"), default="all")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = SQLiteAlertStore(args.db)
    service = AlertService(AlertEngine(store=store))
    if args.regions == "ivanovo":
        adapters = [MchsRssAdapter()]
    else:
        regions = MchsRegionalCatalog().discover()
        adapters = [
            MchsRssAdapter(
                region.rss_url,
                source_id=f"mchs-{region.code}",
                general_fallback_url=GENERAL_RSS_TEMPLATE.format(code=region.code),
            )
            for region in regions
        ]
        log.info("discovered %d official regional MChS sites", len(adapters))
    stop = threading.Event()
    poll_once(service, adapters, args.workers)
    poller = threading.Thread(target=run_poller, args=(service, adapters, args.interval, args.workers, stop), daemon=True)
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
