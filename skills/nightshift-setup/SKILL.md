---
name: nightshift-setup
description: Set up Night Shift for the current repository - analyze it, propose background jobs, write them to .nightshift/ (like .github/workflows), create one minion agent per role, and validate everything with the factory. Use for /nightshift-setup, $nightshift-setup, "set up the factory here", or "add a Night Shift job".
---

Night Shift jobs live in the repository they watch, the way GitHub Actions workflows live in `.github/workflows/`. Each job belongs to a role, and each role has a minion: an agent that runs that role's jobs, reading only unless they write, and appears on the factory floor.

```
.nightshift/jobs/<id>.toml           # one standing job
.nightshift/procedures/<name>.md     # the instructions its minion follows
.nightshift/defaults.toml            # optional: agent = "claude" or "codex" for every job that sets none
.claude/agents/<role>.md             # the role's minion for Claude Code
.codex/agents/<role>.toml            # the same minion for Codex
.mcp.json, .codex/config.toml        # the factory connection, so every session (including cloud) can reach it
.claude/settings.json                # with a job that writes: the permission to open its pull requests
```

## Steps

1. Check that the `nightshift` MCP server's `validate_jobs` tool is available. If it is not, stop and tell the user how to connect, then to restart the session:
   - Claude Code: `claude mcp add --scope project --transport http nightshift <factory URL>/mcp/ --header 'Authorization: Bearer ${NIGHTSHIFT_TOKEN}'` (single quotes keep the variable unexpanded in `.mcp.json`)
   - Codex: the `.codex/config.toml` entry in step 8
   - and `export NIGHTSHIFT_TOKEN=<API key from the factory's Settings, API keys>`
2. Run `git remote get-url origin` and note the repository (owner/repo). Read `.nightshift/` if it exists; extend it rather than replacing it. The Night Shift skills are installed with `npx skills add Tenjin-Tech/nightshift-skills` and tracked in `skills-lock.json`. To refresh them, run `npx skills update`; never copy or edit their files by hand.
3. Analyze the repository before proposing anything: each job you propose must point at something you found here. Read the README, AGENTS.md or CLAUDE.md and the conventions they state; the manifests and lockfiles (`package.json`, `pyproject.toml`, `go.mod`, ...); how it is tested, linted and built (`Makefile`, `.github/workflows/`, the commands they run); the top-level folders; and what changes often (`git log --stat -50`). For code, also measure:
   - `TODO`, `FIXME`, `HACK` and `XXX` markers (`git grep -n -E "TODO|FIXME|HACK|XXX"`): how many, and in which folders;
   - duplicated code: the same function or block copied across files, helpers re-implemented in several modules;
   - code that changes often with no tests near it, and checks that exist but CI does not run;
   - documentation naming files, commands or options the code no longer has;
   - whether work is tracked in Linear: ticket ids such as `ENG-123` in commit messages and branch names (`git log --oneline -200`), a `linear` server in `.mcp.json`, or Linear named in AGENTS.md or CLAUDE.md.
   Note each finding with a `file:line` or a count; step 4 quotes them.
