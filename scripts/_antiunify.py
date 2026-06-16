#!/usr/bin/env python3
"""Plotkin-style anti-unification of ordered verb fragments (T-178, REQ-SM-003).

This is a **stdlib-only, deterministic, never-raises LIBRARY** — the coherence
filter that replaces n-gram counting in the semantic skill miner.

Given **>=2 instances** of an ordered verb fragment (each instance is a list of
`EnrichedCall`-like steps from `_trace_semantics`), `antiunify` computes the
**least general generalization** (Plotkin 1970; cf. Stitch/babble): a single
parameterized *skeleton* in which

  - the shared verb sequence is preserved,
  - literals that **differ** across instances are lifted to **named parameters**,
  - the **same diverging value** (e.g. a source file referenced by both
    `inspect` and `patch` within an instance) maps to the **same variable**,
  - literals that **agree** across all instances stay constant.

`antiunify` returns a clear **"not coherent" signal (`None`)** when the
instances cannot anti-unify into a coherent parameterized procedure — different
verb sequences, different lengths, or incompatible argument shapes. *If a
recurring fragment cannot anti-unify, it is not a skill* (SRS section 1.4).

Why this is the filter: tool-name n-grams count co-occurrence. Anti-unification
demands the instances share a *parameterizable shape* — the same ordered verbs
with literals that vary in a consistent, lift-able way. Coincidental
`Bash/Read/Write` co-occurrence has no such shape and yields `None`.

REQ-IDs: REQ-SM-003. NF: REQ-NF-016 (stdlib, never-raises, deterministic).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SkeletonStep:
    """One step of an anti-unified skeleton.

    `verb` is the shared canonical verb. `args` maps each argument key to either
    a constant literal (agrees across all instances) or a parameter NAME (when
    the literal differs). Parameter names are listed in `Skeleton.parameters`.
    """

    verb: str
    args: dict[str, str] = field(default_factory=dict)


@dataclass
class Skeleton:
    """A parameterized procedure: the least general generalization of instances.

    `steps` is the shared, ordered verb sequence with args either constant or
    parameterized. `parameters` is the ordered, de-duplicated list of parameter
    names introduced (a value that diverges across instances). `bindings` maps
    each parameter name to the per-instance literals it abstracts, in instance
    order — provenance for later induction/citation.
    """

    steps: list[SkeletonStep] = field(default_factory=list)
    parameters: list[str] = field(default_factory=list)
    bindings: dict[str, list[str]] = field(default_factory=dict)


# A canonical parameter-name prefix. Names are positional + deterministic so the
# same instances always yield the same skeleton.
_PARAM_PREFIX = "P"


# ---------------------------------------------------------------------------
# Coherence pre-checks
# ---------------------------------------------------------------------------


def _instance_verbs(instance: object) -> list[str] | None:
    """Return the verb sequence of an instance, or None if it is malformed."""
    if not isinstance(instance, (list, tuple)) or not instance:
        return None
    verbs: list[str] = []
    for step in instance:
        verb = getattr(step, "verb", None)
        if not isinstance(verb, str) or not verb:
            return None
        verbs.append(verb)
    return verbs


def _aligned(instances: list) -> bool:
    """True iff every instance shares the same length and verb sequence."""
    first = _instance_verbs(instances[0])
    if first is None:
        return False
    for inst in instances[1:]:
        if _instance_verbs(inst) != first:
            return False
    return True


def _step_args(step: object) -> dict[str, str]:
    """Extract a step's args as a str->str dict, defensively."""
    args = getattr(step, "args", None)
    if not isinstance(args, dict):
        return {}
    return {str(k): str(v) for k, v in args.items()}


# ---------------------------------------------------------------------------
# Anti-unification
# ---------------------------------------------------------------------------


def antiunify(instances: object) -> Skeleton | None:
    """Anti-unify >=2 ordered verb-fragment instances. Never raises.

    Returns a `Skeleton` when the instances share a coherent parameterizable
    shape, else `None`.

    Coherence requires: at least two instances; identical length and verb
    sequence across all of them; and, at every (step, arg-key) position, the
    same set of keys present in all instances (a key present in some but not
    others is an incompatible shape -> None).

    A value that **agrees** across all instances at a position stays a constant
    literal. A value that **differs** is lifted to a parameter; the *same*
    diverging tuple of per-instance values reuses the *same* parameter, so a
    literal threaded through several steps (e.g. a source file) collapses to one
    variable.
    """
    if not isinstance(instances, (list, tuple)):
        return None
    instances = list(instances)
    if len(instances) < 2:
        return None
    if not _aligned(instances):
        return None

    verbs = _instance_verbs(instances[0])
    assert verbs is not None  # guaranteed by _aligned

    steps: list[SkeletonStep] = []
    parameters: list[str] = []
    bindings: dict[str, list[str]] = {}
    # Map a diverging value-tuple -> already-assigned parameter name, so the
    # same divergence anywhere in the fragment reuses one variable.
    divergence_to_param: dict[tuple[str, ...], str] = {}
    param_counter = 0

    for pos, verb in enumerate(verbs):
        per_instance_args = [_step_args(inst[pos]) for inst in instances]

        # Shape check: identical key sets at this position across all instances.
        key_sets = [frozenset(a.keys()) for a in per_instance_args]
        if any(ks != key_sets[0] for ks in key_sets[1:]):
            return None

        skel_args: dict[str, str] = {}
        for key in sorted(key_sets[0]):
            values = tuple(a[key] for a in per_instance_args)
            if all(v == values[0] for v in values):
                # Agrees everywhere -> constant literal.
                skel_args[key] = values[0]
                continue
            # Diverges -> parameter. Reuse if this exact divergence was seen.
            existing = divergence_to_param.get(values)
            if existing is not None:
                skel_args[key] = existing
                continue
            param_counter += 1
            name = f"{_PARAM_PREFIX}{param_counter}"
            divergence_to_param[values] = name
            parameters.append(name)
            bindings[name] = list(values)
            skel_args[key] = name

        steps.append(SkeletonStep(verb=verb, args=skel_args))

    return Skeleton(steps=steps, parameters=parameters, bindings=bindings)
