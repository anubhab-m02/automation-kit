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
         ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
   ```

5. Add an `ANTHROPIC_API_KEY` secret to the target repo (Settings →
   Secrets and variables → Actions).
6. Because this repo (`automation-kit`) is private, the target repo needs
   explicit access to call its reusable workflow: in **this** repo, go to
   Settings → Actions → General → Access, and allow the target repo (or
   "repositories owned by this account"). Without this the caller workflow
   fails with a permissions error on the `uses:` step.
7. Test with a manual `workflow_dispatch` run before trusting the cron.

## Model/cost tiering

Default model is whatever `claude_args`/the action defaults to (cheapest
suitable tier). For issues that need stronger reasoning, add a
`model:opus` label convention in the target repo and extend the caller
workflow to branch `claude_args` accordingly — not implemented by default
to keep the base case cheap.
