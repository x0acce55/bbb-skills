#!/usr/bin/env python3
"""
claude-cost — Claude Code status line showing live session spend, split by
billing path (Claude Platform on AWS vs. Max subscription).

Reads the statusLine JSON contract on stdin, incrementally parses the session
transcript, prices token usage client-side, prints one line to stdout.

Billing-path detection
  * env ANTHROPIC_BASE_URL contains "aws-external-anthropic"  -> this whole
    session is billed to Claude Platform on AWS. The claude-paid / fable shims
    set it; a plain `claude` session does not.
  * per message, usage.inference_geo == "global" -> CPA-billed, "not_available"
    -> Max subscription. This is the only field in the transcript that
    separates the two paths (model id, req_/msg_ prefixes, service_tier and
    version are identical on both).

Why parse at all when the harness hands us cost.total_cost_usd: that figure is
a single list-price number with no billing-path split, which is the one thing
this status line exists to show. We use it only as a fallback.

Accuracy: CPA has no programmatic usage API (Anthropic's Admin usage_report /
cost_report endpoints are unavailable for it), so local pricing is the only
real-time source. Reconcile against AWS Cost Explorer -> service
"Claude Platform", usage type MP:ccu-Units, UTC daily buckets.

Observed 2026-08-30: this reads ~15% under the AWS-metered figure, and the gap
tracks the 5m->1h cache-write premium — writes appear to bill at the 1h rate
even though usage.cache_creation reports them under ephemeral_5m_input_tokens.
Set CLAUDE_COST_WRITES_1H=1 to price all cache writes at 1h, or
CLAUDE_COST_CALIBRATION=1.15 for a flat multiplier.
"""
import json
import os
import sys
import time

HOME = os.path.expanduser("~")
BASE = os.path.join(HOME, ".claude", "statusline")
CACHE_DIR = os.path.join(BASE, "cache")
DAILY_DIR = os.path.join(BASE, "daily")
SEEN_CAP = 40000
DAILY_KEEP_DAYS = 14

# $ per 1M tokens: (input, output). Cache read = 0.1x input,
# cache write = 1.25x input (5m TTL) or 2.0x input (1h TTL).
RATES = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}
# Fast mode (research preview) is premium-priced on these models.
FAST_RATES = {"claude-opus-5": (10.0, 50.0), "claude-opus-4-8": (10.0, 50.0)}

CAL = float(os.environ.get("CLAUDE_COST_CALIBRATION", "1") or 1)
WRITES_1H = os.environ.get("CLAUDE_COST_WRITES_1H", "") not in ("", "0")

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
RED, YEL, GRN, CYA, MAG = "\033[31m", "\033[33m", "\033[32m", "\033[36m", "\033[35m"


def rate_for(model, usage):
    if usage.get("speed") == "fast" and model in FAST_RATES:
        return FAST_RATES[model]
    return RATES.get(model)


def price(model, usage):
    """Return (usd, known). known=False when the model has no rate table entry."""
    r = rate_for(model, usage)
    if not r:
        return 0.0, False
    inp, out = r
    cc = usage.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens", 0) or 0
    w5m = cc.get("ephemeral_5m_input_tokens", 0) or 0
    if not (w1h or w5m):  # older records only carry the flat total
        w5m = usage.get("cache_creation_input_tokens", 0) or 0
    if WRITES_1H:
        w1h, w5m = w1h + w5m, 0
    usd = (
        (usage.get("input_tokens", 0) or 0) * inp
        + (usage.get("cache_read_input_tokens", 0) or 0) * inp * 0.10
        + w5m * inp * 1.25
        + w1h * inp * 2.00
        + (usage.get("output_tokens", 0) or 0) * out
    ) / 1_000_000
    return usd * CAL, True


def transcript_files(transcript_path):
    """Main transcript plus any subagent transcripts that hang off it."""
    files = []
    if transcript_path and os.path.isfile(transcript_path):
        files.append(transcript_path)
    subdir = os.path.join(transcript_path[:-6] if transcript_path.endswith(".jsonl")
                          else transcript_path, "subagents")
    try:
        for name in sorted(os.listdir(subdir)):
            if name.endswith(".jsonl"):
                files.append(os.path.join(subdir, name))
    except OSError:
        pass
    return files


