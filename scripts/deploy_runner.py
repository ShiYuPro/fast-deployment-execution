#!/usr/bin/env python3
"""Run an immutable, timed deployment plan without rediscovering its steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_KINDS = {"preflight", "build", "dry-run", "deploy", "verify"}
DRY_RUN_KINDS = {"preflight", "build", "dry-run"}


class PlanError(Exception):
    pass


def load_plan(path: Path) -> Dict[str, Any]:
    try:
        raw = path.read_bytes()
        plan = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError("BLOCKED_PLAN_READ={}".format(exc)) from exc

    if not isinstance(plan, dict) or plan.get("version") != 1:
        raise PlanError("BLOCKED_PLAN_VERSION")
    if not isinstance(plan.get("name"), str) or not plan["name"].strip():
        raise PlanError("BLOCKED_PLAN_NAME")
    deadline = plan.get("deadline_seconds", 900)
    if not isinstance(deadline, int) or deadline < 30 or deadline > 7200:
        raise PlanError("BLOCKED_PLAN_DEADLINE")
    phases = plan.get("phases")
    if not isinstance(phases, list) or not phases:
        raise PlanError("BLOCKED_PLAN_PHASES")

    seen = set()
    deploy_count = 0
    for phase in phases:
        if not isinstance(phase, dict):
            raise PlanError("BLOCKED_PHASE_FORMAT")
        phase_id = phase.get("id")
        kind = phase.get("kind")
        argv = phase.get("argv")
        if not isinstance(phase_id, str) or not phase_id or phase_id in seen:
            raise PlanError("BLOCKED_PHASE_ID")
        seen.add(phase_id)
        if kind not in ALLOWED_KINDS:
            raise PlanError("BLOCKED_PHASE_KIND={}".format(phase_id))
        if kind == "deploy":
            deploy_count += 1
        if (
            not isinstance(argv, list)
            or not argv
            or any(not isinstance(item, str) or "\x00" in item for item in argv)
        ):
            raise PlanError("BLOCKED_PHASE_ARGV={}".format(phase_id))
        timeout = phase.get("timeout_seconds", 600)
        if not isinstance(timeout, int) or timeout < 1 or timeout > 7200:
            raise PlanError("BLOCKED_PHASE_TIMEOUT={}".format(phase_id))
        reusable = phase.get("reusable_seconds", 0)
        if not isinstance(reusable, int) or reusable < 0 or reusable > 3600:
            raise PlanError("BLOCKED_PHASE_REUSE={}".format(phase_id))
        env = phase.get("env", {})
        if not isinstance(env, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in env.items()
        ):
            raise PlanError("BLOCKED_PHASE_ENV={}".format(phase_id))
    if deploy_count > 1:
        raise PlanError("BLOCKED_MULTIPLE_DEPLOY_PHASES")

    if deploy_count:
        deploy_index = next(i for i, phase in enumerate(phases) if phase['kind'] == 'deploy')
        if not any(phase['kind'] == 'verify' for phase in phases[deploy_index + 1:]):
            raise PlanError("BLOCKED_POST_DEPLOY_VERIFICATION_MISSING")

    plan["_sha256"] = hashlib.sha256(raw).hexdigest()
    plan["_path"] = str(path.resolve())
    return plan


def state_path(plan: Dict[str, Any], plan_path: Path) -> Path:
    configured = plan.get("state_file")
    if configured:
        target = Path(configured)
        return target if target.is_absolute() else plan_path.parent / target
    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in plan["name"])
    return plan_path.parent / ".deploy-exec" / (safe_name + ".json")


def read_state(path: Path, plan_sha: str) -> Dict[str, Any]:
    try:
        state = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"plan_sha256": plan_sha, "phases": {}}
    if state.get("plan_sha256") != plan_sha:
        return {"plan_sha256": plan_sha, "phases": {}}
    if not isinstance(state.get("phases"), dict):
        state["phases"] = {}
    return state


def write_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def resolve_cwd(plan_path: Path, phase: Dict[str, Any]) -> Path:
    configured = phase.get("cwd", ".")
    target = Path(configured)
    target = target if target.is_absolute() else plan_path.parent / target
    resolved = target.resolve()
    if not resolved.is_dir():
        raise PlanError("BLOCKED_PHASE_CWD={}".format(phase["id"]))
    return resolved


def run(plan_path: Path, mode: str, execute: bool, fresh: bool) -> int:
    plan = load_plan(plan_path)
    if mode == "deploy" and not execute:
        raise PlanError("BLOCKED_EXECUTE_FLAG_REQUIRED")

    selected: List[Dict[str, Any]] = []
    for phase in plan["phases"]:
        if mode == "dry-run" and phase["kind"] not in DRY_RUN_KINDS:
            continue
        selected.append(phase)
    if mode == "dry-run" and not any(phase["kind"] == "dry-run" for phase in selected):
        raise PlanError("BLOCKED_DRY_RUN_PHASE_MISSING")
    if mode == "deploy" and not any(phase["kind"] == "deploy" for phase in selected):
        raise PlanError("BLOCKED_DEPLOY_PHASE_MISSING")

    checkpoint = state_path(plan, plan_path)
    state = read_state(checkpoint, plan["_sha256"])
    started = time.monotonic()
    deadline = plan.get("deadline_seconds", 900)
    print("DEPLOY_EXEC_START name={} mode={} deadline={}s".format(plan["name"], mode, deadline))

    for phase in selected:
        elapsed = time.monotonic() - started
        remaining = deadline - elapsed
        if remaining <= 0:
            print("BLOCKED_DEPLOY_DEADLINE before={}".format(phase["id"]), file=sys.stderr)
            return 124
        cwd = resolve_cwd(plan_path, phase)
        env = os.environ.copy()
        env.update(phase.get("env", {}))
        timeout = min(phase.get("timeout_seconds", 600), max(1, int(remaining)))
        phase_started = time.monotonic()
        print("PHASE_START id={} kind={} timeout={}s".format(phase["id"], phase["kind"], timeout))
        sys.stdout.flush()
        try:
            completed = subprocess.run(phase["argv"], cwd=str(cwd), env=env, timeout=timeout)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            exit_code = 124
        except OSError:
            exit_code = 127
        duration = round(time.monotonic() - phase_started, 3)
        phase_state = {
            "status": "passed" if exit_code == 0 else "failed",
            "kind": phase["kind"],
            "duration_seconds": duration,
            "finished_at": time.time(),
            "exit_code": exit_code,
        }
        state.setdefault("phases", {})[phase["id"]] = phase_state
        state["plan_sha256"] = plan["_sha256"]
        state["updated_at"] = time.time()
        write_state(checkpoint, state)
        print("PHASE_{} id={} elapsed={}s".format("OK" if exit_code == 0 else "FAILED", phase["id"], duration))
        if exit_code != 0:
            print("DEPLOY_EXEC_STOP failed={} total={}s".format(phase["id"], round(time.monotonic() - started, 3)))
            return exit_code

    total = round(time.monotonic() - started, 3)
    marker = "DRY_RUN_PHASES_COMPLETE" if mode == "dry-run" else "DEPLOY_PHASES_COMPLETE"
    print("{} name={} total={}s state={}".format(marker, plan["name"], total, checkpoint))
    return 0


def show(plan_path: Path) -> int:
    plan = load_plan(plan_path)
    print("PLAN_OK name={} sha256={} deadline={}s".format(
        plan["name"], plan["_sha256"], plan.get("deadline_seconds", 900)
    ))
    for phase in plan["phases"]:
        print("{}\t{}\ttimeout={}s\treuse={}s".format(
            phase["id"], phase["kind"], phase.get("timeout_seconds", 600), phase.get("reusable_seconds", 0)
        ))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("plan", type=Path)
    for command in ("dry-run", "deploy"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("plan", type=Path)
        command_parser.add_argument("--fresh", action="store_true")
        if command == "deploy":
            command_parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "check":
            return show(args.plan)
        return run(args.plan, args.command, getattr(args, "execute", False), args.fresh)
    except PlanError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
