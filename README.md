# automation-kit

A reusable GitHub Actions workflow that lets a repo make small, real,
unattended daily progress against a human-curated backlog — without an
open-ended agent guessing what's "meaningful" from scratch every day.

## Design

Two separate loops, kept deliberately apart:

**Loop 1 — ideation (human, interactive, whenever you're available).**
You (with or without Claude Code) decide direction, keep each repo's
`ROADMAP.md` current, and turn that direction into small, fully-scoped
`daily-task` issues. This is the expensive, judgment-heavy part, and it's
paid for once per issue, not once per day.

**Loop 2 — execution (unattended, daily, cheap).**
A scheduled workflow accumulates work on a single long-lived `agent/rolling`
branch: each run attempts 1–3 eligible `daily-task` issues inside a bounded
turn/tool budget, commits each separately, and opens or updates one rolling
PR to the default branch. If the backlog is empty, it exits immediately —
no tokens spent. Work never depends on you merging anything — day N+1
builds directly on day N's unmerged commits on the same branch, so an
unattended multi-day stretch just keeps accumulating onto that one PR.

Guardrails baked into [`daily-agent.yml`](.github/workflows/daily-agent.yml):

- **Skip-if-empty** — no eligible `daily-task` issues, no run.
- **PR-only, never auto-merge** — every run's output lands on the rolling
  PR, reviewed by a human before it lands on the default branch. Merging
  that PR closes every issue it lists via `Closes #n`.
- **Bounded scope** — up to `max_issues` (default 3) issues per run, capped
  agent turns, restricted tool list, explicit "don't refactor unrelated
  code" instruction, and each issue is expected to be small (~150 lines)
  by convention, not enforced by the workflow itself — see the target
  repo's `ROADMAP.md` for the sizing rules.
- **Issue picking order** — eligible = open + `daily-task`, minus `in-pr`,
  minus `needs-input`; `priority`-labeled issues go first, then lowest
  issue number. File a `priority` + `daily-task` issue to get a fix or
  review note picked up before the backlog's regular order.
- **Escalation path** — a genuinely ambiguous or blocked issue gets a
  comment explaining what's needed and the `needs-input` label, and the
  agent moves on to the next candidate instead of guessing or stalling the
  whole run.
- **Bounded backlog growth** — at most one agent-proposed follow-up issue
  per run, labeled `needs-triage`, never auto-promoted to `daily-task`.
- **Real commit identity** — git identity is configured to the repository
  owner before the agent runs, `bot_name`/`bot_id` are overridden to the
  repo owner (the action defaults to a `claude[bot]` identity otherwise),
  and an optional `GH_PAT` (owner-scoped fine-grained token) makes PRs,
  comments, and labels themselves show the owner instead of the Claude
  GitHub App. Commit *count* per day varies naturally with how many
  logical steps the completed issues actually need — it is never an
  arbitrary number picked to look a certain way.

## Onboarding a new repo

1. Add a `ROADMAP.md` (direction, priorities, delivery model), and ideally
   `ARCHITECTURE.md`/`SYSTEM-DESIGN.md`/`UI-DESIGN.md` docs, plus a
   `CLAUDE.md` for conventions.
2. Copy the issue templates from `.github/ISSUE_TEMPLATE/` into the target
   repo (or reference this repo's during an ideation session).
3. Create the labels this workflow relies on:
   `gh label create daily-task && gh label create priority && gh label create in-pr && gh label create needs-input && gh label create needs-triage`
4. File a backlog of `daily-task` issues in dependency order, each scoped
   to roughly one PR's worth of work (~150 lines), with exact files and
   acceptance criteria a test suite can check.
5. Add a thin caller workflow to the target repo, e.g.
   `.github/workflows/daily-agent.yml`:

   ```yaml
   name: Daily Agent
   on:
     schedule:
       - cron: "0 4 * * *"   # runs daily; the reusable workflow no-ops if the backlog is empty
     workflow_dispatch: {}    # allows a manual test run

   jobs:
     run:
       uses: anubhab-m02/automation-kit/.github/workflows/daily-agent.yml@main
       secrets:
         CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
         GH_PAT: ${{ secrets.GH_PAT }}
   ```

6. Generate an OAuth token from your Claude Pro/Max subscription (not a
   metered API key) by running `claude setup-token` locally, then add it
   as a `CLAUDE_CODE_OAUTH_TOKEN` secret on the target repo (Settings →
   Secrets and variables → Actions). Usage draws from the subscription,
   not pay-per-token billing.
7. Optional but recommended: create a fine-grained PAT owned by you,
   scoped to just this repo with Contents/Pull requests/Issues read-write,
   and add it as a `GH_PAT` secret — without it, PRs/comments/labels are
   authored by the Claude GitHub App identity even though commits
   themselves are attributed to you.
8. Test with a manual `workflow_dispatch` run before trusting the cron.

This repo is public specifically so the `uses:` reference above resolves
without any cross-repo access configuration — private reusable workflows
don't reliably resolve across repos owned by a personal (non-organization)
GitHub account, even with the "Access" setting configured correctly, so
public is the simpler and more robust choice here. Nothing in this repo is
sensitive (no secrets, no proprietary logic — just workflow design and a
prompt).

## Auth: subscription OAuth token, not API billing

This kit authenticates via a Claude Pro/Max subscription OAuth token
(`claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` secret), not a metered
`anthropic_api_key`. Two things worth knowing:

- The token is tied to your personal subscription's usage allowance, which
  is designed around interactive use. Running this daily against several
  repos shares that same allowance — if you hit subscription rate limits,
  a run will fail rather than bill overage; check `gh run list` if a
  scheduled run goes missing.
- A couple of action features (e.g. inline PR-comment classification) are
  documented as API-key-only and are skipped under OAuth token auth — not
  used by this kit's daily-task flow, so no impact here.

## Model tiering

Default model is whatever the subscription/action defaults to. For issues
that need stronger reasoning, add a `model:opus` label convention in the
target repo and extend the caller workflow to branch `claude_args`
accordingly — not implemented by default to keep the base case simple.
