from __future__ import annotations

import argparse
import logging
import threading

from http.server import ThreadingHTTPServer

from .api import create_server
from .engine import AlertEngine

from .service import AlertService
from .storage import SQLiteAlertStore
from .poller import SourcePoller
from .regions import get_region, list_regions
from .regions.scheduler import RegionalScheduler


log = logging.getLogger("alertsrv")








def run_maintenance(service: AlertService, stop: threading.Event) -> None:
    while not stop.wait(60.0):
        service.expire()


def main() -> None:
    parser = argparse.ArgumentParser(description="AlertSRV local alert aggregation service")
    parser.add_argument("--db", default="alertsrv.sqlite3")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--regions", choices=("all", "ivanovo"), default="all")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store = SQLiteAlertStore(args.db)
    service = AlertService(AlertEngine(store=store))

    if args.regions == "ivanovo":
        enabled_regions = (get_region("37"),)
    else:
        enabled_regions = tuple(list_regions())

    scheduler = RegionalScheduler(SourcePoller(service.engine), enabled_regions)
    service.attach_scheduler(scheduler)
    stop = threading.Event()
    scheduler.start()
    maintenance = threading.Thread(
        target=run_maintenance,
        args=(service, stop),
        name="alertsrv-maintenance",
        daemon=True,
    )
    maintenance.start()

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
        scheduler.stop(timeout=2)
        maintenance.join(timeout=1)
        store.close()


if __name__ == "__main__":
    main()
