#!/usr/bin/env python3
"""Minimal terminal UI for CR GUI server.

Usage:
  python3 tools/cr_terminal_ui.py --base-url http://127.0.0.1:5050
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def _http_get_json(url: str, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="replace")
    return json.loads(data)


def _http_post_form(url: str, form: dict[str, str], timeout: int = 20) -> str:
    payload = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_run_id(html: str) -> str:
    marker = "Run ID: <b>"
    idx = html.find(marker)
    if idx < 0:
        return ""
    start = idx + len(marker)
    end = html.find("</b>", start)
    if end < 0:
        return ""
    return html[start:end].strip()


def _poll_progress(base_url: str, run_id: str) -> int:
    since = 0
    printed = 0
    print(f"\nMonitoring run_id={run_id}\n")

    while True:
        url = f"{base_url}/api/run-progress/{run_id}?since={since}"
        try:
            data = _http_get_json(url)
        except Exception as exc:  # pylint: disable=broad-except
            print(f"[poll-error] {exc}")
            time.sleep(2)
            continue

        next_since = data.get("next_since", since)
        logs = data.get("logs") or []
        status = data.get("status", "unknown")
        live = data.get("live_results") or {}

        for line in logs:
            printed += 1
            print(f"[{printed:04d}] {line}")

        cr = len(live.get("cr") or [])
        monitor = len(live.get("monitor") or [])
        rerun = len(live.get("rerun") or [])
        print(f"status={status} | CR={cr} monitor={monitor} rerun={rerun}")

        since = next_since if isinstance(next_since, int) else since
        if status in {"done", "error"}:
            print("\nRun finished.")
            return 0 if status == "done" else 1

        time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Terminal UI for CR pipeline")
    parser.add_argument("--base-url", default="http://127.0.0.1:5050", help="CR GUI base URL")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    print("=== CR Terminal UI ===")
    print(f"Server: {base_url}")

    try:
        health = _http_get_json(f"{base_url}/health")
        print(f"Health: {health}")
    except urllib.error.URLError as exc:
        print(f"Cannot reach server: {exc}")
        return 2
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Health check failed: {exc}")
        return 2

    test_url = input("\nPaste test results URL: ").strip()
    if not test_url:
        print("No URL provided. Exiting.")
        return 1

    try:
        html = _http_post_form(f"{base_url}/api/run", {"test_url": test_url})
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Failed to start run: {exc}")
        return 3

    run_id = _extract_run_id(html)
    if not run_id:
        print("Could not parse run_id from response.")
        print(html[:400])
        return 4

    print(f"Run started: {run_id}")
    return _poll_progress(base_url, run_id)


if __name__ == "__main__":
    sys.exit(main())
