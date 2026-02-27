from __future__ import annotations

import os
import shutil
import sys
from typing import List


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def has_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def exec_cmd(cmd: List[str]) -> "NoReturn":
    eprint("▶ " + " ".join(cmd))
    os.execvp(cmd[0], cmd)
