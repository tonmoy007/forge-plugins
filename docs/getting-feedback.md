# Getting Feedback on Forge

A guide for soliciting honest feedback from external users — friends,
coworkers, anyone who isn't you. Includes the testing path, where to look
when things break, three reporting modes, and a drop-in message you can
send.

The single biggest risk to Forge at this stage isn't a bug — it's that
nobody outside the author has stress-tested the experience. This document
exists to remove the friction that keeps you from asking.

---

## Why bother with external testing

You wrote Forge. You know where the landmines are. You walk around them
without noticing. A first-time user trips on every one.

External feedback catches:

- UX rough edges you've stopped seeing
- Documentation gaps you've patched mentally
- Mismatches between what the README promises and what the install
  actually does
- Friction that feels acceptable to you but isn't acceptable to a stranger
- Bugs the unit tests don't cover because the test setup matches your
  mental model

Unit tests prove the code works. External users prove the *product* works.

---

## The 30-minute test path

Don't ask people to "try Forge for a week." They won't start. Ask for 30
bounded minutes against a concrete script.

Tell the tester to do exactly this:

1. **Install the plugin**
   ```
   /plugin marketplace add tonmoy007/forge-plugins
   /plugin install forge@forge-plugins
   ```

2. **Open a small real project** they'd normally use Claude Code on.
   A side project, a script, a half-finished idea. Not a hello-world.
   Real code they care about.

3. **Run `/forge:init`** in that project's directory. Note any
   confusion about what just happened.

4. **Run `/forge:srs`** and let Claude walk them through writing
   requirements for whatever they're building. Note any friction —
   "what's a REQ-ID?", "do I really need this?", etc.

5. **Try to advance to Stage 2** by running `/forge:product`. If
   Forge blocks them, that's expected — the point is to see what
   happens at a gate.

6. **Run `/forge:why`** when blocked, to see whether the explanation
   helps.

7. **Optionally run `/forge:force-advance --reason '<why>'`** to see
   the override flow.

8. **At the end, run `/forge:uninstall`** to clean up.

This gives the tester a bounded experience with a clear endpoint. They
know they're not signing up for an indefinite commitment.

---

## Set expectations upfront (this part matters)

Forge is overhead. It's the *kind* of overhead that some engineers want
and others don't. If you don't tell the tester this upfront, they'll
think Forge is "slow" or "in the way" instead of "deliberate."

Tell them, in plain words:

> Forge adds steps. Claude Code normally just does what you ask. With
> Forge installed, Claude will sometimes pause to update pipeline files,
> run gate checks, or ask you for context before continuing. That's
> intentional. It's trying to keep your project auditable. If it feels
> heavy, that's part of what you're evaluating. Tell me where it felt
> heavy.

This pre-framing matters because it tells the tester their job is to
report friction, not to be a polite guest.

---

## Where to look when something breaks

Forge v0.1.3 has three diagnostic surfaces. Tell the tester about all
three so they know where to point if something goes wrong:

### `/forge:doctor`

First stop for anything that feels wrong. Runs 13 deterministic checks
across environment, plugin, project, and global state. Each failing
check includes a literal fix command.

> Hooks not firing? Stage didn't advance? Claude Code behaving oddly
> after install? Run `/forge:doctor` and paste me the output.

### `.forge/hook-errors.log`

Forge wraps every hook with a crash-safe runner that exits 0 silently
even on internal errors — so the user's session never breaks. The
tradeoff is that hook failures are invisible unless you check the log.

> If something feels broken but `/forge:doctor` says everything's green,
> run `cat .forge/hook-errors.log` and send me whatever's in there.

### `/forge:why`

Not an error path, but it's where confusion gets surfaced. Use it for
"I don't understand why this gate is blocking me" or "what does this
criterion mean."

> Gate blocked you and the message is confusing? Try
> `/forge:why <gate-id>` (e.g. `/forge:why G1-002`). If the explanation
> still doesn't make sense, that itself is feedback I want to hear.

---

## How they should report back

Three reporting modes, in increasing effort. Don't ask for all three.
Pick the one that matches how willing they are to engage.

### Mode 1: copy-paste log (default)

Lowest effort, highest signal. Ask them to keep a single file open
during the session — call it `forge-feedback.md` or whatever — and
paste anything that surprised them. One line per surprise. No format
required.

Show them an example so they see what's wanted:

```
- Stage 1 gate failed on G1-002 but I don't know what NFR means. Frustrated.
- /forge:why G1-002 was helpful — closed the gap in ~30s.
- Got confused when /forge:srs asked about "acceptance criteria" — felt like work.
- /forge:status was the most useful command I used.
- Wasn't sure if I should commit pipeline/ or not. Eventually did.
```

That's already more valuable than 90% of formal bug reports. The mix of
emotional reactions ("frustrated," "felt like work"), command-level
observations, and conceptual gaps is exactly what you can't get from
unit tests.

### Mode 2: GitHub issues (for users who want to file them)

Provide a template at `.github/ISSUE_TEMPLATE/forge-feedback.md`:

