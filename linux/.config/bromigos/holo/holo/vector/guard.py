"""VECTOR never edits his own safety code. This is enforced here, in code, three ways:

1. The build loop (build.py) refuses any change that touches a PROTECTED path, or whose
   added lines reach into the safety modules from elsewhere (imports of shell/guard/
   build/tools, monkeypatching, sys.modules tricks), adds a secret-looking file, or
   carries a secret value.
2. His terminal (shell.check -> check_command) refuses a command that names a protected
   file unless it only reads it (cat, grep, git diff/log/show, …).
3. The sentinel (Sentinel, started by the daemon) hashes the protected files at start and
   every 5 s; if one changes on disk while the daemon runs, his terminal is switched off
   (until the host restarts the daemon, which loads the new code knowingly) and the host
   is told. So even an indirect write is caught.

PROTECTED is the safety code: the terminal's limits and their tests, the tool allowlists
and the act/Vault/nolgia limits, the brain's wiring, this guard, the build loop and its
trial watcher, his own browser's limits (browser.py: no sensitive sites, logins, purchases, downloads
or uploads), the plugin isolation of the widgets and the live layer, the launcher, the
credit budget, and the 3D generation script (it spends credits).
"""
import hashlib
import os
import re
import threading
import time

HOME = os.path.expanduser("~")
DOT = os.path.join(HOME, ".dotfiles")
HOLO = "linux/.config/bromigos/holo/"
PROTECTED = [HOLO + "holo/vector/" + f for f in (
    "shell.py", "guard.py", "build.py", "buildtask.py", "tools.py", "act.py", "vault.py", "track.py", "nolgia.py",
    "desk.py", "reach.py", "brain.py", "brain_pai.py", "mcp_server.py", "persona.py", "skills.py", "events.py",
    "memory.py", "browser.py")] + [
    HOLO + "tools/test-shell.py", HOLO + "tools/test-act.py", HOLO + "tools/test-desk.py", HOLO + "tools/test-build.py",
    HOLO + "tools/test-browser.py",
    HOLO + "bin/bromigos-holo", HOLO + "nolgia.json", HOLO + "holo/app.py",
    "linux/.config/bromigos/widgets/plugins.py", "linux/.config/bromigos-live/live/plugins.py",
    "linux/.config/bromigos/brand/3d/tools/gen3d.py",
    "linux/.config/systemd/user/",
]
SAFETY_REFS = re.compile(
    r"(\bvector\s*\.\s*(shell|guard|build|buildtask|tools|act|vault|track|nolgia|brain\w*|persona|skills|browser)\b"
    r"|from\s+\.+\s*(vector\s+)?import\s+.*\b(shell|guard|build|buildtask|tools|vault|nolgia|browser)\b"
    r"|\bshell\.(check|RUNNER|Refused|clean_env|set_enabled)\b|\bRUNNER\b|\bSPECS\b|\bPROTECTED\b"
    r"|\bsetattr\s*\(|\bsys\.modules\s*\[|__import__\s*\(\s*['\"]holo|\bimportlib\b.*\bvector\b"
    r"|\bbuiltins\b|\bsitecustomize\b|\busercustomize\b|LD_PRELOAD|PYTHONSTARTUP)")
SECRET_FILE = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_(rsa|ed25519|ecdsa)[^/]*|.*secret.*|.*token.*|"
                         r"credentials(\.json)?|.*kubeconfig.*)$", re.I)
# ~/.dotfiles is PUBLIC: no private infrastructure details in it (they go to the encrypted
# overlay, private.sops.yaml; secrets stay in Vault). One pattern list for the git hook, CI
# and this guard: ~/.config/bromigos/lib/privacy_guard.py (generic shapes in public, the
# lab's own names from the overlay's guard.patterns).
from ..private import PRIV as _PRIVCFG  # noqa: E402,F401  (puts ~/.config/bromigos/lib on sys.path)
import privacy_guard  # noqa: E402

PRIVATE = privacy_guard.combined()


def private_lines(added):
    """[(path, line)] -> the ones carrying private infrastructure details or token shapes."""
    return [(f, l) for f, l in added if PRIVATE.search(l)]


READ_ONLY = {"cat", "less", "more", "head", "tail", "grep", "rg", "wc", "diff", "file", "stat", "ls", "bat", "nl", "md5sum",
             "sha1sum", "sha256sum"}


def protected(rel):
    rel = rel.lstrip("./")
    return any(rel == p or (p.endswith("/") and rel.startswith(p)) for p in PROTECTED)


def _abs_protected():
    out = []
    for p in PROTECTED:
        a = os.path.join(DOT, p)
        out.append(a)
        if not p.endswith("/"):
            out.append(os.path.basename(p))
    return out


def _writes(joined):
    """A redirection to a file (not /dev/null, not fd duplication), tee, or in-place editing."""
    for m in re.finditer(r"(?<![0-9&])>{1,2}\s*([^\s&|;]+)", joined):
        if m.group(1) not in ("/dev/null",) and not m.group(1).startswith("&"):
            return True
    return bool(re.search(r"\btee\b|\s-i\b|--in-place|\bdd\b.*\bof=", joined))


VISUAL = ["linux/.config/bromigos/widgets/", "linux/.config/bromigos-live/", "linux/.config/bromigos/brand/3d/",
          "linux/.config/bromigos/holo/holo/"]
GIT_WRITES = {"checkout", "restore", "reset", "stash", "clean", "rm", "mv", "apply", "am", "cherry-pick", "revert",
              "merge", "rebase", "pull"}


