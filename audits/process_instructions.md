# AI Pair Programming Review & Implementation Process

This document outlines the collaborative, multi-agent process used to audit and improve this codebase.

## Directory Structure
- All audit reports and consolidated task lists must be saved in a date-specific directory: `audits/<YYYY-MM-DD>/`.
- For each implementation task, an audit trail must be maintained in `audits/<YYYY-MM-DD>/tasks/<task_slug>/`.
- Process instructions (like this document) should be stored in the root of the `audits/` directory.


## Phase 1: Multi-Agent Audit & Convergence
1. **Independent Audits:** Multiple AI models independently review the target codebase and produce separate architectural audit reports. The agents name must be part of the file name.
2. **Cross-Review:** Each model reads all other models' audit reports.
3. **Report Amendment:** Each model amends its original report, incorporating valid findings from its peers and explicitly documenting any disputed findings in a separate section. THis amendment goes into a separate file.
4. **Task Consolidation:** The findings from all amended reports are merged into a unified Markdown `todo.md` list (saved in `audits/<YYYY-MM-DD>/todo.md`). The items should be categorized by consensus (e.g., "All Agree", "Only Model A", "Model A & B Agree").
5. **Human Triage:** The human developer reviews the consolidated `todo.md` list and explicitly annotates which items should be worked on.

## Phase 2: Iterative Implementation
For each human-annotated task in the `todo.md` list, the following execution loop is used:

1. **Initialization:** Create a dedicated task directory: `audits/<YYYY-MM-DD>/tasks/<task_slug>/` (where `task_slug` is a short, lowercase-hyphenated name for the task).
2. **Implementation:** One designated model takes an annotated work item and implements the code fix.
3. **Peer Review & Audit Trail:**
   - Save the current `git diff` to `audits/<YYYY-MM-DD>/tasks/<task_slug>/diff.patch`.
   - Present the diff to peer models for review. The prompt MUST point to the original audit report finding, explicitly ask whether it is properly addressed, and **include a link to these [process_instructions.md](file:///home/dominic/dev/shade_scheduler/audits/process_instructions.md)** so the peer model knows the rules of the review.
   - Save each review response to `audits/<YYYY-MM-DD>/tasks/<task_slug>/rev<N>.md` (e.g., `rev1.md`, `rev2.md`).
4. **Incorporate Feedback & Re-Review:** The implementing model incorporates the peer review feedback and refines the code. If any changes are made, update `diff.patch` and perform another peer review round (saving to `rev2.md`, etc.) until consensus is reached.
5. **Resolve Disputes:** If the models disagree on the implementation details or feedback, the implementing model pauses and asks the human to make the final architectural decision.
6. **Commit & Track:** Once consensus (or a human override) is reached, the implementing model performs a git commit for the fix and marks the corresponding item as "Done" (`[x]`) in the `todo.md` list.


## Useful code review snippets
```bash
# 1. Capture diff (shared)
git diff origin/main...HEAD > audits/<YYYY-MM-DD>/tasks/<task_slug>/diff.patch

# 2. Define prompt (shared)
PROMPT="Review this diff. It addresses finding [FINDING_NAME] from audits/<YYYY-MM-DD>/<agent>_audit_report.md. \
Process rules: file:///home/dominic/dev/shade_scheduler/audits/process_instructions.md. \
Is the finding properly addressed? Any bugs, security issues, or code quality concerns?"

# 3. Run review — pick one CLI:

# Gemini
gemini -p "$PROMPT" < audits/<YYYY-MM-DD>/tasks/<task_slug>/diff.patch \
  > audits/<YYYY-MM-DD>/tasks/<task_slug>/rev<N>.md

# Claude
claude -p "$PROMPT" < audits/<YYYY-MM-DD>/tasks/<task_slug>/diff.patch \
  > audits/<YYYY-MM-DD>/tasks/<task_slug>/rev<N>.md
```