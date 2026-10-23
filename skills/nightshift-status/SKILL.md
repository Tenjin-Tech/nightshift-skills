---
name: nightshift-status
description: Show this repository's Night Shift jobs - which are eligible, which are waiting and why, and each job's latest run. Use for /nightshift-status, $nightshift-status, or "what is the factory doing".
---

Call the Night Shift `factory_status` tool (the `nightshift` server or the Night Shift connector) with repository set to `git remote get-url origin` (omit it to see every repository's jobs), and report each job as one row: job, role, merge mode (manual or auto, for jobs that write), eligibility, latest run outcome. For a job with merge mode auto waiting on `PR #N awaiting merge` (the factory left it open), add the state of its checks (for example `PR #N awaiting merge (checks running)`) from `gh api --paginate repos/<owner>/<repo>/commits/<sha>/check-runs --jq '.check_runs[] | {name, status, conclusion}'` and `gh api repos/<owner>/<repo>/commits/<sha>/status --jq '.statuses[] | {context, state}'`, where sha is `gh api repos/<owner>/<repo>/pulls/N --jq .head.sha`: cloud sessions reject `gh pr`. This is read-only: do not call `next_assignment` or `finish_assignment`.

If the tool is missing, report that the `nightshift` MCP server is not connected: check `.mcp.json` (Claude Code) or `.codex/config.toml` (Codex), and that `NIGHTSHIFT_TOKEN` is set.