4. Propose jobs from what you found, best evidence first, and ask the user which to keep (recommend two or three to start). For each, say in one line what it watches, what it would have caught today (for example "14 FIXMEs, 9 of them in `src/billing/`"), and whether it audits or writes. Drop a candidate with no evidence in this repository. Candidates that suit most code repositories:
   - **todo-fixer** (writes, scope the source folder): each run settles one `TODO` or `FIXME` it can fix and test inside `scope`, runs the repository's checks, and removes the marker; a marker it cannot settle safely goes in the report instead.
   - **duplicate-finder** (audit): finds code repeated across files and proposes one extraction, with every copy's `file:line` and the callers to change.
   - **code-quality** (audit): one evidence-backed improvement per run (correctness, error handling, performance, dead code) as a finite task.
   - **test-gaps** (audit, or a writer scoped to the tests folder that watches the source): after commits to the source, checks the changed behaviour is tested, and proposes or writes the missing tests.
   - **docs-refresh** (writes `docs/`, watches the source): keeps the documentation true to the code.
   - **dependency-drift** (audit): ranges without a lockfile, unused or duplicated dependencies.
   - **ticket-backlog** (writes, scope `.`), only when work is tracked in Linear: a `[hopper]` hands each run the oldest ticket a person labelled, and the job implements it as one pull request. Ask the user whether they want one, and for the team's key (the prefix of its ticket ids) and the label people will put on tickets for Night Shift (suggest `night-shift`); write those as `team` and `label`, and leave out `every`, so the job runs only when a ticket waits. Its procedure reads the ticket from the `ticket` input, claims it (assigned, In Progress), moves it back to its earlier status if it stops before finishing (Night Shift offers a ticket again only in the hopper's `states`), implements it with a test, comments the result on it, starts the report with `Linear: <identifier>` and `Branch: <branch>`, and ends no_op to decline a ticket it cannot verify, after commenting why and removing the label.
   For notes or documentation repositories: notes left in an inbox, decisions without an owner, broken links. Beyond these, look for a convention the repository states but nothing enforces.
   - Most jobs audit: read-only, findings become proposals awaiting approval.
   - A job may change the repository when the change is safe to review as a pull request, for example updating documentation to match the code. It edits only inside its `scope`; the factory session commits its edits on a branch and opens a pull request, which is the human review. A writer that changes code names the repository's checks in its procedure (step 3), so its minion gets `Bash`.
   - When it runs: by default, after a commit changes its `scope` (list other paths in `watch` when they should count too, since docs go stale when the code changes). Set `every = "7d"` (or `12h`, `30m`) to run it on a schedule instead, whether or not anything changed, or, for exact times, `cron = "0 9 * * MON"` (standard 5 fields, UTC). Add `shift = "night"` to any of these to run it only between 22:00 and 06:00 UTC.
   If you cannot ask, keep the two or three with the best evidence and continue.
