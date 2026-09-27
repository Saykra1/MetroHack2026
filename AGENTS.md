# Agent roles & protocol

## Roles
| Role | Job | Output |
|---|---|---|
| **Orchestrator** (main session) | Strategy, task split, merges results, keeps logs | LOG.md, DECISIONS.md |
| **Researcher** | Prior art: similar competitions/hackathons, winning solutions, SOTA models, datasets, libs | `research/*.md` with links |
| **Deep Researcher** | Multi-source deep dive on one hard question (on demand) | `research/deep_*.md` |
| **Data Analyst** | EDA, distributions, leaks, train/test shift, target quirks, metric exploitation | `INSIGHTS.md`, `experiments/eda/` |
| **Builders (N)** | Implement pipelines / features / models / product parts in parallel (isolated worktrees when risky) | `src/`, `experiments/<id>/` |
| **Debaters (2–3)** | Argue opposing strategies (e.g. safe baseline vs risky moonshot; ML vs LLM; product vs score) | positions → Judge |
| **Judge** | Scores options vs judging criteria & metric, checks CV validity, flags overfit/leaks/weak pitch | verdict in DECISIONS.md |
| **Red Team** | Tries to break the solution: edge cases, what jury will ask, demo failure modes | risks in INSIGHTS.md |
| **Pitch** | Story, slides, demo script, Q&A prep | `pitch/` |

## Protocol
1. Task arrives → Orchestrator fills TASK.md, lists ambiguities.
2. In parallel: Researcher (prior art) + Data Analyst (EDA).
3. Debaters propose 2–3 strategies → Judge picks, logs in DECISIONS.md.
4. Baseline first (fast, submitted early) → then iterate; every run into LEADERBOARD.md.
5. Keep one risky branch alive in parallel with the safe branch.
6. Red Team + Judge review before final submit; Pitch starts at ~60% of time.

## Principles
- Solution code/docs in English; summaries to user in Russian.
- Spawn agents only where parallelism pays; no duplicate work.
- Validate locally before spending submissions; mirror public LB with CV.
- Log conclusions, not noise.
