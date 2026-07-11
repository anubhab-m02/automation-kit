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
A scheduled workflow picks the single oldest open `daily-task` issue,
implements only that issue inside a bounded turn/tool budget, and opens a
PR. If the backlog is empty, it exits immediately — no tokens spent.

Guardrails baked into [`daily-agent.yml`](.github/workflows/daily-agent.yml):

- **Skip-if-empty** — no open `daily-task` issues, no run.
- **PR-only, never auto-merge** — every run's output is reviewed by a human
  before it lands on the default branch.
- **Bounded scope** — one issue per run, capped agent turns, restricted
  tool list, explicit "don't refactor unrelated code" instruction.
- **Escalation path** — genuine ambiguity or missing input stops the agent;
  it opens a draft PR or issue comment explaining what decision is needed
  and labels the issue `needs-input`, instead of guessing.
- **Bounded backlog growth** — at most one agent-proposed follow-up issue
  per run, labeled `needs-triage`, never auto-promoted to `daily-task`.
- **Real commit identity** — git identity is configured to the repository
  owner before the agent runs, and the agent is instructed not to add any
  AI/bot attribution to commits or PRs. Commit *count* per day varies
  naturally with how many logical steps the day's issue(s) actually need —
  it is never an arbitrary number picked to look a certain way.

## Onboarding a new repo

1. Add a `ROADMAP.md` to the target repo (direction, priorities, current
   architecture) and a `CLAUDE.md` if useful for conventions.
2. Copy the issue templates from `.github/ISSUE_TEMPLATE/` into the target
   repo (or reference this repo's during an ideation session).
3. File a handful of `daily-task` issues, each scoped to one PR's worth of
   work.
4. Add a thin caller workflow to the target repo, e.g.
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
   ```

5. Generate an OAuth token from your Claude Pro/Max subscription (not a
   metered API key) by running `claude setup-token` locally, then add it
   as a `CLAUDE_CODE_OAUTH_TOKEN` secret on the target repo (Settings →
   Secrets and variables → Actions). Usage draws from the subscription,
   not pay-per-token billing.
6. Test with a manual `workflow_dispatch` run before trusting the cron.

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
