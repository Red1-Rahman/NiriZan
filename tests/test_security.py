# tests/test_security.py
"""Security regression tests for nirizan."""
import ast
import pathlib
import re
import nirizan

ROOT = pathlib.Path(nirizan.__file__).resolve().parent

# Dangerous function calls forbidden in core SDK logic
DANGEROUS_CALLS = {
    "eval", "exec", "compile", "__import__",
    "os.system", "pickle.loads", "marshal.loads",
    "shelve.open", "ctypes.CDLL", "pty.spawn",
}

# Explicit allowlist for legitimate internal calls (file_name, call_name)
ALLOWED_CALLS = {
    ("collector.py", "subprocess.run"),  # Safe usage for Git commit SHA resolution
}

OBFUSCATION_CALLS = {
    "base64.b64decode", "zlib.decompress", "lzma.decompress"
}

# Top-level network modules banned in core SDK
BANNED_NETWORK_MODULES = {
    "socket", "urllib", "urllib3", "requests", "httpx", "aiohttp"
}


def _iter_python_files():
    for p in ROOT.rglob("*.py"):
        yield p


def _get_call_name(node):
    """Recursively resolve AST node names like 'os.system' or 'subprocess.run'."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        val_name = _get_call_name(node.value)
        return f"{val_name}.{node.attr}" if val_name else node.attr
    return ""


def test_no_dangerous_calls():
    offenders = []
    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _get_call_name(node.func)
                if name in DANGEROUS_CALLS or name.startswith("subprocess."):
                    if (path.name, name) not in ALLOWED_CALLS:
                        offenders.append(f"{path.name}:{node.lineno} uses '{name}'")
    assert not offenders, "Dangerous calls found:\n" + "\n".join(offenders)


def test_no_obfuscated_payloads():
    offenders = []
    for path in _iter_python_files():
        # AST check: catch execution of decoding functions rather than docstrings
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = _get_call_name(node.func)
                if name in OBFUSCATION_CALLS:
                    offenders.append(f"{path.name}:{node.lineno} executes '{name}'")

        # Byte check: require long consecutive hex streams (10+ escapes) to avoid false positives on short byte literals
        raw = path.read_bytes()
        if re.search(rb"(\\x[0-9a-fA-F]{2}){10,}", raw):
            offenders.append(f"{path.name}: contains long hex-encoded byte blob")

    assert not offenders, "Possible obfuscation detected:\n" + "\n".join(offenders)


def test_no_network_calls():
    offenders = []
    for path in _iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_module = alias.name.split(".")[0]
                    if top_module in BANNED_NETWORK_MODULES:
                        offenders.append(f"{path.name}:{node.lineno} imports '{alias.name}'")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_module = node.module.split(".")[0]
                    if top_module in BANNED_NETWORK_MODULES:
                        offenders.append(f"{path.name}:{node.lineno} imports from '{node.module}'")

    assert not offenders, "Banned network imports found:\n" + "\n".join(offenders)
