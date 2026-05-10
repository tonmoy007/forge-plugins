---
name: forge-product
description: Run Stage 2 of the Forge pipeline — product UX and PRD. Use when the
  user says /forge:ux, /forge:product, wants wireframes, user flows, a PRD, or a design
  system. Requires Stage 1 SRS to exist. Invokes the product-designer persona.
allowed-tools: [Read, Write, WebSearch, WebFetch]
---

# /forge:product — Product Design & UX

## When to Use

- User says `/forge:ux` or `/forge:product`
- User wants wireframes, user flows, a PRD, or design system tokens
- Working in a Forge project at Stage 1 or 2

## Pre-flight Check

1. Read `pipeline/state.md` — confirm Forge project.
2. Confirm `pipeline/01-srs/srs.md` exists. If not: "Stage 1 (SRS) must be completed first. Run `/forge:srs`."
3. If stage > 2, inform the user this stage appears done and ask if they want to revise.

## Steps

1. Read `agents/product-designer.md` to load the Product Designer persona.
2. Adopt that persona — you are now the Product Designer.
3. Read `pipeline/01-srs/srs.md` to understand the requirements.
4. Follow the Product Designer workflow: define personas, map user flows, describe wireframes, define design tokens.
5. Write `pipeline/02-product-ux/prd.md` and `pipeline/02-product-ux/design-system.md` per the Output Contract.
6. Run `python3 ${CLAUDE_PLUGIN_DIR}/scripts/state-manager.py advance --to 2` to mark Stage 2 active.

## Verification

After running, confirm:
- `pipeline/02-product-ux/prd.md` exists with user flows (UF-IDs)
- `pipeline/02-product-ux/design-system.md` exists with color/font/spacing tokens
- `pipeline/state.md` shows `current_stage: 2`

## Next Step

"PRD and design system written. Run `/forge:architecture` to design the technical architecture."
