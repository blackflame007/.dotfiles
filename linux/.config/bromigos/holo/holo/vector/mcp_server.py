"""VECTOR's read-only tools as an MCP server, for background workers (scheduled checks,
subagents, other harnesses). stdio by default; `--http PORT` serves streamable HTTP on
127.0.0.1 only.

Only the read tools are published. Desktop actions (launch, panel, wallpaper, scan,
notes_append), memory writes (remember, forget) and the UI tools (show_hologram,
open_gallery, set_voice) are not. Every call still goes through tools.call(), so the
allowlist, the argument checks and the audit log are the same as on the desktop.

    ~/.local/share/bromigos/venv-brain/bin/python -m holo.vector.mcp_server
"""
import functools
import inspect
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

from holo.vector import tools  # noqa: E402

READ_ONLY = ["system_stats", "lab_status", "k8s_get", "k8s_logs", "k8s_events", "argocd_apps", "prometheus_query",
             "github", "arbiter", "gnosis_search", "knowledge_search", "web_search", "web_fetch", "docs_search", "docs_read", "notes_read", "time_now", "calendar_month"]


def _wrap(name):
    fn = tools.FUNCS[name]
    desc = tools.SPECS[name][0]

    @functools.wraps(fn)
    def call(**kwargs):
        result, _ = tools.call(name, {k: v for k, v in kwargs.items() if v is not None})
        try:
            return json.loads(result)
        except ValueError:
            return result
    sig = inspect.signature(fn)
    if name == "system_stats":                 # its `live` parameter is the desktop's, not the caller's
        sig = sig.replace(parameters=[])
    call.__signature__ = sig
    call.__doc__ = desc
    return call, desc


def build():
    server = MCPServer("vector-readonly", instructions="Read-only views of the operator's workstation, the homelab, "
                                                      "ARBITER and the docs. Nothing here writes, trades or arms.")
    for name in READ_ONLY:
        fn, desc = _wrap(name)
        server.add_tool(fn, name=name, description=desc,
                        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
    return server


if __name__ == "__main__":
    srv = build()
    if "--http" in sys.argv:
        import anyio
        port = int(sys.argv[sys.argv.index("--http") + 1])
        anyio.run(lambda: srv.run_streamable_http_async(host="127.0.0.1", port=port))
    else:
        srv.run()
