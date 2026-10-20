#!/usr/bin/env python3
"""Preload the configured maya-nvim Ollama models and keep them resident."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "http://127.0.0.1:11434"


def api(path, data=None, timeout=180):
    req = urllib.request.Request(
        ENDPOINT + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read(4096).decode(errors="replace")
        raise RuntimeError(f"Ollama {path}: HTTP {error.code}: {detail}") from error


def configured_models(state):
    """Return the models used by the saved Maya provider and mode."""
    try:
        data = json.loads(Path(state).read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("provider") != "ollama":
        return []
    mode = data.get("local_mode") or "completion-only"
    names = []
    if mode in ("dual", "completion-only"):
        names.append(data.get("model"))
    if mode in ("dual", "single"):
        names.append(data.get("next_edit_model"))
    return [name for name in dict.fromkeys(names) if name]


def main():
    global ENDPOINT

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "maya-nvim/ai.json",
    )
    parser.add_argument(
        "--endpoint", default=os.environ.get("OLLAMA_ENDPOINT", ENDPOINT)
    )
    parser.add_argument(
        "--keep-alive", default=os.environ.get("OLLAMA_KEEP_ALIVE", "-1")
    )
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument(
        "--wait",
        type=float,
        default=30,
        help="seconds to wait for the Ollama server to accept requests",
    )
    args = parser.parse_args()

    ENDPOINT = args.endpoint.rstrip("/")
    models = configured_models(args.state)
    if not models:
        print("No local Ollama models configured; nothing to warm.")
        return 0

    deadline = time.monotonic() + args.wait
    while True:
        try:
            api("/api/tags", timeout=2)
            break
        except (OSError, RuntimeError, ValueError) as error:
            if time.monotonic() >= deadline:
                print(f"Ollama is not available: {error}", file=sys.stderr)
                return 1
            time.sleep(1)

    keep_alive = args.keep_alive
    try:
        keep_alive = int(keep_alive)
    except ValueError:
        pass

    failed = False
    for model in models:
        payload = {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"num_ctx": 4096, "num_predict": 1},
        }
        started = time.monotonic()
        try:
            api("/api/generate", payload, timeout=args.timeout)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"Could not warm {model}: {error}", file=sys.stderr)
            failed = True
        else:
            elapsed = time.monotonic() - started
            print(f"Warmed {model} in {elapsed:.3f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
