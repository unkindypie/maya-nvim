"""Summarize candidate JSONL; warm repetitions only, failures remain in outcomes."""

import argparse
import collections
import json
import math
import statistics
from pathlib import Path


def percentile(values, quantile=0.95):
    return (
        round(sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)], 1)
        if values
        else None
    )


def response_text(request):
    parts = []
    for chunk in request.get("chunks", []):
        for line in chunk.splitlines():
            line = line.removeprefix("data: ")
            if not line or line == "[DONE]":
                continue
            try:
                body = json.loads(line)
            except ValueError:
                continue
            parts.append(body.get("response", ""))
            parts.extend(choice.get("text", "") for choice in body.get("choices", []))
    return "".join(parts)


def no_preview_category(row):
    if row["visible"]:
        return None
    if not row["requests"]:
        return "no_request"
    request = row["requests"][-1]
    text = response_text(request)
    if not text:
        return "empty_response"
    prompt = request["body"]["prompt"]
    if "<|file_sep|>current/" in prompt and "<|file_sep|>updated/" in prompt:
        current = (
            prompt.rsplit("<|file_sep|>current/", 1)[1]
            .partition("\n")[2]
            .split("<|file_sep|>updated/", 1)[0]
        )
        prefill = prompt.rsplit("<|file_sep|>updated/", 1)[1].partition("\n")[2]
        if (prefill + text).strip() == current.replace("<|cursor|>", "").strip():
            return "model_noop"
    return "nonempty_unshown_response"


def transport_disconnect(request):
    # The initial capture stored client resets in the generic error field.
    # Preserve that raw evidence and show it separately from inference failures.
    message = str(request.get("error", ""))
    return bool(request.get("client_disconnect")) or (
        request["body"].get("stream")
        and ("Connection reset by peer" in message or "Broken pipe" in message)
    )


def summarize(rows):
    output = []
    groups = collections.defaultdict(list)
    for row in rows:
        if "candidate" in row and row["sample"] > 0:
            groups[(row["candidate"], row["kind"], row["split"])].append(row)
            groups[(row["candidate"], row["kind"], "all")].append(row)
    for (candidate, kind, split), group in sorted(groups.items()):
        previews = [r["preview_ms"] for r in group if r["preview_ms"] is not None]
        safe = [r["safe_preview_ms"] for r in group if r["safe_preview_ms"] is not None]
        requests = [q for r in group for q in r["requests"]]
        output.append(
            {
                "candidate": candidate,
                "kind": kind,
                "split": split,
                "trials": len(group),
                "fixtures": len({r["case"] for r in group}),
                "correct": sum(r["correct"] for r in group),
                "visible": sum(r["visible"] for r in group),
                "unchanged": sum(r["unchanged"] for r in group),
                "visible_unchanged": sum(
                    r["visible"] and r["unchanged"] for r in group
                ),
                "no_preview_categories": dict(
                    collections.Counter(
                        no_preview_category(r) for r in group if not r["visible"]
                    )
                ),
                "incorrect_changes": sum(
                    not r["correct"] and not r["unchanged"] for r in group
                ),
                "timed_out": sum(r["timed_out"] for r in group),
                "overlaps": sum(r["overlap"] for r in group),
                "requests": len(requests),
                "post_accept_requests": sum(r["post_accept_requests"] for r in group),
                "request_errors": sum(
                    bool(q.get("error")) and not transport_disconnect(q)
                    for q in requests
                ),
                "transport_disconnects": sum(
                    bool(transport_disconnect(q)) for q in requests
                ),
                "preview_p50_ms": round(statistics.median(previews), 1)
                if previews
                else None,
                "preview_p95_ms": percentile(previews),
                "safe_preview_p95_ms": percentile(safe),
                "all_outcomes_p95_ms": percentile([r["elapsed_ms"] for r in group]),
                "request_p95_ms": percentile(
                    [(q["finished"] - q["started"]) * 1000 for q in requests]
                ),
                "prompt_p95_chars": percentile(
                    [len(q["body"]["prompt"]) for q in requests]
                ),
            }
        )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    rows = [
        json.loads(line)
        for path in args.files
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
