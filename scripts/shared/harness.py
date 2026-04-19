#!/usr/bin/env python3
"""Game action harness — trigger pseudo-human input + observe hook effects.

See skills/game-action-harness/SKILL.md for the contract.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "harness.py requires PyYAML. Install with: pip install pyyaml\n"
    )
    raise

# Make sibling backends package importable when invoked directly.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from harness_backends import adb_input, sendinput, log_tail, memory_reader, template_match  # noqa: E402


CATALOG_PATH = Path(".harness/actions.yaml")
SYMBOLS_PATH = Path(".harness/symbols.yaml")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _load_catalog(repo: Path) -> dict[str, Any]:
    path = repo / CATALOG_PATH
    if not path.is_file():
        raise FileNotFoundError(
            f"No action catalog at {path}. Populate .harness/actions.yaml first "
            f"(see skills/game-action-harness/templates/actions.yaml.example)."
        )
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if "target" not in data or "actions" not in data:
        raise ValueError(f"{path}: catalog must define `target` and `actions`")
    return data


def _load_symbols(repo: Path) -> dict[str, Any] | None:
    path = repo / SYMBOLS_PATH
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _dispatch_invoke(target: dict, spec: dict) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Run one invoke step. Returns (result, outputs).

    `outputs` is a dict of variables this step produced (e.g. locate → {"pos": [x, y]}),
    to be merged into the scope for subsequent chained steps. None for pure-action steps.
    """
    kind = spec.get("kind")
    start = time.monotonic()
    outputs: dict[str, Any] | None = None
    try:
        if kind in {"adb_tap", "adb_swipe", "adb_keyevent", "adb_text"}:
            adb_input.invoke(target, spec)
        elif kind in {"sendinput_click", "sendinput_key", "postmessage_click"}:
            sendinput.invoke(target, spec)
        elif kind == "locate":
            outputs = template_match.locate(target, spec)
        elif kind == "wait":
            duration_ms = int(spec.get("duration_ms", 0))
            if duration_ms < 0:
                raise ValueError("wait.duration_ms must be >= 0")
            time.sleep(duration_ms / 1000.0)
        else:
            raise ValueError(f"Unknown invoke kind: {kind!r}")
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return {"bridge": kind, "elapsed_ms": elapsed_ms, "error": None}, outputs
    except adb_input.BridgeDownError as exc:
        return {"bridge": kind, "elapsed_ms": 0, "error": f"bridge_down: {exc}"}, None
    except sendinput.BridgeDownError as exc:
        return {"bridge": kind, "elapsed_ms": 0, "error": f"bridge_down: {exc}"}, None
    except template_match.BridgeDownError as exc:
        return {"bridge": kind, "elapsed_ms": 0, "error": f"bridge_down: {exc}"}, None
    except template_match.LocateFailure as exc:
        return {"bridge": kind, "elapsed_ms": int((time.monotonic() - start) * 1000),
                "error": f"locate_failed: {exc}"}, None
    except Exception as exc:
        return {"bridge": kind, "elapsed_ms": 0, "error": f"{type(exc).__name__}: {exc}"}, None


def _dispatch_observe(target: dict, spec: dict | None, symbols: dict | None, started_mono: float) -> dict[str, Any] | None:
    if spec is None:
        return None
    kind = spec.get("kind")
    try:
        if kind in {"hook_log", "logcat", "packet"}:
            return log_tail.observe(target, spec, started_mono)
        if kind == "memory":
            return memory_reader.observe(target, spec, symbols)
        raise ValueError(f"Unknown observe kind: {kind!r}")
    except log_tail.BridgeDownError as exc:
        return {"bridge": kind, "matched": False, "elapsed_ms": 0, "evidence": None, "error": f"bridge_down: {exc}"}
    except memory_reader.BridgeDownError as exc:
        return {"bridge": kind, "matched": False, "elapsed_ms": 0, "evidence": None, "error": f"bridge_down: {exc}"}
    except Exception as exc:
        return {"bridge": kind, "matched": False, "elapsed_ms": 0, "evidence": None, "error": f"{type(exc).__name__}: {exc}"}


