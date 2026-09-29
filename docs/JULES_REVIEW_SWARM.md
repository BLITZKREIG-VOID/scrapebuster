# Jules PR review swarm

## Normal flow

The trusted `Jules PR Review` workflow runs on PR open, new commits, reopen, and ready-for-review events. `pull_request_target` lets it review fork PRs. It checks out only the workflow's trusted base revision, fetches PR metadata and patches through GitHub's API, and gives the diff to source-less Jules sessions as untrusted text. It never checks out, builds, tests, or executes PR code. `JULES_API_KEY` is available only to the trusted review script.

The script validates findings against changed lines, deduplicates them, posts inline comments and suggestions, updates a single PR dashboard, resolves stale Jules threads when the reviewed diff proves the issue is gone, and publishes the `jules/review` commit status. A new small commit uses one focused final Jules session, including a small fix in a sensitive path; a materially expanded diff gets the specialized swarm again.

## Review routing

Thresholds and sensitive paths are in `.github/jules-review-config.json`.

| Change size/risk | Jules sessions |
|---|---|
| Small: up to 3 files and 150 changed lines | 1 path-selected reviewer |
| Medium: up to 8 files and 400 lines | 2 path-selected reviewers |
| Large: above medium | 4 parallel reviewers: architecture, security, tests, integration |
| Very large or sensitive path | 4 parallel reviewers; a clean initial pass also gets a final verification session |
| Small fix push after a completed pass | 1 focused final reviewer; broaden to the swarm if scope expands or touches a sensitive path |

The reviewers cover correctness and architecture, security and failure handling, tests and regressions, and integration/contracts. Role prompts receive only relevant changed-file patches where possible. Findings need a concrete explanation, evidence, recommendation, confidence, and an exact changed line to become an inline comment.

## Findings and duplicate control

Only high-confidence serious `BLOCKING` findings fail `jules/review`. `MAJOR`, warnings, style preferences, speculative issues, and lower-confidence reports stay advisory; on a high-risk PR, the check remains pending until its mandatory final Jules review completes. High-confidence `BLOCKING` and evidence-backed `MAJOR` findings are included in a structured coding handoff with the PR number, original source repository/branch/SHA, exact file/line, evidence, and recommendation. The handoff explicitly preserves the original PR and forbids creating a duplicate PR.

Workflow concurrency serializes runs per PR. Before spending sessions, the script skips stale event SHAs and commits already present in the last completed review. Findings are keyed by file and issue, duplicate reviewer evidence is consolidated, old unresolved findings outside the changed scope are carried forward, and bot-owned threads are resolved only when the fresh review no longer reports them.

The project has an Orca local worker runtime, but GitHub Actions has no configured secure route to dispatch into that workstation runtime. The dashboard therefore records a complete same-PR worker handoff but does not claim that a coding worker ran. A worker must fix the original branch, run targeted tests, and push; that push automatically triggers the focused Jules re-review. Do not give an untrusted PR access to a local worker or repository secrets.

## Merge gate and operations

Require the `jules/review` status context for each protected base branch. `success` means there are no unresolved high-confidence blocking findings; `failure` blocks merge; API/session failures publish `error` and fail closed. CI status checks remain independently required by repository rules. Jules never merges a PR.

- Normal operation is automatic; opening or updating a PR starts review.
- To trigger a fresh focused review, push a commit to the same PR branch. Do not open a replacement PR.
- If a run failed before producing a status, inspect Actions logs and retry the PR event with a new commit after correcting the cause.
- Confirm the `JULES_API_KEY` Actions secret exists if Jules session creation fails.
- If inline comments fail but the Jules session succeeds, verify the workflow token has `pull-requests: write` and `issues: write` permissions.
- Keep review rules in the trusted base branch. Never move the privileged job to `pull_request` or check out PR code in this workflow.

## Local verification

Run `python -m unittest discover -s scripts/tests` for deterministic policy and integration-mock tests. The tests do not call Jules or GitHub.
