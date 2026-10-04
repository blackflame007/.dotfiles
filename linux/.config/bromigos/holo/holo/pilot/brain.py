"""PILOT's brain: qwen3.8-flash-next on the homelab LiteLLM, streaming, with tool calls.

The key comes from ~/.local/share/bromigos/litellm-key (mode 600, from Vault
secret/<vault-path> litellm_api_key); it is never logged. Thinking is turned off
(about 0.5 s to first token instead of about 6 s). The conversation is kept in memory
for the session and appended to ~/.local/state/bromigos/pilot-chat.log (local only).
"""
import json
import os
import ssl
import threading
import time
import urllib.request

from . import persona, tools

URL = "https://litellm.redacted/v1/chat/completions"
MODEL = "qwen3.8-flash-next"
KEY = os.path.expanduser("~/.local/share/bromigos/litellm-key")
CA = os.path.expanduser("~/.config/homelab/homelab-ca.crt")
CHATLOG = os.path.expanduser("~/.local/state/bromigos/pilot-chat.log")
MAX_ROUNDS = 6


def _label(name, args):
    a = ", ".join(f"{v}" for v in (args or {}).values() if v not in (None, "", [], {}))
    return name.replace("_", " ") + (f" · {a}" if a else "")


class Brain:
    """cb: object with state(s), delta(text), tool(name, args, label, exhibit), done(text, stats), error(msg).
    Callbacks run on the worker thread; the app marshals them to GTK."""

    def __init__(self, cb, ui=None, live=None):
        self.cb = cb
        self.ui = ui
        self.live = live
        self.history = []
        self.lock = threading.Lock()
        self.busy = False
        self.cancel = threading.Event()
        self.ctx = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()

    def ask(self, text):
        if self.busy:
            self.cancel.set()
            time.sleep(0.05)
        self.cancel.clear()
        threading.Thread(target=self._run, args=(text,), daemon=True, name="pilot-brain").start()

    def _log(self, rec):
        os.makedirs(os.path.dirname(CHATLOG), exist_ok=True)
        with open(CHATLOG, "a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}) + "\n")

    def _messages(self):
        now = time.strftime("%A %d %B %Y, %H:%M %Z")
        sys = persona.SYSTEM + f"\nIt is {now}. The workstation is an Arch Linux desktop (Hyprland) the operator sits at."
        return [{"role": "system", "content": sys}] + self.history[-24:]

    def _run(self, text):
        with self.lock:
            self.busy = True
            t0 = time.monotonic()
            stats = {"first_token_s": None, "tools": 0, "rounds": 0}
            try:
                self.history.append({"role": "user", "content": text})
                self._log({"role": "user", "text": text})
                self.cb.state("thinking")
                final = ""
                for rnd in range(MAX_ROUNDS):
                    stats["rounds"] = rnd + 1
                    content, calls = self._stream(stats, t0)
                    if self.cancel.is_set():
                        return
                    if calls:
                        self.history.append({"role": "assistant", "content": content or None, "tool_calls": calls})
                        for c in calls:
                            name = c["function"]["name"]
                            try:
                                args = json.loads(c["function"]["arguments"] or "{}")
                            except ValueError:
                                args = {}
                            self.cb.state("thinking")
                            label = _label(name, args)
                            result, ex = tools.call(name, args, ui=self.ui, live=self.live)
                            stats["tools"] += 1
                            self.cb.tool(name, args, label, ex)
                            self._log({"role": "tool", "name": name, "args": args, "bytes": len(result)})
                            self.history.append({"role": "tool", "tool_call_id": c["id"], "content": result})
                        continue
                    final = content
                    break
                else:
                    final = "Sorry, sorry, I went round in circles there. Ask me again, maybe a bit narrower?"
                    self.cb.delta(final)
                self.history.append({"role": "assistant", "content": final})
                # older tool results are large; keep only their gist in history
                for m in self.history[:-8]:
                    if m.get("role") == "tool" and len(m.get("content") or "") > 1500:
                        m["content"] = m["content"][:1500] + "…"
                stats["total_s"] = round(time.monotonic() - t0, 2)
                self._log({"role": "pilot", "text": final, "stats": stats})
                self.cb.done(final, stats)
            except Exception as e:  # say what broke, in character, and keep going
                self._log({"role": "error", "text": str(e)[:300]})
                self.cb.error(f"{type(e).__name__}: {str(e)[:160]}")
            finally:
                self.busy = False

    def _stream(self, stats, t0):
        with open(KEY) as f:
            key = f.read().strip()
        body = {"model": MODEL, "messages": self._messages(), "tools": tools.schemas(), "tool_choice": "auto",
                "stream": True, "temperature": 0.7, "max_tokens": 900,
                "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        content = ""
        calls = {}
        spoke = False
        with urllib.request.urlopen(req, timeout=90, context=self.ctx) as r:
            for raw in r:
                if self.cancel.is_set():
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    ch = json.loads(data)["choices"][0]
                except (ValueError, KeyError, IndexError):
                    continue
                d = ch.get("delta") or {}
                if d.get("content"):
                    if stats["first_token_s"] is None:
                        stats["first_token_s"] = round(time.monotonic() - t0, 2)
                    if not spoke:
                        self.cb.state("speaking")
                        spoke = True
                    content += d["content"]
                    self.cb.delta(d["content"])
                for tc in d.get("tool_calls") or []:
                    i = tc.get("index", 0)
                    c = calls.setdefault(i, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                    if tc.get("id"):
                        c["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        c["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        c["function"]["arguments"] += fn["arguments"]
        out = [calls[i] for i in sorted(calls)]
        for k, c in enumerate(out):
            c["id"] = c["id"] or f"call_{int(time.time() * 1000)}_{k}"
        return content.strip(), out

    def reset(self):
        self.history.clear()
