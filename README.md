# automation-kit

A reusable GitHub Actions workflow that lets a repo make small, real,
unattended daily progress against a human-curated backlog — without an
open-ended agent guessing what's "meaningful" from scratch every day.

## Design

Four unattended automations, each modeled on a role a small engineering
org already has, running in sequence across the day so no two ever
compete for the same Claude subscription usage window. Full design
rationale: a target repo's own
`docs/superpowers/specs/*automation-org-design.md`, if it has one —
this file covers the mechanics, that one covers the reasoning.

- **Coder** (dev) — [`daily-agent.yml`](.github/workflows/daily-agent.yml).
  Picks up to `max_issues` eligible `daily-task` issues, one independent
  branch and PR per issue (not a shared rolling branch — a flagged issue
  blocks only itself). Runs nightly for new issues, and again — via a
  `resolve-comments` mode triggered by the Reviewer's own completion,
  never on its own schedule — to push fixes to PRs with requested
  changes.
- **Reviewer** (QA) — [`reviewer.yml`](.github/workflows/reviewer.yml).
  Reviews every currently open PR in a hard-isolated fresh context per
  PR (a separate job invocation each time — no shared memory with the
  Coder run that produced it, or with any other PR's review). Submits a
  real GitHub review (`Approve`/`Request changes`), attempts an
  auto-merge using the workflow's own non-admin token (not the owner's
  `GH_PAT` — see "Two credential tiers" below), and writes a dated
  report to `docs/superpowers/reports/`.
- **Brainstormer** (PM) — [`brainstormer.yml`](.github/workflows/brainstormer.yml).
  Reads the latest report, any open `steering`-labeled issue (checked
  first, treated as binding), open `needs-input` issues, and the repo's
  Dependabot alerts; updates `ROADMAP.md` directly — no PR, no approval
  gate on its own edits — and sends the day's one notification by
  commenting on and assigning the human to a persistent tracking issue.
- **Issue Generator** (scrum master) — [`issue-generator.yml`](.github/workflows/issue-generator.yml).
  Reads `ROADMAP.md` as the Brainstormer left it and the latest report
  (parsed deterministically via [`scripts/parse_review_report.py`](scripts/parse_review_report.py),
  not re-judged from prose); files new, dedup-checked issues; sets
  `priority` from the report's own stated severity.

**The merge gate** (all three required — an AND): required status
checks pass, no touched file matches the sensitive-path denylist (the
Reviewer's own judgment call, checked before anything else in its
prompt), and the Reviewer's isolated review approves. Enforced by real
GitHub branch protection on the target repo, not just these workflows'
own instructions.

**Two credential tiers**, used deliberately: the admin-scoped `GH_PAT`
is used only by the Brainstormer (writes `ROADMAP.md`) and the
Reviewer's report-writing step (writes `docs/superpowers/reports/`) —
both of which only ever touch documentation paths, never application
code, which is what makes an admin-level bypass of branch protection
safe for them specifically. The Coder's actual `gh pr merge` call uses
the workflow-scoped default `GITHUB_TOKEN` instead, which has no admin
rights — so branch protection is genuinely enforced there, rather than
silently bypassed by an over-privileged merge actor.

Guardrails carried over from the original single-automation design,
still true of the Coder:

- **Skip-if-empty** — no eligible `daily-task` issues, no run.
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
  comment explaining what's needed and the `needs-input` label; the
  Coder moves on to the next candidate. It never notifies the human
  directly — only the Brainstormer does that, once a day.
- **Bounded backlog growth** — the Coder may open at most one
  agent-proposed follow-up issue per run, labeled `needs-triage`, never
  auto-promoted to `daily-task`; the Issue Generator caps itself at 10
  new issues per run.
- **Real commit identity** — git identity is configured to the repository
  owner before any automation runs, `bot_name`/`bot_id` are overridden to
  the repo owner (the action defaults to a `claude[bot]` identity
  otherwise), and an optional `GH_PAT` (owner-scoped fine-grained token)
  makes PRs, comments, and labels themselves show the owner instead of
  the Claude GitHub App.

## Onboarding a new repo

1. Add a `ROADMAP.md` (direction, priorities, delivery model), and ideally
   `ARCHITECTURE.md`/`SYSTEM-DESIGN.md`/`UI-DESIGN.md` docs, plus a
   `CLAUDE.md` for conventions.
