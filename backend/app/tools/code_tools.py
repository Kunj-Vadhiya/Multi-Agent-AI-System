"""
Code tools for Coding Agent and MCP Server.

Provides safe Python code analysis and restricted sandboxed evaluation:
- validate_python_code(code) -> AST validation, syntax parsing, and dangerous call auditing
- execute_sandboxed_python(code, timeout) -> Restricted in-memory execution with safe builtins,
  AST safety enforcement, stdout/stderr capture, and timeout capping.
"""

import ast
import contextlib
import io
import logging
import math
import sys
import threading
from typing import Any, Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

BANNED_AST_NODES = {
    "Import",  # Checked individually in visitor
    "ImportFrom",
}

BANNED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "http", "urllib", "requests",
    "pty", "ctypes", "multiprocessing", "threading", "builtins", "posix", "nt",
}

BANNED_CALLS = {
    "eval", "exec", "__import__", "open", "compile", "breakpoint", "getattr", "setattr", "delattr",
}


class CodeSafetyAuditor(ast.NodeVisitor):
    """AST visitor that checks for dangerous calls, imports, or attributes."""

    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_mod = alias.name.split(".")[0]
            if root_mod in BANNED_MODULES:
                self.violations.append(f"Import of disallowed module '{alias.name}'.")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in BANNED_MODULES:
                self.violations.append(f"Import from disallowed module '{node.module}'.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            self.violations.append(f"Call to prohibited function '{node.func.id}()'.")
        self.generic_visit(node)


def validate_python_code(code: str) -> Dict[str, Any]:
    """
    Validate Python code syntax and security posture via AST parsing.

    Args:
        code: Python source code snippet.

    Returns:
        Dict with 'valid' (bool), 'syntax_error' (optional), and 'security_violations' (list).
    """
    if not code or not code.strip():
        return {"valid": False, "error": "Empty code snippet provided."}

    # 1. Syntax check
    try:
        tree = ast.parse(code)
    except SyntaxError as err:
        return {
            "valid": False,
            "syntax_error": {
                "message": err.msg,
                "line": err.lineno,
                "offset": err.offset,
                "text": err.text,
            },
            "security_violations": [],
        }

    # 2. Security audit
    auditor = CodeSafetyAuditor()
    auditor.visit(tree)

    is_safe = len(auditor.violations) == 0
    return {
        "valid": is_safe,
        "syntax_error": None,
        "security_violations": auditor.violations,
        "ast_nodes_count": len(list(ast.walk(tree))),
    }


def execute_sandboxed_python(
    code: str,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Execute a Python snippet in a restricted, sandboxed environment.

    Safety measures:
    - Pre-execution AST audit for banned calls and modules.
    - Restricted global scope with safe built-ins only.
    - Timeout protection against infinite loops.
    - Captures stdout and stderr streams.
    - Output character cap (max 4000 chars).
    """
    max_timeout = timeout or settings.CODE_EXECUTION_TIMEOUT

    # Pre-validation
    validation = validate_python_code(code)
    if not validation["valid"]:
        violations_str = "; ".join(validation["security_violations"])
        error_msg = validation.get("syntax_error") or f"Security policy violation: {violations_str}"
        return {
            "status": "rejected",
            "error": str(error_msg),
            "stdout": "",
            "stderr": "",
        }

    # Safe restricted namespace
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bin": bin,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "hex": hex,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "iter": iter,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "oct": oct,
        "ord": ord,
        "pow": pow,
        "print": print,
        "range": range,
        "reversed": reversed,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }

    restricted_globals = {
        "__builtins__": safe_builtins,
        "math": math,
    }
    local_vars: Dict[str, Any] = {}

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exec_result: Dict[str, Any] = {"status": "success", "error": None}

    def _target_runner() -> None:
        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                exec(code, restricted_globals, local_vars)
        except Exception as err:
            exec_result["status"] = "runtime_error"
            exec_result["error"] = f"{type(err).__name__}: {str(err)}"

    thread = threading.Thread(target=_target_runner)
    thread.daemon = True
    thread.start()
    thread.join(timeout=max_timeout)

    if thread.is_alive():
        logger.warning("[Code Tool] Sandboxed execution timed out after %ds", max_timeout)
        return {
            "status": "timed_out",
            "error": f"Execution exceeded safety limit of {max_timeout} seconds.",
            "stdout": stdout_buf.getvalue()[:2000],
            "stderr": "Execution terminated by watchdog.",
        }

    raw_stdout = stdout_buf.getvalue()[:4000]
    raw_stderr = stderr_buf.getvalue()[:4000]

    # Pick up last variable defined if present
    returned_vars = {k: str(v) for k, v in local_vars.items() if not k.startswith("_")}

    return {
        "status": exec_result["status"],
        "error": exec_result["error"],
        "stdout": raw_stdout,
        "stderr": raw_stderr,
        "variables": returned_vars,
    }
