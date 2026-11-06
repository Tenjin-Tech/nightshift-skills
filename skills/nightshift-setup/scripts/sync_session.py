#!/usr/bin/env python3
"""Night Shift session sync: a Claude Code hook that uploads what this cloud session did, so its runs' pages show it.

Runs only in a cloud session with NIGHTSHIFT_TOKEN set. It never stops the session: every failure ends in exit 0, and a
failed upload at Stop reports itself as a system message. Thinking is left out, long text is cut, and the values of
this environment's secrets are masked before anything leaves; the factory masks common secret shapes again."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_TEXT = 2000
MAX_STEPS = 2000
EVERY_SECONDS = 60  # PostToolUse uploads at most this often, so a run that dies later still shows its steps.
SECRET_NAME = re.compile(r"TOKEN|SECRET|KEY|PASSWORD|PASSWD|CREDENTIAL", re.I)
MIN_SECRET = 5  # Shorter, and masking says nothing: "true" or "1" would vanish from every line.
REPOSITORY = re.compile(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$")  # owner/repo, so credentials in the remote's URL stay here.


def secrets_of(environ: dict[str, str]) -> list[str]:
    """Longest first, each also as JSON escapes it, since a tool call's input is masked as JSON."""
    values = {value for name, value in environ.items() if SECRET_NAME.search(name) and len(value) >= MIN_SECRET}
    return sorted(values | {json.dumps(value, ensure_ascii=False)[1:-1] for value in values}, key=len, reverse=True)


def clean(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, "[redacted]")
    return text if len(text) <= MAX_TEXT else f"{text[:MAX_TEXT]}… [+{len(text) - MAX_TEXT} chars]"


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block["text"] for block in content if isinstance(block, dict) and isinstance(block.get("text"), str))
    return ""


def entries_of(path: Path, minion: str | None) -> Iterator[dict[str, Any]]:
    """Its people's and agents' turns, without injected text or, in the session's file, a subagent's own."""
    for line in path.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") in ("user", "assistant") and entry.get("timestamp") and not entry.get("isMeta") \
                and (minion is not None or not entry.get("isSidechain")):
            yield entry


def step_of(block: Any, own_kind: str, secrets: list[str]) -> dict[str, Any] | None:
    """One content block as a SessionStep in backend/transcripts.py; None for thinking and anything else."""
    kind = block.get("type") if isinstance(block, dict) else None
    if kind == "text" and block.get("text"):
        return {"kind": own_kind, "text": clean(block["text"], secrets)}
    if kind == "tool_use":
        return {"kind": "tool", "tool": str(block.get("name"))[:200],
                "text": clean(json.dumps(block.get("input"), ensure_ascii=False), secrets)}
    if kind == "tool_result":
        return {"kind": "result", "error": bool(block.get("is_error")), "text": clean(text_of(block.get("content")), secrets)}
    return None


def steps_of(path: Path, minion: str | None, secrets: list[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for entry in entries_of(path, minion):
        content = (entry.get("message") or {}).get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content or []
        own_kind = "prompt" if entry["type"] == "user" else "agent"
        made = (step_of(block, own_kind, secrets) for block in blocks)
        steps += [{**step, "at": entry["timestamp"], "minion": minion} for step in made if step]
    return steps


def session_steps(transcript: Path, secrets: list[str]) -> list[dict[str, Any]]:
    """The session and its subagents in time order, newest kept when it runs long."""
    steps = steps_of(transcript, None, secrets)
    for path in sorted(transcript.with_suffix("").glob("subagents/agent-*.jsonl")):
        meta = path.with_name(f"{path.stem}.meta.json")
        try:
            minion = str(json.loads(meta.read_text()).get("agentType") or "minion")[:200]
        except (OSError, ValueError):
            minion = "minion"
        steps += steps_of(path, minion, secrets)
    return sorted(steps, key=lambda step: step["at"])[-MAX_STEPS:]


def due(session: str, event: str | None, now: float) -> bool:
    stamp = Path(tempfile.gettempdir()) / f"nightshift-sync-{session}"
    if event == "PostToolUse" and stamp.exists() and now - stamp.stat().st_mtime < EVERY_SECONDS:
        return False
    stamp.touch()
    return True


def upload(url: str, token: str, body: bytes) -> str | None:
    """curl, not urllib: a cloud sandbox sets curl up for its proxy. Returns what went wrong. The key goes on stdin, so
    no process list shows it."""
    with tempfile.NamedTemporaryFile(suffix=".json") as data:  # Readable only by this user.
        data.write(body)
        data.flush()
        config = f'header = "Authorization: Bearer {token}"\n'
        done = subprocess.run(
            ["curl", "-sS", "-m", "15", "-o", "/dev/null", "-w", "%{http_code}", "-X", "PUT", "-H",
             "Content-Type: application/json", "--data-binary", f"@{data.name}", "--config", "-", url],
            input=config, capture_output=True, text=True, timeout=20, check=False)
    if done.returncode == 0 and done.stdout.startswith("2"):
        return None
    return done.stderr.strip()[:300] or f"HTTP {done.stdout}"


def main() -> None:
    token = os.environ.get("NIGHTSHIFT_TOKEN")
    remote = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID")
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true" or not token or not remote:
        return
    hook = json.load(sys.stdin)
    event = hook.get("hook_event_name")
    if not due(remote, event, time.time()):
        return
    session = re.sub(r"^cse_", "session_", remote)
    project = os.environ.get("CLAUDE_PROJECT_DIR") or hook.get("cwd") or "."
    origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=project, capture_output=True, text=True,
                            timeout=5, check=True).stdout.strip()
    repository = REPOSITORY.search(origin)
    if not repository:
        return
    steps = session_steps(Path(hook["transcript_path"]), secrets_of(dict(os.environ)))
    factory = os.environ.get("NIGHTSHIFT_URL", "https://nightshiftfactory.com").rstrip("/")
    problem = upload(f"{factory}/api/sessions/{session}/transcript", token,
                     json.dumps({"repository": repository.group(1), "steps": steps}).encode())
    if problem and event == "Stop":
        print(json.dumps({"systemMessage": f"Night Shift could not upload this session: {problem}"}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # A sync problem must never stop or fail the session.
        print(f"Night Shift session sync: {error} at {datetime.now(timezone.utc).isoformat()}", file=sys.stderr)
    sys.exit(0)
