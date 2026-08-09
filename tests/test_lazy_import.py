import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _heavy_modules_after_dispatch(args):
    """子进程内模拟入口分发到 add_parser 注册（不执行命令本体），
    返回已加载的 cnki/selenium 模块名列表。空列表表示惰性导入生效。"""
    code = (
        "import sys; sys.argv = ['literature'] + %r;"
        "sys.path.insert(0, %r);"
        "import importlib;"
        "from cli.registry import COMMANDS;"
        "cmd = next((t for t in sys.argv[1:] if not t.startswith('-')), None);"
        "importlib.import_module(COMMANDS[cmd]).add_parser;"
        "print(chr(10).join(k for k in sys.modules if 'cnki' in k or 'selenium' in k))"
        % (args, str(SCRIPTS))
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return [m for m in out.stdout.strip().splitlines() if m]


def test_search_command_does_not_load_cnki_or_selenium():
    loaded = _heavy_modules_after_dispatch(["search", "x", "--source", "openalex"])
    assert loaded == [], f"纯 API search 不应加载 cnki/selenium，实际加载: {loaded}"


def test_openalex_execution_does_not_load_cnki_or_selenium():
    code = (
        "import argparse, contextlib, io, os, sys, tempfile;"
        "sys.path.insert(0, %r);"
        "from cli import search_cmd;"
        "search_cmd.search_openalex = lambda *a, **kw: [];"
        "parser = argparse.ArgumentParser();"
        "sub = parser.add_subparsers(dest='command');"
        "search_cmd.add_parser(sub);"
        "args = parser.parse_args(['search', 'x', '--source', 'openalex']);"
        "tmp = tempfile.TemporaryDirectory();"
        "previous_cwd = os.getcwd();"
        "os.chdir(tmp.name);"
        "buf = io.StringIO();"
        "ctx = contextlib.redirect_stdout(buf);"
        "ctx.__enter__();"
        "args.func(args);"
        "ctx.__exit__(None, None, None);"
        "os.chdir(previous_cwd);"
        "tmp.cleanup();"
        "print(chr(10).join(k for k in sys.modules if k.startswith('core.cnki') or k.startswith('selenium')))"
        % str(SCRIPTS)
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    loaded = [m for m in out.stdout.strip().splitlines() if m]
    assert loaded == [], f"执行纯 API search 不应加载 cnki/selenium，实际加载: {loaded}"


def test_pure_api_command_modules_stay_clean_on_import():
    for args in (
        ["trends"], ["citations", "10.1/x"], ["export", "--format", "json"],
        ["cite"], ["import", "f"], ["read-paper", "f"], ["pdf-meta", "f"],
        ["projects"], ["library"], ["clean-cache"],
        ["format-profile", "--template"], ["format-check", "f.docx", "--profile", "p.json"],
        ["format-apply", "f.md", "--profile", "p.json"],
        ["review-rubric", "--template"], ["review-signals", "f.docx", "--rubric", "r.json"],
        ["review-signals", "f.md"],
        ["cite-source", "e.json"], ["cite-source-template", "--type", "ancient"],
        ["polish-signals", "f.md"],
        ["journal-profile", "--template"], ["journal-check", "f.md"],
        ["qual-codebook-template"], ["qual-code", "f.md", "--codebook", "cb.json"],
        ["theory-catalog"], ["theory-match", "--keywords", "信任,社会资本"],
    ):
        loaded = _heavy_modules_after_dispatch(args)
        assert loaded == [], f"{args} 不应加载 cnki/selenium，实际加载: {loaded}"


def test_detail_command_lazy_imports_core_cnki(monkeypatch):
    """cnki 命令在执行时才惰性导入 core.cnki（进而加载 selenium）。
    用 stub 拦截 get_detail，避免真实启动浏览器。"""
    import argparse
    import io
    from contextlib import redirect_stdout

    from cli import cnki_cmd
    import core.cnki

    called = {}
    monkeypatch.setattr(
        core.cnki, "get_detail",
        lambda url: called.setdefault("url", url) or {"status": "ok"},
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        cnki_cmd.cmd_detail(argparse.Namespace(url="https://kns.cnki.net/x"))

    assert called["url"] == "https://kns.cnki.net/x"
    assert "core.cnki" in sys.modules
