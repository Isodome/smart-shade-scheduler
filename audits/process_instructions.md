# AI Pair Programming Review & Implementation Process

This document outlines the collaborative, multi-agent process used to audit and improve this codebase.

## Directory Structure
- All audit reports and consolidated task lists must be saved in a date-specific directory: `audits/<YYYY-MM-DD>/`.
- Process instructions (like this document) should be stored in the root of the `audits/` directory.


## Phase 1: Multi-Agent Audit & Convergence
1. **Independent Audits:** Multiple AI models independently review the target codebase and produce separate architectural audit reports. The agents name must be part of the file name.
2. **Cross-Review:** Each model reads all other models' audit reports.
3. **Report Amendment:** Each model amends its original report, incorporating valid findings from its peers and explicitly documenting any disputed findings in a separate section. THis amendment goes into a separate file.
4. **Task Consolidation:** The findings from all amended reports are merged into a unified Markdown `todo.md` list (saved in `audits/<YYYY-MM-DD>/todo.md`). The items should be categorized by consensus (e.g., "All Agree", "Only Model A", "Model A & B Agree").
5. **Human Triage:** The human developer reviews the consolidated `todo.md` list and explicitly annotates which items should be worked on.

## Phase 2: Iterative Implementation
For each human-annotated task in the `todo.md` list, the following execution loop is used:

1. **Implementation:** One designated model takes an annotated work item and implements the code fix.
2. **Peer Review:** Before committing the changes, the implementing model presents its code to one or more peer models. When asking for the review, the prompt MUST point to the original audit report where the finding is described and explicitly ask whether the issue is properly addressed.
3. **Incorporate Feedback:** The implementing model incorporates the peer review feedback and refines the code.
4. **Resolve Disputes:** If the models disagree on the implementation details or feedback, the implementing model pauses and asks the human to make the final architectural decision.
5. **Commit & Track:** Once consensus (or a human override) is reached, the implementing model performs a git commit for the fix and marks the corresponding item as "Done" (`[x]`) in the `todo.md` list.


## Useful code review snippets
```bash
# Gemini
result=$(git diff origin/main...HEAD | gemini -p "Please review these changes. They are meant to address finding [FINDING_NAME] from the audit report in audits/<YYYY-MM-DD>_gemini_audit_report.md. Is the issue properly addressed? Are there any bugs, security issues, or code quality concerns?" --output-format json)
echo "$result" | jq -r '.response' > pr-review-gemini.json

# Claude
result=$(git diff origin/main...HEAD | claude -p "Please review these changes. They are meant to address finding [FINDING_NAME] from the audit report in audits/<YYYY-MM-DD>_claude_audit_report.md. Is the issue properly addressed? Are there any bugs, security issues, or code quality concerns?")
echo "$result" > pr-review-claude.md
```