def _substitute(spec: dict, scope: dict[str, Any]) -> dict:
    """Shallow-substitute $var references in a spec from the current variable scope.

    Scope is seeded by CLI --arg pairs and grows as chained invoke steps emit outputs
    (e.g. a `locate` step writes {"pos": [x, y]} which a later `click` can reference
    as `coords: $pos`).
    """
    if not scope:
        return spec
    result: dict[str, Any] = {}
    for key, val in spec.items():
        if isinstance(val, str) and val.startswith("$") and val[1:] in scope:
            result[key] = scope[val[1:]]
        elif isinstance(val, list):
            result[key] = [
                scope[item[1:]] if isinstance(item, str) and item.startswith("$") and item[1:] in scope else item
                for item in val
            ]
        else:
            result[key] = val
    return result


def cmd_list(repo: Path, as_json: bool) -> int:
    catalog = _load_catalog(repo)
    rows = []
    for name, entry in catalog.get("actions", {}).items():
        invoke = entry.get("invoke")
        if isinstance(invoke, list) and invoke:
            invoke_kind = invoke[0].get("kind", "?")
        elif isinstance(invoke, dict):
            invoke_kind = invoke.get("kind", "?")
        else:
            invoke_kind = "?"
        observe = entry.get("observe")
        observe_kind = observe.get("kind", "-") if isinstance(observe, dict) else "-"
        rows.append({"name": name, "invoke": invoke_kind, "observe": observe_kind})
    out = {"actions": rows}
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        print(f"{'ACTION':<24} {'INVOKE':<20} OBSERVE")
        for r in rows:
            print(f"{r['name']:<24} {r['invoke']:<20} {r['observe']}")
    return 0


def cmd_probe(repo: Path, as_json: bool) -> int:
    catalog = _load_catalog(repo)
    target = catalog["target"]
    bridges = []
    if target.get("platform") == "android":
        bridges.append(adb_input.probe(target))
    elif target.get("platform") == "pc":
        bridges.append(sendinput.probe(target))
    else:
        bridges.append({"kind": "target", "ok": False, "detail": f"unknown platform: {target.get('platform')!r}"})
    bridges.append(log_tail.probe(target))
    ok = all(b["ok"] for b in bridges)
    out = {"profile": "game-re", "target": {k: target.get(k) for k in ("platform", "device", "window", "pid")}, "bridges": bridges, "ok": ok}
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        for b in bridges:
            mark = "OK " if b["ok"] else "FAIL"
            print(f"[{mark}] {b['kind']:<12} {b['detail']}")
        print("OK" if ok else "FAIL")
    return 0 if ok else 2


def cmd_trigger(repo: Path, action_name: str, cli_args: dict[str, str], as_json: bool) -> int:
    catalog = _load_catalog(repo)
    target = catalog["target"]
    actions = catalog.get("actions", {})
    if action_name not in actions:
        out = {"action": action_name, "status": "unknown_action", "invoke": None, "observe": None,
               "started_at": _now_iso(), "error": f"action not in catalog; see 'harness list'"}
        print(json.dumps(out, indent=2) if as_json else f"unknown action: {action_name}")
        return 3
    entry = actions[action_name]
    started_at = _now_iso()
    started_mono = time.monotonic()

    invoke_specs = entry.get("invoke")
    if isinstance(invoke_specs, dict):
        invoke_specs = [invoke_specs]
    if not isinstance(invoke_specs, list) or not invoke_specs:
        out = {"action": action_name, "status": "unknown_action", "started_at": started_at,
               "invoke": None, "observe": None, "error": "action has no invoke spec"}
        print(json.dumps(out, indent=2) if as_json else f"action {action_name} has no invoke spec")
        return 3

    scope: dict[str, Any] = dict(cli_args)
    step_results: list[dict] = []
    invoke_result: dict | None = None
    for spec in invoke_specs:
        resolved = _substitute(spec, scope)
        invoke_result, outputs = _dispatch_invoke(target, resolved)
        step_results.append(invoke_result)
        if outputs:
            scope.update(outputs)
        if invoke_result["error"]:
            break

    if invoke_result and invoke_result["error"]:
        err = invoke_result["error"]
        if err.startswith("bridge_down"):
            status = "bridge_down"
        elif err.startswith("locate_failed"):
            status = "locate_failed"
        else:
            status = "timeout"
        summary = dict(invoke_result)
        if len(step_results) > 1:
            summary["steps"] = step_results
        out = {"action": action_name, "status": status, "started_at": started_at,
               "invoke": summary, "observe": None}
        print(json.dumps(out, indent=2) if as_json else f"[{status}] {err}")
        return 4

    observe_spec = entry.get("observe")
    symbols = _load_symbols(repo)
    if isinstance(observe_spec, dict):
        observe_spec = _substitute(observe_spec, scope)
    observe_result = _dispatch_observe(target, observe_spec, symbols, started_mono)

    summary = dict(invoke_result) if invoke_result else {}
    if len(step_results) > 1:
        summary["steps"] = step_results
    out = {"action": action_name, "status": "ok", "started_at": started_at,
           "invoke": summary, "observe": observe_result}
    if as_json:
        print(json.dumps(out, indent=2))
    else:
        inv = invoke_result or {}
        obs = observe_result or {}
        print(f"action={action_name} status=ok invoke={inv.get('bridge')} "
              f"observe={'matched=' + str(obs.get('matched')) if observe_result else 'none'}")
        if observe_result and observe_result.get("evidence"):
            print(f"evidence: {observe_result['evidence']}")
    return 0


