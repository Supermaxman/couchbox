"""Running system commands, in one place so tests can swap them out.

    from couchbox.system import sh
    sh(["systemctl", "restart", "couchbox-input"])          -> CompletedProcess (check=True)
    sh([...], check=False).returncode

Tests replace RUNNER with a fake that records calls and returns canned output.
"""

import logging
import subprocess
from collections.abc import Callable, Sequence

log = logging.getLogger("couchbox.system")


class CommandError(RuntimeError):
    pass


def _real(cmd: Sequence[str], input: str | None, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(list(cmd), input=input, capture_output=True, text=True, timeout=timeout)


RUNNER: Callable[[Sequence[str], str | None, float], subprocess.CompletedProcess] = _real


def sh(cmd: Sequence[str], *, input: str | None = None, check: bool = True, timeout: float = 120) -> subprocess.CompletedProcess:
    log.debug("run %s", " ".join(cmd))
    try:
        r = RUNNER(cmd, input, timeout)
    except FileNotFoundError:
        if check:
            raise CommandError(f"{cmd[0]} isn't installed") from None
        return subprocess.CompletedProcess(list(cmd), 127, "", f"{cmd[0]}: not found")
    except subprocess.TimeoutExpired:
        if check:
            raise CommandError(f"{cmd[0]} took too long") from None
        return subprocess.CompletedProcess(list(cmd), 124, "", "timeout")
    if check and r.returncode != 0:
        msg = (r.stderr or r.stdout or "").strip().splitlines()
        raise CommandError(f"{' '.join(cmd[:2])}: {msg[-1] if msg else f'exit {r.returncode}'}")
    return r


def out(cmd: Sequence[str], **kw) -> str:
    return sh(cmd, **kw).stdout.strip()


def systemctl(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return sh(["systemctl", *args], check=check)


def user_systemctl(user: str, *args: str) -> subprocess.CompletedProcess:
    return sh(["systemctl", "--user", "-M", f"{user}@", *args], check=False)
