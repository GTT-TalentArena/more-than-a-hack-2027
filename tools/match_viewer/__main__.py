"""Start the viewer; the browser and all data stay on loopback."""

import argparse
import threading

import games
from .server import Session, make_server


def main():
    parser = argparse.ArgumentParser(description="Local 2D tactical tracking viewer (read-only).")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--synthetic", action="store_true", help="Run the invented demo; no match files are opened.")
    mode.add_argument("--data-dir", help="Authorised local bundle root containing tactical/.")
    parser.add_argument("--predictions", help="Optional local frame,label CSV.")
    parser.add_argument("--no-predictions", action="store_true", help="Hide the synthetic labels (test the no-CSV state).")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    if args.predictions and args.no_predictions:
        parser.error("Choose --predictions or --no-predictions, not both.")
    paths = games.asset_paths(data_dir=args.data_dir) if args.data_dir else {}
    session = Session()
    worker = threading.Thread(target=session.load, kwargs={
        "meta": paths.get("atd_meta"), "raw": paths.get("atd_raw"),
        "predictions": args.predictions, "no_predictions": args.no_predictions}, daemon=True)
    try:
        server = make_server(session, args.port)
    except OSError:
        parser.exit(2, "Cannot bind the loopback port. Try a different --port.\n")
    worker.start()
    print("Open http://127.0.0.1:{} — press Ctrl+C to stop.".format(args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
