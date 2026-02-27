from __future__ import annotations

import subprocess
from typing import List, Tuple

from .config import STACKS
from .executil import eprint, has_cmd


def expand_stack(value: str) -> str:
    """Expand an alias into a full stack name, or return the input unchanged."""
    return STACKS.get(value, value)


def _run_list_stacks() -> Tuple[int, str, str]:
    p = subprocess.run(
        ["atmos", "list", "stacks"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return p.returncode, p.stdout, p.stderr


def discover_stacks(verbose_errors: bool = False) -> List[str]:
    """
    Discover stacks using `atmos list stacks`.

    Atmos 1.83 prints one stack per line, which is exactly what we parse.
    """
    if not has_cmd("atmos"):
        return []

    rc, out, err = _run_list_stacks()
    if rc != 0:
        if verbose_errors and err.strip():
            eprint(err.strip())
        return []

    stacks = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return sorted(set(stacks))


def alias_choices() -> List[str]:
    """Alias display strings for fzf picker."""
    return [f"{k} → {v}" for k, v in STACKS.items()]


def pick_stack_fzf() -> str:
    """
    Fuzzy pick stack using fzf; includes aliases + discovered stacks.
    """
    if not has_cmd("fzf"):
        raise RuntimeError("No stack provided and fzf is not installed.")

    choices: List[str] = []
    choices.extend(alias_choices())
    choices.extend(discover_stacks(verbose_errors=False))

    choices = sorted(set(c for c in choices if c.strip()))

    p = subprocess.run(
        ["fzf", "--prompt=Select stack: ", "--height=40%", "--reverse"],
        input="\n".join(choices) + "\n",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if p.returncode != 0:
        raise RuntimeError("Stack selection cancelled")

    picked = p.stdout.strip()
    if "→" in picked:
        return picked.split("→", 1)[1].strip()
    return picked
