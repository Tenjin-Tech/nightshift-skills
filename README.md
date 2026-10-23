# Night Shift skills

Agent skills for [Night Shift](https://nightshiftfactory.com), for Claude Code and Codex. Install them into the repository whose jobs Night Shift should run:

```bash
npx skills add Tenjin-Tech/nightshift-skills -a claude-code -a codex --copy -y
```

Then run `/nightshift-setup` (Codex: `$nightshift-setup`). Refresh them later with `npx skills update`.

| Skill | Does |
| --- | --- |
| `nightshift-setup` | Analyzes the repository, proposes background jobs, writes `.nightshift/` and one minion agent per role |
| `nightshift-factory` | Claims this repository's jobs and hands each to its role's minion until nothing is left |
| `nightshift-status` | Read-only list of jobs, eligibility, and latest runs |

This repository is published automatically; changes made here are overwritten.
