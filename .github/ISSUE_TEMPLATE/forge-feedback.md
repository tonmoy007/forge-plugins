---
name: Forge feedback / bug report
about: Report a Forge bug, confusing behavior, or rough edge
title: "[feedback] "
labels: feedback
assignees: ''
---

<!--
Before filing: run `/forge:doctor` and paste its top-line status below.
If the error is a PreToolUse/Stop hook that doesn't mention a Forge path, it may
be from another plugin — see docs/getting-feedback.md#troubleshooting-third-party-plugin-hooks
-->

## What happened

<!-- One or two sentences. What did you run, what did Forge do? -->

## What you expected

<!-- What should have happened instead? -->

## Steps to reproduce

1.
2.
3.

## Environment

- Forge version: <!-- from .claude-plugin/plugin.json, e.g. 0.1.5 -->
- Claude Code version: <!-- `claude --version` -->
- OS:
- `/forge:doctor` top-line status: <!-- healthy / wedged / broken -->
- Current stage (`/forge:status`):

## Logs / output

<!--
Paste the relevant output. Helpful sources:
- `/forge:doctor` full report
- `.forge/errors.log` (recent lines)
- the exact error message
Please scrub anything sensitive (paths, tokens, PII).
-->

```
(paste here)
```

## Severity

- [ ] Blocks me from using Forge
- [ ] Confusing / rough edge but I worked around it
- [ ] Minor / cosmetic