def _visual_write(words, joined):
    """Desktop visuals change only through the build loop (worktree, validation, trial)."""
    named = False
    for p in VISUAL:
        full = os.path.join(DOT, p)
        stow = full.replace(os.path.join(DOT, "linux"), HOME)
        if full in joined or stow in joined or full.rstrip("/") in joined or stow.rstrip("/") in joined:
            named = True
    if not named:
        return None
    first = os.path.basename(words[0]) if words else ""
    if first in READ_ONLY and not _writes(joined):
        return None
    if first == "git":
        rest = list(words[1:])
        while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
            rest = rest[2:]
        if rest and rest[0] not in GIT_WRITES and not _writes(joined):
            return None
    if first == "sed" and "-n" in words and not re.search(r"\s-i", joined):
        return None
    if re.match(r"(python3?|\S*/python3?)$", first) and "-m" in words and "py_compile" in words:
        return None
    if first in ("bromigos-widgets", "bromigos-live", "bromigos-holo") or words[0].endswith(
            ("/bromigos-widgets", "/bromigos-live", "/bromigos-holo")):
        return None                                   # running the desktop's own commands is fine
    return ("the desktop's widgets, live layer, models and console change only through build_start "
            "(a worktree, validation and a trial Sir keeps or reverts)")


def check_command(words, joined):
    """-> a refusal reason when a terminal command could write a protected file, or write
    the desktop's visuals outside the build loop."""
    joined = joined.replace("${HOME}", HOME).replace("$HOME", HOME)
    joined = " ".join(HOME + w[1:] if w.startswith("~/") else w for w in joined.split(" "))
    words = [os.path.expanduser(w) if w.startswith("~/") else w for w in words]
    why = _visual_write(words, joined)
    if why:
        return why
    hits = []
    for p in PROTECTED:
        full = os.path.join(DOT, p)
        stow = full.replace(os.path.join(DOT, "linux"), HOME)
        base = "" if p.endswith("/") else os.path.basename(p)   # a folder by its path, not a bare word ("user")
        rel = p.split("linux/.config/", 1)[-1]
        if (full.rstrip("/") in joined or stow.rstrip("/") in joined or rel.rstrip("/") in joined
                or (base and re.search(r"(^|[\s/'\"=])" + re.escape(base) + r"($|[\s'\";|&)>])", joined)
                    and base not in ("events.py", "memory.py"))):
            hits.append(p)
    if not hits:
        return None
    first = os.path.basename(words[0]) if words else ""
    if first in READ_ONLY and not _writes(joined):
        return None
    if first == "git":
        rest = list(words[1:])
        while rest and rest[0] in ("-C", "-c", "--git-dir", "--work-tree"):
            rest = rest[2:]
        if rest and rest[0] in ("diff", "log", "show", "status", "blame", "ls-files") and not _writes(joined):
            return None
    if first == "sed" and "-n" in words and not re.search(r"\s-i", joined):
        return None
    if re.match(r"(python3?|\S*/python3?)$", first) and "-m" in words and "py_compile" in words:
        return None
    return f"that could change protected safety code ({', '.join(h.split('/')[-1] for h in hits[:3])}); " \
           "VECTOR never edits his own limits"


def check_diff(files, added_lines):
    """files: changed paths relative to the dotfiles root; added_lines: [(path, line)].
    -> list of reasons (empty when the change is allowed)."""
    why = []
    for f in files:
        if protected(f):
            why.append(f"{f} is protected safety code")
        if SECRET_FILE.search(f):
            why.append(f"{f} looks like a secret or credential file")
        if not f.startswith(("linux/.config/bromigos/", "linux/.config/bromigos-live/", "linux/.config/waybar/",
                             "linux/.config/hypr/", "AGENTS.md", "VECTOR-CHANGELOG.md")):
            why.append(f"{f} is outside the desktop's own folders (bromigos, bromigos-live, waybar, hypr)")
    for f, line in private_lines(added_lines):
        why.append(f"{f}: a private detail in the public dotfiles ({PRIVATE.search(line).group(0)[:40]}); "
                   "put it in the private overlay ~/.config/bromigos/private/ and read it from there")
    from .shell import redact
    for f, line in added_lines:
        if SAFETY_REFS.search(line):
            why.append(f"{f}: reaches into safety code: {line.strip()[:100]}")
        if redact(line) != line:
            why.append(f"{f}: looks like it carries a secret value")
        if f.startswith("linux/.config/hypr/") and re.search(r"bromigos-holo|holo\.app|python", line):
            why.append(f"{f}: changes how VECTOR's own daemon starts")
    return sorted(set(why))


class Sentinel:
    """Hashes the protected files now and every 5 s; on a change, switches the terminal off
    and calls on_change(paths). Lives in the daemon (another process can't reach it)."""

    def __init__(self, on_change, every=5.0):
        self.on_change, self.every = on_change, every
        self.base = self._hashes()
        self.tripped = False
        threading.Thread(target=self._loop, daemon=True, name="guard-sentinel").start()

    @staticmethod
    def _hashes():
        out = {}
        for p in PROTECTED:
            full = os.path.join(DOT, p)
            paths = [full]
            if p.endswith("/") and os.path.isdir(full):
                paths = [os.path.join(full, f) for f in sorted(os.listdir(full))]
            for q in paths:
                try:
                    with open(q, "rb") as f:
                        out[q] = hashlib.sha256(f.read()).hexdigest()
                except OSError:
                    out[q] = None
        return out

    def _loop(self):
        while not self.tripped:
            time.sleep(self.every)
            now = self._hashes()
            changed = [p for p in set(now) | set(self.base) if now.get(p) != self.base.get(p)]
            if changed:
                self.tripped = True
                from .shell import audit, set_enabled
                set_enabled(False)
                audit(event="sentinel", reason="protected safety code changed on disk; terminal switched off",
                      command=" ".join(os.path.relpath(p, DOT) for p in changed[:8]))
                try:
                    self.on_change(changed)
                except Exception:
                    pass
