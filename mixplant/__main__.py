"""Command line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .config import StationConfig
from .console.run import build_server
from .runtime import PlantRuntime


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""

    parser = argparse.ArgumentParser(prog="mixplant")
    parser.add_argument("--config", default=None, help="json config file")
    parser.add_argument("--host", default=None, help="bind address")
    parser.add_argument("--port", type=int, default=None, help="bind port")
    parser.add_argument("--data-dir", default=None, help="journal and snapshot directory")
    parser.add_argument("--web-dir", default=None, help="directory holding the console pages")
    parser.add_argument("--station", default=None, help="station name reported by the console")
    parser.add_argument(
        "--check",
        action="store_true",
        help="boot the runtime, print the restore report and the health payload, then exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the console or run a single boot check."""

    args = build_parser().parse_args(argv)
    config = StationConfig.load(args.config) if args.config else StationConfig()
    overrides: dict[str, object] = {}
    if args.host is not None:
        overrides["host"] = args.host
    if args.port is not None:
        overrides["port"] = args.port
    if args.data_dir is not None:
        overrides["data_dir"] = Path(args.data_dir)
    if args.web_dir is not None:
        overrides["web_dir"] = Path(args.web_dir)
    if args.station is not None:
        overrides["station"] = args.station
    runtime = PlantRuntime(config.with_overrides(**overrides))
    try:
        report = runtime.bootstrap()
        if args.check:
            print(
                json.dumps(
                    {"restore": report, "health": runtime.health()},
                    sort_keys=True,
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        server = build_server(runtime)
        server.bind()
        print(f"listening on {server.url}")
        print(f"health check {server.url}/api/health")
        print(
            "restart replay "
            f"{report['replayed_records']} records snapshot={report['used_snapshot_id']}"
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("stopping")
        finally:
            server.stop()
    finally:
        runtime.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