5. Before writing anything, show the user what each kept job will be allowed to do, and ask what to change. The defaults allow more than people expect, so on a first setup (no `.nightshift/` yet) say so plainly. One row per job, for example:

   | Job | Edits | Pull request merged by | Network | Tracker issues | Commands | Runs | Priority |
   |---|---|---|---|---|---|---|---|
   | todo-fixer | `src/` only, as a pull request | a person | yes | may create them | `make test` | after commits to `src/`, at night | leftover |
   | duplicate-finder | nothing | - | yes | may create them | none | every 7 days | if_budget |

   Then list the levers, one line each, from "Restricting a minion" below (read-only, `merge = "auto"`, `task_creation`, `network`, `proposals`, a procedure rule, the minion's `tools`), plus `agent` and `priority`: suggest `if_budget` or `leftover` for improvement jobs, so they never use allowance mandatory jobs need. Explain priority as the Floor shows it, as coins at the job's feet, each the share of the plan's allowance the job may spend: three coins `mandatory` (all of it), two `if_budget` (while each window is on pace to keep 10% at its reset), one `optional` (25%), an apple core `leftover` (only the last 6 hours before the longest window resets). The room kept is for a whole window ahead and shrinks as the reset nears, so the end of a window is spent, not lost. A red cross over the coins means the job waits now: at the current pace a window would end above its line. It runs again once that window resets or the pace slows. The factory reads usage from a Claude token saved in Settings, or else from what workers report. Ask "Keep these, or change any?" and apply the answers. If you cannot ask, keep the defaults and list them in step 11 so the user can change them later.
6. Write each job and its procedure using the formats below. Reuse one role for similar jobs; keep jobs that write in their own roles, since a role's minion either reads or writes.
7. Write one minion per role, using the formats below (the writer variant for roles whose jobs write). Do not overwrite an existing agent file with the same name unless it is a Night Shift minion.
8. Make sure the factory connection is committed, keeping any other entries in these files:
   - `.mcp.json`: a `nightshift` server with `"type": "http"`, the factory URL ending in `/mcp/`, and the header `"Authorization": "Bearer ${NIGHTSHIFT_TOKEN}"`. `claude mcp get nightshift` shows the URL you are connected to.
   - `.codex/config.toml`:
     ```toml
     [mcp_servers.nightshift]
     url = "<factory URL>/mcp/"
     bearer_token_env_var = "NIGHTSHIFT_TOKEN"
     default_tools_approval_mode = "approve"   # its tools only touch the factory ledger
     ```
   - When any job writes (`source_access = "write_in_scope"`), `.claude/settings.json`: Claude Code asks before opening a pull request no permission rule allows, and an unattended session (auto mode, a cloud routine) may refuse it. Add this rule to `permissions.allow`, and the one under `deny` with it, with the owner/repo from step 2, creating the file or merging into it without dropping any key or rule:
     ```json
     { "permissions": { "allow": ["Bash(gh api repos/<owner>/<repo>/pulls -f *)"], "deny": ["Bash(gh api *--hostname*)"] } }
     ```
     Add too, for each distinct `scope` of a job that writes, `Bash(rm ./<scope>/*)` (`Bash(rm ./*)` for `.`): a minion deletes a file with a plain `rm ./<path>`, and without the rule the unattended session stops at the prompt until its lease runs out. Tell the user it lets any session delete files inside those folders without asking; an `rm` with an option, a path outside them or a `..` still asks. An `ask` or `deny` rule that also matches `rm ./<scope>/<file>` or the pull request command (such as `Bash(**rm **)`) wins over `allow`: name it to the user and propose removing it. The Floor's Needs you lists the rules a repository still lacks after each check-in.
     It must be the committed file, not `~/.claude/settings.json` or `.claude/settings.local.json`: cloud sessions only read the repository's. Tell the user it lets any Claude Code session in this repository open pull requests without asking, and since the rule matches any options after `-f`, also send a file it can read (`--input`, `-F field=@<file>`) to this repository's pull requests; the deny rule keeps the session from naming another host (a `GH_HOST` it sets itself still asks). It cannot merge, close or comment on them, and no job can edit `.claude/`. The session also creates a branch, commits and pushes it: say so if the file has no rule for those either.
   Run `git check-ignore .mcp.json .codex/config.toml .claude/settings.json`: if one is ignored, tell the user, because cloud sessions will not get it.
9. Call `validate_jobs` with every file under `.nightshift/` (path to content). Fix what it reports and validate again until it passes. Check that each `scope` directory exists.
10. Show the user the files, and the diff of a `.claude/settings.json` that already existed. Commit them on a new branch only if the user agrees; do not push or open a pull request without asking.
11. Tell the user what happens next: nothing to register. After the change is merged into the jobs branch (the default branch, unless changed in Settings), the first `/nightshift-factory` (Claude Code) or `$nightshift-factory` (Codex) run there checks the jobs in and hands each to its minion; a Claude Code routine on this repository with the prompt `/nightshift-factory` runs them on its schedule. To try them before merging, run `/nightshift-factory` on this branch and ask it to run this branch's jobs. A session reaches the factory through the Night Shift connector (claude.ai, signed in with GitHub: attach it to the routine) or `.mcp.json` / `.codex/config.toml` with `NIGHTSHIFT_TOKEN`, an API key the user creates in the factory's Settings, API keys (for cloud sessions, set it in the cloud environment, as an environment variable rather than a secret in Codex cloud, and allow the factory host in its network access). With a `merge = "auto"` job, use the connector or an API key: the factory merges as that GitHub user, and never for the factory's shared access key. `/nightshift-status` shows the jobs.
   When a job has a `[hopper]`, also say Night Shift reads its tickets from the Linear workspace connected in the factory's Settings, Assigned issues, with this repository chosen there: until then the job waits and says so. People hand it work by putting the label on a ticket.
   When a job reads Dependabot alerts (a security-fix or dependabot job), also say its routine needs a GitHub credential that can read them: cloud sessions reach GitHub through the account's GitHub connection, by default the Claude GitHub App, which cannot, so the job fails with 403 `Resource not accessible by integration`. Give both ways to grant it: (1) in a local terminal where `gh auth status` is logged in, start `claude`, check that `/status` shows the claude.ai account that owns the routine, and type `/web-setup` (not in a cloud session, where it is not available); it must print `Connected as <github-user>`, and it replaces the GitHub connection of all the account's cloud sessions (on Team and Enterprise plans an Owner first turns on Quick setup, Organization settings > Claude Code); (2) or set `GH_TOKEN` in the routine's cloud environment variables, a fine-grained token limited to the repository with Dependabot alerts: read, Pull requests: read and write, and Metadata: read, which anyone using the environment can read. When you can, run the check `gh api "repos/<owner>/<repo>/dependabot/alerts?state=open&per_page=1" --jq length` and report its result: a number means this session's credential can read the alerts (in a cloud session, so can the routine's); a 403 `Resource not accessible by integration` means it cannot yet and `Resource not accessible by personal access token` means the `GH_TOKEN` lacks Dependabot alerts: read (a rate-limit 403 says nothing about the credential).

## Job format: `.nightshift/jobs/<id>.toml`

Only these fields are accepted; anything else fails validation.

```toml
id = "inbox-triage"                       # letters, digits, - and _; unique in this repository
owner_role = "notes-gardener"             # who does this kind of work; reuse a role for similar jobs
mission = "Find notes in the inbox that need a home, with evidence."
procedure = "procedures/inbox-triage.md"  # relative to .nightshift/
scope = "Inbox"                           # a directory, relative to the repository root; . for the whole repository
output = ["triage_report", "optional_finite_task_proposal"]
lease_minutes = 30
# model = "high"                          # optional: the minion's model; low (Haiku, luna), medium (default:
                                          # Sonnet, terra), high (Opus, sol), xhigh (Fable, astra)
# model = { codex = "gpt-6.1-sol" }       # or per agent, a level or an exact model; others get medium
# effort = "high"                         # optional: how hard it thinks; low, medium (default), high, xhigh
# priority = "if_budget"                  # optional: mandatory (default) runs whatever the provider allowance;
                                          # if_budget needs each window on pace to keep 10% at its reset
                                          # (or usage unknown); optional needs 25%; both less as the reset nears
                                          # leftover only spends what a reset would waste: the last 6 hours of the longest
                                          # window; handed out last

[permissions]                             # these exact values; jobs are read-only
source_access = "read_only"
external_writes = "forbidden"
# task_creation = "human_approval_required"  # optional: forbid the tracker issue the procedure asks for; only a proposal
# network = "forbidden"                   # optional: network only for the repository's bootstrap and checks
# proposals = "forbidden"                 # optional: no proposals; follow-ups become tracker issues
```

A job that changes the repository edits only inside `scope`, delivered as a pull request, and can watch other paths:

```toml
id = "docs-refresh"
owner_role = "docs-writer"
mission = "Keep docs/ accurate to the code in src/."
procedure = "procedures/docs-refresh.md"
scope = "docs"                            # the only directory it may edit
every = "7d"                              # weekly, whether or not anything changed; omit to run on changes
# cron = "0 9 * * MON"                    # advanced, instead of every: Mondays 09:00 UTC
# shift = "night"                         # only run between 22:00 and 06:00 UTC, whatever makes it due
# agent = "codex"                         # only Codex workers run it ("claude": only Claude Code; "any": both)
# agent = ["codex", "claude"]             # Codex while it can; Claude when Codex is out of allowance or not checking in
# runs_on = "brain-a-reader"              # only routines whose NIGHTSHIFT_LABELS include this label run it
watch = ["src"]                           # without every: also run again when these change
output = ["docs_change"]
# [hopper]                                # run on the Linear tickets a person labels: one per run, oldest first
# tracker = "linear"
# team = "ENG"                            # the team's key, as in ENG-123
# label = "night-shift"

[permissions]
source_access = "write_in_scope"
external_writes = "pull_request"          # required with write_in_scope, and only allowed with it
# merge = "auto"                          # optional: the factory merges the pull request once GitHub reports it clean
```

`merge = "auto"` suits low-risk writers whose dependents should not wait for a person, for example a mirror that only touches its own folder. When the run finishes, the factory merges the pull request as the GitHub user the session is signed in as (the Night Shift connector), and only when GitHub reports it clean: it waits up to 10 minutes for the checks, and one whose checks fail or still run after that, or that waits on a review, stays open for a person. It takes effect once `merge = "auto"` is on the default branch on GitHub: running a branch's jobs before merging them never merges on its own. A session on the factory's shared access key merges as no one (an API key from Settings merges as its user), so the factory logs `pr_auto_merge_refused` and leaves the pull request open. It is only allowed for jobs that write. With `scope = "."` it still never merges changes to agent instructions: the factory's own files are outside every scope, and a pull request that touches agent instructions (any `AGENTS*.md` or `CLAUDE*.md`, the files they import, or what a symlink in those folders points to) waits for a person. Otherwise leave it out: a person merges the pull request.

`model` decides the minion's model: the factory session starts it on the newest of that family, whatever the session's own model: `low` Haiku or Codex luna, `medium` (the default) Sonnet or terra, `high` Opus or sol, `xhigh` Fable or astra. To pin a model, set it per agent: `model = { claude = "high", codex = "gpt-6.1-sol" }`, each a level or an exact model id; an agent it leaves out gets `medium`. Claude Code only picks a family, so a Claude id runs on the newest of its family. `model` never decides which agents run the job: `agent` does. `effort` decides how hard it thinks (its reasoning effort): `low`, `medium` (the default), `high` or `xhigh`. Suggest `low` for both on mechanical jobs (a mirror, a format check), and `high` for jobs that judge code or write it. Changing them never makes a job run again.

`agent` decides which workers may claim the job; leave it out and the job takes `agent` from `.nightshift/defaults.toml` (one line, `agent = "codex"`), or `"any"` without that file. Set it only when the user asks for it, for example to spend one provider's allowance. A list (`["codex", "claude"]`) is an order of preference: a later agent takes the job only while the earlier one cannot, because it has not checked in this repository within twice its Expected check-ins (a day without them) or its last usage reading leaves no room for the job's priority. A job with `runs_on` never waits: check-ins carry no labels. Changing it never makes a job run again. A job whose scope is the whole repository still runs again, as after any commit to it.

`[hopper]` hands each run the oldest Linear ticket of `team` that carries `label` (in `states`, `["Todo", "Backlog"]` unless set) and that no run took: the run finds it as `ticket` in its inputs, with its identifier, title, link and branch. Use it for a backlog a person fills by labelling tickets, instead of a procedure that lists Linear on a timer: leave out `every`, and the job runs only when a ticket waits. Night Shift reads the tickets from the Linear workspace connected to the repository in Settings, Assigned issues, and takes only those created by the people ticked there as allowed to assign issues. The procedure still moves and comments the ticket, moves it back to its earlier status when a run cannot finish (the hopper offers it again only in `states`), and ends no_op to decline one for good.

`runs_on` names a label: only sessions whose `NIGHTSHIFT_LABELS` (comma-separated, set in the routine's environment) include it claim the job; others show `waiting for a worker labelled <label>`. Jobs without it run on any session. Set it only when the user asks, for example when one routine has access another lacks. It routes work, it is not a permission: anyone who can push the job can add the label, so tell the user never to give a labelled routine access that the repository's other writers should not have. Changing it never makes a job run again.

A job that needs another job's result declares it; the factory rejects cycles and unknown outputs:

```toml
[[dependencies]]
job_id = "inbox-triage"
package = "triage_report"
```

The dependent runs when the upstream publishes new packages, so a job with dependencies and no `every` or `cron` runs only when there is something new to handle. A read-only upstream's packages, and those of a run that changed nothing (`no_op`), are available as soon as it finishes. A `write_in_scope` upstream that opens a pull request publishes its packages only once that pull request is merged: until then the dependent waits (`waiting for package: <job>/<package> (PR #N awaiting merge)`), and once it is merged, the dependent runs only from a factory session whose checkout contains the merge commit, so it always sees the merged edits. If the pull request is closed without merging, its packages are discarded and the dependent does not run (`PR #N of run <run_id> closed without merging`) until the upstream produces again.

`job_id` names a job of this repository. A dependency may name a job of another repository with `repository`, once that job lists this repository in its `consumers`:

```toml
# downstream job (acme/company-brain)
[[dependencies]]
job_id = "granola-export"
package = "digest"
repository = "acme/mind"                  # owner/repo of the upstream job
```

```toml
# upstream job (acme/mind), top level, before any [[...]] table
consumers = ["acme/company-brain"]        # repositories whose jobs may depend on its outputs
```

The dependent's session gets each package's `data` and `content` with its assignment, never the upstream repository's files, runs or reports, so the upstream's procedure decides what crosses: have its minion return the shared material as the package's `content` (only the claim that consumes it receives it, and the factory clears it once every dependent has), and keep `data` to light metadata such as paths and counts, which the Floor shows. When a script must decide what crosses, have the minion only run it and pass its output on, with `data.sha256` (each `content.files` path and the SHA-256 of its text): the factory refuses a package whose files differ. Until the upstream exists and lists this repository, the dependent waits (`no job of this factory shares this package with this repository`), the same answer whether the job is missing or does not share. `proposal` packages only come from a job of this repository: leave out `repository`. Changing `consumers` never makes a job run again.

Every job also has a `proposal` package, without listing it in `output`: the proposals of its runs that a person approved on the Floor. A job that depends on it implements them, usually a `write_in_scope` job whose procedure says to make the change the proposal describes and meet its acceptance criteria:

```toml
[[dependencies]]
job_id = "backend-audit"
package = "proposal"
```

To have one job apply every job's proposals, without listing each, write `job_id = "*"`: it takes those of every job in the repository that no other job takes, jobs added later included, except its own and those of jobs downstream of it. One job per repository may have it.

Each approval reaches one dependent's next successful run, once: the first job to take it, even when two depend on the same job's proposals or the one that took it is later removed, whatever happens to the upstream since; proposals still awaiting a decision hold it (`waiting for package: backend-audit/proposal (1 awaiting approval)`). A dependent that also runs on a schedule (`every` or `cron`) or on other packages is never held by proposals: it runs as those say, and each run takes the approvals there are, so a backlog job (labelled tracker tickets every 30 minutes, say) can also implement the proposals approved on the Floor; its procedure then says to do an approved proposal first. Without such a job, approving only records the decision.

## Procedure format: `.nightshift/procedures/<name>.md`

Write it for a worker who has never seen the repository. Keep these rules, which every Night Shift procedure follows:

```markdown
You are the **notes-gardener**. This is a read-only audit of the `scope` directory given in your assignment.

## Rules

- Do not modify, create or delete anything. Do not create issues, pull requests, commits or any external write. A fix is a proposal awaiting human approval.
- Every claim needs a `file:line` reference you actually read. No reference, no claim.

## Steps

1. Read the files in `scope`. <what to look for, concretely>
2. Pick the findings worth a human's time. Prefer clear evidence over impressive claims.
3. Write the report with `## Finding`, `## Evidence`, `## Proposed finite task` (title, 2-4 testable acceptance criteria, marked **Proposal, awaiting approval**) and `## Review`, where you re-read each reference and confirm or downgrade the claim.
4. Outcome: `completed` when the report is written and the review passed; `no_op` when nothing needs review (say what you checked); `failed` when you could not finish (say why).
```

A procedure for a job that writes replaces the audit rules and steps with:

```markdown
You are the **docs-writer**. You may edit files inside the `scope` directory given in your assignment, and nowhere else.

## Rules

- Edit only inside `scope`. Read anything you need elsewhere, but never edit it. Never run git, commit, push or create issues; the factory session delivers your edits as a pull request.
- Every change needs a reason you can cite with `file:line` from the source of truth (for docs, the code). No reference, no change.
- Keep changes minimal and in the existing style.

## Steps

1. Read `scope` and the paths it describes. <what must stay true, concretely>
2. Fix what is wrong or missing, inside `scope` only.
3. Write the report with `## Changes` (each file changed, with the `file:line` that justifies it) and `## Review`, where you re-read each change against its reference.
4. Outcome: `completed` when you changed files and the review passed; `no_op` when nothing needed changing (say what you checked); `failed` when you could not finish (say why).
```

A procedure may rely on what the factory allows every minion: reading and searching the whole repository, running the commands it names from the directory it names (a bootstrap from the repository root, checks from a package directory) even outside `scope`, the network, and the external writes it asks for, such as the tracker issue, an API call or a message. Restrict any of these per job, as in "Restricting a minion" below. Those commands may change nothing outside `scope` except caches and dependency or build directories the repository already ignores, and edits stay inside `scope`. Write each command on its own, without `&&`, `;`, `|` or `$(...)`, since the minion runs one command per call. A procedure cannot have the minion push, merge, open or comment on a pull request, install packages beyond the repository's bootstrap, change env files, or run git beyond `git status --short`.

## Restricting a minion

Everything above is allowed by default. When the user wants a limit (step 5), use the narrowest lever that holds:

| To keep the minion from | Use |
|---|---|
| editing files | `source_access = "read_only"` (with `external_writes = "forbidden"`); the factory session checks a reader edited nothing, and a writer only inside `scope` |
| having its pull request merged without a person (the minion and the session never merge; the factory does with `merge = "auto"`) | leave out `merge = "auto"` (the default is `manual`) |
| creating the tracker issue | `task_creation = "human_approval_required"`: it returns the issue as a proposal |
| returning proposals, so its pull request is the only thing to review | `proposals = "forbidden"`, with `task_creation` and `network` allowed: its follow-ups become tracker issues |
| any network beyond the repository's bootstrap and checks | `network = "forbidden"`; the tracker issue then becomes a proposal too |
| one action in particular (posting to Slack, a write API, a command, a folder it should not read) | a rule in the job's procedure, such as "Do not post messages; report them instead." |
| running commands, fetching web pages or calling an MCP tool, for every job of a role | Claude Code: leave `Bash`, `WebFetch`/`WebSearch` or that MCP tool out of the minion's `tools`. With `Bash` kept, the minion can still reach the network through commands (`curl`), so only leaving out `Bash` keeps a role off the network |

A minion asks no questions by default: it decides each open point itself and makes the change it decided, or returns it as a proposal or tracker issue as its permissions allow. To let a job leave questions for a person, say so in its procedure, such as "List what needs a person's decision."

`[permissions]` and procedure rules are instructions the minion follows. Claude Code enforces a minion's `tools`, so use them when a limit must hold even if the minion misreads; a Codex agent file cannot change the session's sandbox or MCP servers, so set `agent = "claude"` on such a job. Keep jobs with different limits in different roles, since a role's minion has one set of tools.

## Minion formats

Claude Code, `.claude/agents/<role>.md`:

```markdown
---
name: notes-gardener
description: Night Shift minion for the notes-gardener station. Runs one assigned read-only Night Shift job and returns its report. Use when the factory hands out a notes-gardener assignment.
tools: Read, Grep, Glob
---

You are the notes-gardener minion of the Night Shift floor. You receive one assignment: a task, a scope_path relative to the repository root, permissions and instructions. Follow the instructions exactly. You only read: never edit, create or delete files, and make no external write your instructions do not ask for, and never push, merge, open or comment on a pull request. Return the report Markdown, an outcome (completed, no_op or failed), a one-line factual summary and, only for completed, an optional proposal with title, evidence and acceptance_criteria.
```

Codex, `.codex/agents/<role>.toml`:

```toml
name = "notes-gardener"
description = "Night Shift minion for the notes-gardener station. Runs one assigned read-only Night Shift job and returns its report."
sandbox_mode = "read-only"
developer_instructions = """
You are the notes-gardener minion of the Night Shift floor. You receive one assignment: a task, a scope_path relative to the repository root, permissions and instructions. Follow the instructions exactly. You only read: never edit, create or delete files, and make no external write your instructions do not ask for, and never push, merge, open or comment on a pull request. Return the report Markdown, an outcome (completed, no_op or failed), a one-line factual summary and, only for completed, an optional proposal with title, evidence and acceptance_criteria.
"""
```

For a role whose jobs write, the minion may also edit. Claude Code: `tools: Read, Grep, Glob, Edit, Write`. Codex: `sandbox_mode = "workspace-write"`. When the role's procedures run commands, add `Bash` to the Claude Code tools. Its instructions say it may edit files only inside scope_path, never runs git beyond `git status --short`, and lists each change with its justifying `file:line` in the report.

When a role's procedures call MCP tools, list each one in the Claude Code `tools` under every name a session may give it, since the name depends on how the session reaches the server: `mcp__claude_ai_<connector>__<tool>` through a claude.ai connector (its name with spaces as underscores, as in `mcp__claude_ai_Claap__get_recording`), and `mcp__<server>__<tool>` through `.mcp.json` or `claude mcp add` (`mcp__Claap__get_recording`). A name the session does not have is dropped without an error, so a minion listing only the other name starts without the tool and fails its job. `mcp__<server>__*` gives a role a whole server, again once per name. Claude Desktop's local sessions name a claude.ai connector by its connection id instead (`mcp__<uuid>__<tool>`), which no committed file can list for every user: there, a role gets that service only through a `.mcp.json` server, or with no `tools` line, which gives the minion every tool of the session.

Never add a model to a minion file: the factory starts the minion on its job's `model`, whatever the file says. When the user asks for a model, set the job's `model` (per agent for an exact model id).