```markdown
**What I was trying to do:**

**What Forge did:**

**What I expected instead:**

**Output of `/forge:doctor`:**

```
(paste)
```

**Hook errors (`cat .forge/hook-errors.log`):**

```
(paste, or "empty" if no log)
```

**Severity in my honest opinion:**
- [ ] Bug — Forge is broken
- [ ] Friction — Forge works but it was annoying
- [ ] Confusion — I didn't understand what Forge wanted
- [ ] Suggestion — Idea for improvement
```

Don't push this on casual testers. It's too much friction for a
30-minute session. Save it for users who *want* to file issues.

### Mode 3: 15-minute debrief call

By far the highest-value mode. You'll learn things in 15 minutes of
"so what did you find weird?" that three pages of written feedback
miss. The brain-to-mouth path captures hesitations, mid-sentence
corrections, and assumptions the brain-to-keyboard path filters out.

If the tester is willing, do this. Bring a notebook. Don't argue with
their reactions, even when you disagree. Note everything.

---

## What's *not* the tester's job

Be explicit about this so they don't sandbag feedback out of politeness:

- They don't need to triage whether something is a bug, a missing
  feature, or a design choice. That's your job. They just report
  friction.
- They don't need to suggest fixes. Their job is to be a fresh pair
  of eyes, not to redesign the product.
- They don't need to read the README, SRS, or task DAG first. If they
  have to read documentation to use Forge, that itself is feedback.

The single most useful sentence to include is: *"Don't try to be polite
about it. The friction is the point of the experiment."*

---

## The drop-in message

Copy this and send it. Adjust the install command if your repo or
marketplace location is different.

---

> Hey — I built a Claude Code plugin called Forge. Trying to figure out
> if it's useful or if I've built something that gets in the way. 30
> minutes of your honest reaction would help me a lot.
>
> Here's the deal:
>
> 1. Install:
>    ```
>    /plugin marketplace add tonmoy007/forge-plugins
>    /plugin install forge@forge-plugins
>    ```
> 2. Open a small real project (a side project, a script, anything you'd
>    use Claude Code on)
> 3. Run `/forge:init`, then `/forge:srs`, then try `/forge:product` to
>    move to the next stage
> 4. If anything is confusing, slow, or pointless, write it down. Any
>    format. Send me whatever you wrote.
> 5. When you're done: `/forge:uninstall` to clean up
>
> If something breaks: run `/forge:doctor` and paste me the output. Or
> `cat .forge/hook-errors.log` if Claude Code is acting weird but doctor
> says everything's green. Either is enough for me to debug.
>
> Heads up: Forge adds friction by design. It's trying to enforce
> discipline around requirements, planning, and gates. That might feel
> heavy or pointless — and if it does, that's exactly what I want to
> hear. Don't try to be polite about it.

---

## Picking testers

The feedback you get is shaped by who you ask. Two profiles worth
recruiting, deliberately:

**The disciplined engineer.** Writes specs before code. Cares about
traceability. Has opinions about ADRs. Likely to appreciate Forge's
overhead.

**The vibes coder.** Treats Claude Code as "just write me the code."
Doesn't write README files. Will probably hate the gates.

Both are useful, and they tell you different things:

- If the disciplined engineer hits friction, it's a real UX bug.
  Forge should not feel heavy to its target audience.
- If the vibes coder hates everything, that's expected. The signal
  is *which specific things* they hate. "I hate the gates" tells you
  Forge isn't for them. "I hate that I have to write REQ-IDs by hand"
  tells you the friction is in implementation, not philosophy.

If you can only ask one person, ask the disciplined engineer first.
They're your actual user.

---

## What to do with the feedback

After the test:

1. **Read everything without responding.** Resist the urge to
   defend or explain. The tester's reactions are data; defending
   pollutes the data.
2. **Categorize each item:**
   - **Bug** — Forge is broken; fix in next patch
   - **UX friction** — Forge works but is rough; queue for v0.1.4
   - **Confusion** — documentation gap; fix the README or add a
     `docs/` file
   - **Design disagreement** — they want Forge to be something it
     isn't; ignore or note as out-of-scope
3. **Capture lessons.** Anything that surprised them should become
   an entry in your project's `tasks/lessons.md` so future you (and
   future Claude sessions) start with that context.
4. **Update v0.1.4 SRS** with the friction items. Don't try to fix
   everything in one patch; pick the top 3-5.
5. **Thank them concretely.** Show them what you changed because of
   their feedback. People who feel heard give more feedback next time.

---

## A note about v0.1.3 specifically

v0.1.3 ships *without* the external-user round-trip the original SRS
acceptance required (§9.4). This is a deliberate deferral. The v0.1.4
retrospective should treat the first external user's feedback as the
single most important input — more important than any individual bug
report — and the v0.1.4 SRS should be heavily influenced by what they
found.

If the first tester finds something that makes you want to ship a
v0.1.3.1 patch instead of waiting for v0.1.4, do it. Trust on a small
project compounds fast — one well-handled "I found this bug, you fixed
it in 2 days" interaction makes a tester much more willing to test
v0.1.5, v0.2, and beyond.