2. Copy the issue templates from `.github/ISSUE_TEMPLATE/` into the target
   repo (or reference this repo's during an ideation session).
3. Create the labels this workflow relies on:
   `gh label create daily-task && gh label create priority && gh label create in-pr && gh label create needs-input && gh label create needs-triage && gh label create steering`
4. File a backlog of `daily-task` issues in dependency order, each scoped
   to roughly one PR's worth of work (~150 lines), with exact files and
   acceptance criteria a test suite can check.
5. Add thin caller workflows to the target repo — one per automation, each
   with its own schedule spaced so no two compete for the same Claude
   subscription usage window (a rolling five hours; every stage below sits
   a full hour past the previous one's window before the next opens):

   ```yaml
   # .github/workflows/daily-agent.yml — the Coder
   name: Daily Agent
   on:
     schedule:
       - cron: "30 18 * * *"  # e.g. 00:00 IST
     repository_dispatch:
       types: [resolve-review-comments]
     workflow_dispatch: {}

   jobs:
     new-issues:
       if: github.event_name != 'repository_dispatch'
       uses: anubhab-m02/automation-kit/.github/workflows/daily-agent.yml@main
       with:
         mode: new-issues
       secrets:
         CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
         GH_PAT: ${{ secrets.GH_PAT }}
     resolve-comments:
       if: github.event_name == 'repository_dispatch'
       uses: anubhab-m02/automation-kit/.github/workflows/daily-agent.yml@main
       with:
         mode: resolve-comments
       secrets:
         CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
         GH_PAT: ${{ secrets.GH_PAT }}
   ```

   ```yaml
   # .github/workflows/reviewer.yml — the QA pass, ~6 hours after the Coder
   name: Reviewer
   on:
     schedule:
       - cron: "30 0 * * *"  # e.g. 06:00 IST
     workflow_dispatch: {}
   jobs:
     run:
       uses: anubhab-m02/automation-kit/.github/workflows/reviewer.yml@main
       secrets:
         CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
         GH_PAT: ${{ secrets.GH_PAT }}
   ```

   ```yaml
   # .github/workflows/brainstormer.yml — the PM, ~6 hours after the Reviewer
   name: Brainstormer
   on:
     schedule:
       - cron: "30 6 * * *"  # e.g. 12:00 IST
     workflow_dispatch: {}
   jobs:
     run:
       uses: anubhab-m02/automation-kit/.github/workflows/brainstormer.yml@main
       secrets:
         CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
         GH_PAT: ${{ secrets.GH_PAT }}
   ```

   ```yaml
   # .github/workflows/issue-generator.yml — the scrum master, ~6 hours after the Brainstormer
   name: Issue Generator
   on:
     schedule:
       - cron: "30 12 * * *"  # e.g. 18:00 IST
     workflow_dispatch: {}
   jobs:
     run:
       uses: anubhab-m02/automation-kit/.github/workflows/issue-generator.yml@main
       secrets:
         CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
         GH_PAT: ${{ secrets.GH_PAT }}
   ```

6. Generate an OAuth token from your Claude Pro/Max subscription (not a
   metered API key) by running `claude setup-token` locally, then add it
   as a `CLAUDE_CODE_OAUTH_TOKEN` secret on the target repo (Settings →
   Secrets and variables → Actions). Usage draws from the subscription,
   not pay-per-token billing.
7. Create a fine-grained PAT owned by you, scoped to just this repo, with
   `Contents`/`Pull requests`/`Issues` read-write **and `Administration`
   read-write** (the Brainstormer and Reviewer need this to push
   documentation-path commits directly under the two-credential model
   above), and add it as a `GH_PAT` secret. This is no longer optional
   the way it was for the single-automation design — the Brainstormer and
   Reviewer's docs-only pushes require it.
8. Configure branch protection on the target repo's default branch:
   required status checks (once the repo has CI) and a required approving
   review, with **"Include administrators" left off** — this is what
   lets the admin-scoped `GH_PAT` (and you, the repo owner) bypass, while
   the Coder's merge step — which deliberately uses the workflow-scoped
   default token, not `GH_PAT` — stays genuinely gated.
9. Seed `docs/superpowers/reports/TEMPLATE.md` in the target repo (see
   this repo's own copy for the exact shape) so the Reviewer and Issue
   Generator agree on the report format from day one.
10. Test each workflow with a manual `workflow_dispatch` run — in this
    order, since each later one reads output the earlier ones produce —
    before trusting any cron: Coder, Reviewer, Brainstormer, Issue
    Generator.

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