def cmd_observe(repo: Path, action_name: str, duration_s: float, as_json: bool) -> int:
    catalog = _load_catalog(repo)
    target = catalog["target"]
    actions = catalog.get("actions", {})
    if action_name not in actions:
        print(f"unknown action: {action_name}")
        return 3
    observe_spec = actions[action_name].get("observe")
    if not observe_spec:
        print(f"action {action_name} has no observer")
        return 3
    spec = dict(observe_spec)
    spec["timeout_ms"] = int(duration_s * 1000)
    started_mono = time.monotonic()
    result = _dispatch_observe(target, spec, _load_symbols(repo), started_mono)
    out = {"action": action_name, "observe": result}
    print(json.dumps(out, indent=2) if as_json else str(result))
    return 0 if result and result.get("matched") else 5


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--repo", default=argparse.SUPPRESS, help="Path to repo root (containing .harness/actions.yaml)")
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Emit structured JSON output")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Game action harness — trigger pseudo-human input and observe hook effects.",
    )
    _add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (("list", "List actions in the catalog"), ("probe", "Check bridges are up")):
        sp = sub.add_parser(name, help=help_text)
        _add_common(sp)

    trig = sub.add_parser("trigger", help="Trigger an action and observe the effect")
    _add_common(trig)
    trig.add_argument("action", help="Action name")
    trig.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE",
                      help="Override a $variable field in the action's invoke/observe spec")

    obs = sub.add_parser("observe", help="Passively observe the action's target without triggering")
    _add_common(obs)
    obs.add_argument("action", help="Action name")
    obs.add_argument("--duration", default="5s", help="Observe window, e.g. '5s', '1500ms' (default 5s)")

    ns = parser.parse_args()
    if not hasattr(ns, "repo"):
        ns.repo = "."
    if not hasattr(ns, "json"):
        ns.json = False
    return ns


def _parse_duration(s: str) -> float:
    s = s.strip().lower()
    if s.endswith("ms"):
        return float(s[:-2]) / 1000.0
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


def main() -> int:
    args = _parse_args()
    repo = Path(args.repo).resolve()
    # Make all relative paths in the catalog resolve against the repo root consistently.
    if repo.is_dir():
        os.chdir(repo)
    cli_args: dict[str, str] = {}
    for pair in getattr(args, "arg", []) or []:
        if "=" not in pair:
            sys.stderr.write(f"--arg expects KEY=VALUE, got {pair!r}\n")
            return 64
        k, v = pair.split("=", 1)
        cli_args[k.strip()] = v.strip()

    try:
        if args.command == "list":
            return cmd_list(repo, args.json)
        if args.command == "probe":
            return cmd_probe(repo, args.json)
        if args.command == "trigger":
            return cmd_trigger(repo, args.action, cli_args, args.json)
        if args.command == "observe":
            return cmd_observe(repo, args.action, _parse_duration(args.duration), args.json)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 66
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        return 65
    sys.stderr.write(f"unknown command: {args.command}\n")
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
