"""VECTOR's skills: know-how he loads on demand, from the one shared directory
~/.config/bromigos/skills/ (dotfiles linux/.config/bromigos/skills/).

A skill is a Markdown file with YAML frontmatter (name, description, when_to_use), either
flat (`<name>.md`, as the live layer's skills are written) or Agent-Skills style
(`<name>/SKILL.md`). Each becomes a deferred Pydantic AI capability: the model sees the
name and description in its catalog and loads the body with `load_capability` when a task
needs it. The catalog is re-read when the directory changes (signature()), so a new or
edited skill is live on the next question.
"""
import os
import re

import yaml

from .. import private

DIRS = [os.path.expanduser("~/.config/bromigos/skills")]
FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.S)
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}$")


def _files():
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for e in sorted(os.listdir(d)):
            p = os.path.join(d, e)
            if e.endswith(".md") and os.path.isfile(p) and e.lower() != "readme.md":
                yield p
            elif os.path.isfile(os.path.join(p, "SKILL.md")):
                yield os.path.join(p, "SKILL.md")


def signature():
    out = []
    for p in _files():
        try:
            st = os.stat(p)
            out.append((p, st.st_mtime_ns, st.st_size))
        except OSError:
            pass
    return tuple(out)


def _frontmatter(text):
    """YAML, or, when a value holds an unquoted colon (strict YAML refuses it), plain
    `key: value` lines, as most skill readers accept."""
    try:
        meta = yaml.safe_load(text)
        if isinstance(meta, dict):
            return meta
    except yaml.YAMLError:
        pass
    meta = {}
    for line in text.splitlines():
        k, sep, v = line.partition(":")
        if sep and re.fullmatch(r"[A-Za-z_][\w-]*", k.strip()):
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def load():
    """-> [{name, description, when, body, path}] for every well-formed skill."""
    skills, seen = [], set()
    for p in _files():
        try:
            with open(p, errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        m = FRONT.match(text)
        if not m:
            continue
        meta = _frontmatter(m.group(1))
        name = str(meta.get("name") or "").strip()
        desc = " ".join(str(meta.get("description") or "").split())
        if not NAME.match(name) or not desc or name in seen:
            continue
        seen.add(name)
        when = " ".join(str(meta.get("when_to_use") or "").split())
        skills.append({"name": name, "description": desc, "when": when, "body": private.fill(m.group(2).strip()), "path": p})
    return skills


def capabilities():
    """Deferred capabilities for an Agent (loaded by the model with load_capability)."""
    from pydantic_ai.capabilities import Capability
    caps = []
    for s in load():
        desc = s["description"] + (f" Use when: {s['when']}" if s["when"] else "")
        body = (f"# Skill: {s['name']}\n(source: {s['path']}; files it names are relative to "
                f"{os.path.dirname(s['path'])})\n\n{s['body']}")
        caps.append(Capability(id=s["name"], description=desc[:1500], instructions=body, defer_loading=True))
    return caps


class Router:
    """Attach the skills a question needs, by meaning. The question and each skill's
    name + description + when_to_use are embedded with the same local model Gnosis uses
    (memory.embed). Some skills are hubs that resemble every question a little
    (data-sources), so each skill's score is taken relative to its own baseline: its mean
    score over a few neutral questions. Skills at least MARGIN above baseline, best first,
    at most MAX, go into that turn's instructions; so does a clear single winner (CLEAR above
    baseline and CLEAR above the runner-up). The deferred catalog stays for anything
    the router misses."""
    MARGIN = 0.12
    CLEAR = 0.08
    MAX = 2
    NEUTRAL = ["hey, how are you?", "what's the weather like?", "what did we talk about yesterday?",
               "tell me something interesting", "what time is it?", "thanks, that's all"]

    def __init__(self, embed):
        self.embed = embed
        self.sig = None
        self.items = []
        self.m = None
        self.base = None

    def _refresh(self):
        sig = signature()
        if sig == self.sig:
            return
        items = load()
        texts = [f"{s['name'].replace('-', ' ')}: {s['description']} Use when: {s['when']}" for s in items]
        if texts:
            self.m = self.embed(texts, timeout=10.0)
            self.base = (self.embed(self.NEUTRAL, timeout=10.0) @ self.m.T).mean(axis=0)
        else:
            self.m = self.base = None
        self.items, self.sig = items, sig

    def scores(self, question, timeout=1.0):
        self._refresh()
        if self.m is None:
            return []
        q = self.embed([question[:1000]], timeout=timeout)[0]
        rel = self.m @ q - self.base
        return sorted(((float(rel[i]), self.items[i]) for i in range(len(self.items))), key=lambda x: -x[0])

    def match(self, question, timeout=1.0):
        """-> [(margin, skill)] best first; [] on any failure (the turn just goes without)."""
        try:
            sc = self.scores(question, timeout)
            out = [x for x in sc[:self.MAX] if x[0] >= self.MARGIN]
            if not out and sc and sc[0][0] >= self.CLEAR and (len(sc) < 2 or sc[0][0] - sc[1][0] >= self.CLEAR):
                out = sc[:1]                 # a clear single winner just under the margin
            return out
        except Exception as e:
            print(f"skills: router skipped ({type(e).__name__}: {str(e)[:100]})", flush=True)
            return []

    def warm(self):
        import threading

        def go():
            try:
                self._refresh()
            except Exception as e:
                print(f"skills: router warm failed ({type(e).__name__}: {str(e)[:100]})", flush=True)
        threading.Thread(target=go, daemon=True, name="skills-warm").start()


def embed(texts, timeout=5.0):
    """The local embedding model through LiteLLM (the one Gnosis and the memory mirror use)."""
    import json
    import ssl
    import urllib.request

    import numpy as np
    from .memory import EMBED_MODEL, EMBED_URL, LLM_KEY
    ca = os.path.expanduser("~/.config/homelab/homelab-ca.crt")
    ctx = ssl.create_default_context(cafile=ca) if os.path.exists(ca) else ssl.create_default_context()
    with open(LLM_KEY) as f:
        key = f.read().strip()
    req = urllib.request.Request(EMBED_URL, data=json.dumps({"model": EMBED_MODEL, "input": texts}).encode(),
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        data = json.load(r)["data"]
    m = np.array([d["embedding"] for d in sorted(data, key=lambda d: d["index"])], np.float32)
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)


BUILD_SKILLS = {"make-widget", "make-hologram-model", "live-shader-layer", "update-visualization", "make-sound-cue",
                "hologram-build", "live-layer-animation"}
BUILD_DIRECTIVE = """
THIS IS A BUILD TASK (the host wants something made or changed on the desktop)
Call build_start now, with the whole goal in the host's words plus any details he gave. Then say one short line that your builder has started and stop. Do not read, write or inspect the desktop's files yourself, do not use your terminal for it, and never switch your terminal off: the builder does the work in the background, validates it and puts it up for a trial, and you'll announce it.
"""


def instructions_for(matched, builder=False):
    """The matched skills' bodies. For VECTOR's own voice (builder=False), a build skill
    becomes one directive instead: the build belongs to the builder (build_start)."""
    if not matched:
        return ""
    if not builder and any(s["name"] in BUILD_SKILLS for _, s in matched):
        rest = [(sc, s) for sc, s in matched if s["name"] not in BUILD_SKILLS]
        return BUILD_DIRECTIVE + (instructions_for(rest, builder=True) if rest else "")
    parts = [f"\nSKILLS FOR THIS TASK (loaded for you; follow them)\n"]
    for _, s in matched:
        parts.append(f"# Skill: {s['name']} (source: {s['path']})\n\n{s['body']}\n")
    return "\n".join(parts)
