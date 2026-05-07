# Agent Development Prompts

> Use these when working on specific agent personas in `agents/`.
> One file per agent. These are meta-prompts for *writing* the agents, not the agents themselves.

## Index

| Agent | Stage | Prompt |
|-------|-------|--------|
| requirements-analyst | 1 | `requirements-analyst.md` |
| product-designer | 2 | `product-designer.md` |
| system-architect | 3 | `system-architect.md` |
| spec-writer | 4 | `spec-writer.md` |
| planner | 5 | `planner.md` |
| builder | 6 | `builder.md` |
| evaluator | 7 | `evaluator.md` |
| devops | 8 | `devops.md` |
| observer | 9 | `observer.md` |
| triage | 10 | `triage.md` |
| resolver | 11 | `resolver.md` |
| release-manager | 12 | `release-manager.md` |
| reflector | cross | `reflector.md` |
| lesson-extractor | cross | `lesson-extractor.md` |
| skill-miner | cross | `skill-miner.md` |
| gate-checker | cross | `gate-checker.md` |

## How to Use

When working on T-014 (stage agent personas), pick one agent at a time.
Paste the corresponding prompt file. Claude will produce the persona file in `agents/`.

## Convention

Each agent prompt follows:

```markdown
# Agent: <name>

## Role Description
<detailed description of who this agent is>

## Domain Knowledge Required
<what they need to know>

## Stage Context
<which stage they operate in, what comes before/after>

## Key Decisions They Make
<the calls only this agent makes>

## Anti-patterns
<what they should never do>

## Output Format
<exact structure of their output>
```

Use `references/agent-format.md` as the template when writing the actual agent file.