def scan(state, transcript_path):
    """Incrementally fold new transcript records into state. Mutates + returns it."""
    seen = state["seen"]
    offsets = state["offsets"]
    for path in transcript_files(transcript_path):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        start = offsets.get(path, 0)
        if start > size:  # file rewritten/truncated -> re-read from scratch
            start = 0
        if start == size:
            continue
        # Read the delta as bytes and advance the offset arithmetically.
        # (Do NOT use `for line in fh` + fh.tell(): tell() during text-file
        # iteration raises OSError "telling position disabled by next() call".)
        try:
            with open(path, "rb") as fh:
                fh.seek(start)
                chunk = fh.read(size - start)
        except OSError:
            continue
        nl = chunk.rfind(b"\n")  # ignore any partial trailing write
        if nl < 0:
            continue
        offsets[path] = start + nl + 1
        for raw in chunk[:nl].split(b"\n"):
            if b'"assistant"' not in raw:  # cheap prefilter before json.loads
                continue
            try:
                rec = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage, mid = msg.get("usage"), msg.get("id")
            # Claude Code repeats records for one message id within a
            # transcript, so dedupe on it or the total roughly doubles.
            if not usage or not mid or mid in seen:
                continue
            seen[mid] = 1
            model = msg.get("model") or ""
            usd, known = price(model, usage)
            bucket = "paid" if usage.get("inference_geo") == "global" else "sub"
            state[bucket] += usd
            day = (rec.get("timestamp") or "")[:10]
            if day:
                bd = state["by_day"].setdefault(day, {"paid": 0.0, "sub": 0.0})
                bd[bucket] = bd.get(bucket, 0.0) + usd
            state["calls"] += 1
            if model and model != "<synthetic>":
                state["last_model"] = model
                if not known:
                    state["unpriced"][model] = 1
    if len(seen) > SEEN_CAP:  # unbounded-growth guard on very long sessions
        state["seen"] = dict(list(seen.items())[-SEEN_CAP // 2:])
    return state


def load_state(session_id):
    path = os.path.join(CACHE_DIR, session_id + ".json")
    try:
        with open(path) as fh:
            st = json.load(fh)
        for k, d in (("seen", {}), ("offsets", {}), ("unpriced", {}), ("by_day", {})):
            if not isinstance(st.get(k), dict):
                st[k] = d
        for k in ("paid", "sub"):
            st[k] = float(st.get(k) or 0)
        st["calls"] = int(st.get("calls") or 0)
        return st
    except Exception:
        return {"seen": {}, "offsets": {}, "unpriced": {}, "by_day": {},
                "paid": 0.0, "sub": 0.0, "calls": 0, "last_model": ""}


def atomic_write(path, obj):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(tmp, "w") as fh:
            json.dump(obj, fh)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def daily_paid_total(session_id, state):
    """Sum today's CPA spend across all sessions. UTC to match Cost Explorer.

    Only this session's spend *dated today* is contributed, so a session
    resumed across midnight UTC does not dump its whole history onto today.
    """
    day = time.strftime("%Y-%m-%d", time.gmtime())
    session_paid = (state.get("by_day", {}).get(day, {}) or {}).get("paid", 0.0)
    path = os.path.join(DAILY_DIR, day + ".json")
    try:
        with open(path) as fh:
            rollup = json.load(fh)
        if not isinstance(rollup, dict):
            rollup = {}
    except Exception:
        rollup = {}
    if abs(rollup.get(session_id, 0) - session_paid) > 0.0005:
        rollup[session_id] = round(session_paid, 6)
        atomic_write(path, rollup)
    prune_daily(day)
    return sum(v for v in rollup.values() if isinstance(v, (int, float)))


def prune_daily(today):
    cutoff = time.time() - DAILY_KEEP_DAYS * 86400
    try:
        for name in os.listdir(DAILY_DIR):
            if name.endswith(".json") and name[:-5] != today:
                p = os.path.join(DAILY_DIR, name)
                if os.path.getmtime(p) < cutoff:
                    os.unlink(p)
    except OSError:
        pass


def fit(segments, width):
    """Join segments with a separator, dropping from the right until it fits."""
    sep = DIM + "  ·  " + RESET
    while segments:
        line = sep.join(s[0] for s in segments)
        plain = sum(len(s[1]) for s in segments) + 5 * (len(segments) - 1)
        if plain <= width or len(segments) == 1:
            return line
        segments = segments[:-1]
    return ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    session_id = data.get("session_id") or "unknown"
    transcript = data.get("transcript_path") or ""
    model_name = ((data.get("model") or {}).get("display_name")
                  or (data.get("model") or {}).get("id") or "")
    ctx = data.get("context_window") or {}
    used_pct = ctx.get("used_percentage")
    cache = data.get("prompt_cache") or {}

    on_cpa = "aws-external-anthropic" in os.environ.get("ANTHROPIC_BASE_URL", "")

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(DAILY_DIR, exist_ok=True)

    state = load_state(session_id)
    try:
        state = scan(state, transcript)
        atomic_write(os.path.join(CACHE_DIR, session_id + ".json"), state)
        parsed = True
    except Exception:
        parsed = False

    paid, sub = state["paid"], state["sub"]
    if not parsed and not (paid or sub):  # fall back to the harness estimate
        fallback = (data.get("cost") or {}).get("total_cost_usd") or 0
        if on_cpa:
            paid = fallback
        else:
            sub = fallback

    today_paid = daily_paid_total(session_id, state)

    segs = []
    if on_cpa or paid > 0:
        segs.append((BOLD + RED + "PAID $%.2f" % paid + RESET, "PAID $%.2f" % paid))
    else:
        segs.append((DIM + "sub ~$%.2f" % sub + RESET, "sub ~$%.2f" % sub))
    if paid > 0 and sub > 0:  # mixed session: both paths used
        segs.append((DIM + "+sub ~$%.2f" % sub + RESET, "+sub ~$%.2f" % sub))
    if today_paid > 0.005:
        t = "today $%.2f" % today_paid
        segs.append((YEL + t + RESET, t))
    if model_name:
        segs.append((CYA + model_name + RESET, model_name))
    if isinstance(used_pct, (int, float)):
        col = GRN if used_pct < 50 else (YEL if used_pct < 80 else RED)
        t = "ctx %d%%" % used_pct
        segs.append((col + t + RESET, t))
    if cache.get("caching_observed") and isinstance(cache.get("hit_ratio"), (int, float)):
        t = "cache %d%%" % round(cache["hit_ratio"] * 100)
        segs.append((DIM + t + RESET, t))
    if state.get("unpriced"):
        t = "?%d unpriced" % len(state["unpriced"])
        segs.append((MAG + t + RESET, t))

    try:
        width = int(os.environ.get("COLUMNS") or 0) or 120
    except ValueError:
        width = 120
    sys.stdout.write(fit(segs, max(width - 2, 20)) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.stdout.write("\n")  # never break the UI
