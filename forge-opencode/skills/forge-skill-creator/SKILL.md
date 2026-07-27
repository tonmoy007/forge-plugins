---
name: skill-creator
description: Author a tested, installable Forge skill from a mined candidate proposal. Use
  whenever the user runs /forge:skill-creator, wants to turn a mined skill proposal into a
  real skill, says "author this skill", "write a skill from the proposal", "promote a mined
  candidate", "refine a proposed skill", or asks to test/optimize a skill's triggering
  description. Consumes a .forge/proposed-skills/<slug>/SKILL.md draft and runs the
  capture→write→test→grade→improve→optimize-description loop in-session, extending (never
  replacing) the /forge:skill-approval flow. Nothing installs without explicit user approval.
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob]
---

# /forge:skill-creator — author a tested skill from a mined candidate

This skill takes a mined **candidate proposal** and authors it into a real, tested
`SKILL.md` through the Anthropic skill-creator loop. It runs **in-session** because the
authoring agent cannot be spawned by a hook or script (ADR-006: skills drive in-session
work; scripts cannot drive the Agent tool). It **extends** the approval flow — it does not
replace it, and **nothing installs without explicit user approval** (REQ-NF-019).

## When to Use

- User runs `/forge:skill-creator [<slug>]`.
- A mining run (`skill_miner_v2.py`) has written one or more
  `.forge/proposed-skills/<slug>/SKILL.md` drafts and the user wants to promote one into a
  real, tested skill.
- User wants to refine, test, or optimize the triggering description of a proposed skill.

## Inputs

- `$ARGUMENTS` — optionally the proposal `<slug>` to author. If omitted, list the pending
  proposals first and ask the user which one to author.

## Pre-flight

1. List the pending mined proposals so the user can pick one:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/skill-approval.py list --cwd .
   ```

2. Read the chosen draft at `.forge/proposed-skills/<slug>/SKILL.md`. It already contains
   a non-empty third-person `description`, a `Procedure`, and `Provenance` with
   source-trace-line citations — this is your starting material, never a blank page.

## The skill-creator loop (run in-session)

Do these in order. This is the Anthropic author→test→grade→improve→optimize loop, adapted
to a mined candidate.

1. **Capture intent.** From the proposal's Procedure + Provenance citations, restate in one
   sentence *what* this skill does and *when* it should fire. If the intent is ambiguous,
   ask the user one clarifying question — do not guess.

2. **Write the SKILL.md.** Edit `.forge/proposed-skills/<slug>/SKILL.md` in place:
   - Tighten the `description` to be third-person, state **what + when**, and be
     deliberately discoverable (pushy) — this is the retrieval key Claude matches on.
   - Make the `Procedure` clear imperative steps that reference the parameters.
   - Keep the `Provenance` citations intact (they justify the generalization).

3. **Test against a baseline.** Replay the procedure against one of the source episodes the
   candidate was induced from. For coding skills, the oracle is the test suite: the
   procedure must reproduce **red→green**. If no runnable oracle exists, do a critic read:
   does each step follow from the cited evidence?

4. **Grade.** Score the draft on: does it reproduce the successful outcome? Are the steps
   unambiguous? Is the description specific enough to trigger on the right requests and no
   others? Note concrete weaknesses.

5. **Improve.** Apply the fixes from the grade — sharpen steps, add a guard/pitfall, fix a
   parameter name. Re-test (step 3) until the baseline passes.

6. **Optimize the description (should-/should-not-trigger test).** Write 3 *should-trigger*
   user requests and 3 *should-not-trigger* requests. Read only the `description` and judge,
   for each, whether the skill would fire. Revise the description until every should fires
   and every should-not does not. Record the test set in the body for traceability.

## Approval (extends, never replaces, skill-approval)

Authoring **does not install** the skill. Once the loop passes, hand back to the existing
approval flow — the user decides:

```bash
# install the authored proposal into the plugin's skills/ dir
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/skill-approval.py approve --slug <slug> --cwd .

# or reject it — blacklists the motif signature so it is not re-proposed
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/skill-approval.py reject --slug <slug> --cwd .
```

State clearly to the user that **nothing is installed until they run `approve`**.

## Verification

Before telling the user the skill is ready to approve:

- The authored `.forge/proposed-skills/<slug>/SKILL.md` has valid frontmatter
  (`name`, non-empty `description`, `status: proposed`).
- The replay/baseline test passed (red→green, or critic check documented).
- The should-/should-not-trigger set passes (every should fires, every should-not does not).
- You have **not** installed anything — the install only happens on explicit
  `skill-approval.py approve`.

## Notes

- No `.forge/proposed-skills/` directory ⇒ nothing to author; tell the user to run mining
  first. This skill is a clean no-op in that case.
- Human-in-the-loop throughout: you author and test, the user approves. See
  `references/skill-format.md` for the SKILL.md format and description best-practices.
