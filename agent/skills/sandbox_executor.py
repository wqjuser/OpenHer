"""Sandboxed shell command executor for OpenClaw SKILL execution."""

import asyncio
import shlex


_DISALLOWED_SHELL_TOKENS = (";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r")


async def execute_shell(command: str, timeout: int = 30) -> dict:
    """Execute a shell command in sandbox, return stdout/stderr.

    Args:
        command: Shell command to execute.
        timeout: Maximum execution time in seconds.

    Returns:
        dict with keys: success, stdout, stderr, returncode.
    """
    if any(token in command for token in _DISALLOWED_SHELL_TOKENS):
        return {
            "success": False,
            "stdout": "",
            "stderr": "shell metacharacters are not allowed",
            "returncode": -1,
        }

    try:
        args = shlex.split(command)
    except ValueError as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
        }
    if not args:
        return {
            "success": False,
            "stdout": "",
            "stderr": "empty command",
            "returncode": -1,
        }

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"command not found: {args[0]}",
            "returncode": -1,
        }
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()  # 防止 zombie
        return {
            "success": False,
            "stdout": "",
            "stderr": "command timed out",
            "returncode": -1,
        }
    return {
        "success": proc.returncode == 0,
        "stdout": stdout.decode("utf-8", errors="replace").strip(),
        "stderr": stderr.decode("utf-8", errors="replace").strip(),
        "returncode": proc.returncode,
    }
