# Lessons Learned (Test Fixture)

> Diverse fixture for testing lesson filtering and injection.

## Lessons

### 2026-04-15 — T4 GPU dtype mismatch
- **Trigger**: Fine-tuning on T4 GPU
- **Rule**: T4 lacks bf16 support. Use fp16 with manual cast after 4-bit load.
- **Why**: Wasted session on silent dtype mismatch in Qwen2.5
- **Tags**: [gpu, dtype, t4]
- **Stages**: [6]
- **Project Types**: [ml-pipeline]

### 2026-04-20 — Read before edit
- **Trigger**: About to edit a file not viewed in current turn
- **Rule**: Always view immediately before editing. Earlier views go stale.
- **Why**: Edit failed silently — file had drifted between sessions.
- **Tags**: [workflow, tools]
- **Stages**: [6]
- **Project Types**: []  # universal

### 2026-04-22 — TorchServe NVML socket
- **Trigger**: TorchServe in Docker with GPU
- **Rule**: Volume-mount /var/run/nvidia-persistenced/socket and add disable_system_metrics=true
- **Why**: nvidia-smi exits 255 in container otherwise
- **Tags**: [docker, gpu, torchserve]
- **Stages**: [8]
- **Project Types**: [ml-pipeline]

### 2026-04-25 — Bengali regex backtracking
- **Trigger**: Nested quantifier regex in Bengali postal codes
- **Rule**: Use `\s+` not `\s*` in repeating groups to prevent O(2^n) backtracking
- **Why**: Pattern matched in 60ms then hung for 30s on edge cases
- **Tags**: [regex, performance]
- **Stages**: [6]
- **Project Types**: []  # universal

### 2026-04-28 — Don't fabricate signatures
- **Trigger**: User asks how to use an unfamiliar API
- **Rule**: Read the actual code or docs before answering. Never invent function signatures.
- **Why**: "Probably right" answers are worse than "let me check"
- **Tags**: [communication, fabrication]
- **Stages**: [6, 4]
- **Project Types**: []  # universal

### 2026-05-01 — Plan mode for complex changes
- **Trigger**: Task involves 3+ files or 3+ steps
- **Rule**: Enter plan mode first. State the plan in chat. Wait for approval.
- **Why**: Diving in leads to scope creep and rework
- **Tags**: [workflow, planning]
- **Stages**: [6]
- **Project Types**: []  # universal
