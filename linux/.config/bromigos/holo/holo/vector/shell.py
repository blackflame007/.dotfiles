"""VECTOR's terminal: full access as the operator's user, no confirmation prompts, every
command logged. The limits are here, in code, and covered by tools/test-shell.py:

1. No privilege escalation: sudo, su, doas, pkexec, run0 and polkit helpers are refused
   anywhere in the command, including inside `sh -c '...'`, pipes, $(...), and the text
   of a script the command runs. A command that can't be parsed is refused.
2. No secrets: the shell's environment is scrubbed of tokens, keys, secrets, passwords,
   Vault, cloud and GitHub credentials. `vault`, `gcloud secrets`, `kubectl … secret(s)`
   and any read of known secret paths (~/.vault-token, ~/.ssh private keys, the desktop's
   key and token files, gcloud, kube config, .env files, gnupg, password stores, browser
   profiles, git/docker/netrc credentials, wallets) are refused. Anything secret-looking in
   the output is redacted before it reaches the model, the transcript or the log.
3. No real money: live venue order endpoints (Alpaca live, Kalshi, Polymarket, Coinbase),
   ARBITER live/arm routes, fund transfers and wallet keys are refused. Paper and read
   endpoints are fine.
4. Each command runs in a new session (killable as a group), default 60 s timeout (up to
   10 min on request), cwd ~ by default, output capped. `bromigos-holo shell off|on` is
   the kill switch; while off nothing runs. Barge-in or STOP kills the running group.
5. Audit: ~/.local/state/bromigos/vector-shell.log, one JSON line per command or refusal.
"""
import json
import os
import re
import shlex
import signal
import subprocess
import threading
import time

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".local/state/bromigos")
LOG = os.path.join(STATE, "vector-shell.log")
OFF = os.path.join(STATE, "vector-shell-off")
MAX_READ = 512 * 1024
MODEL_CHARS = 6000

PRIV = {"sudo", "su", "doas", "pkexec", "run0", "pkttyagent", "sudoedit", "visudo", "polkit-agent-helper-1",
        "machinectl", "systemd-run"}           # systemd-run / machinectl shell can escalate via polkit
SECRET_CMDS = {"vault", "pass", "gopass", "secret-tool", "gpg", "gpg2", "keepassxc-cli", "op", "bw", "lpass"}
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "ksh"}
SECRET_PATHS = [
    ".vault-token", ".ssh/", ".gnupg", ".password-store", ".local/share/bromigos/", ".config/gcloud", ".kube/",
    ".aws", ".azure", ".docker/config.json", ".netrc", ".git-credentials", ".config/gh/", ".config/nolgia",
    ".mozilla", ".librewolf", ".config/google-chrome", ".config/chromium", ".config/BraveSoftware",
    ".config/solana", ".local/share/keyrings", ".pki", ".config/rclone", ".npmrc", ".pypirc", ".cargo/credentials",
    "zsh-secrets", "private/",
]
SECRET_FILE = re.compile(r"(^|/)(\.env(\..*)?|.*\.pem|.*\.key|id_(rsa|ed25519|ecdsa|dsa)[^/]*|.*keypair.*\.json|"
                         r"credentials(\.json)?|.*token.*|.*secret.*)$", re.I)
SAFE_SSH = re.compile(r"\.ssh/(known_hosts|config|[^/]+\.pub)$")
MONEY = [
    (re.compile(r"(?<!paper-)api\.alpaca\.markets", re.I), "Alpaca live endpoint"),
    (re.compile(r"(trading-api|api\.elections)\.kalshi\.com|kalshi\.com/trade-api", re.I), "Kalshi live endpoint"),
    (re.compile(r"clob\.polymarket\.com|polymarket\.us/.*order|api\.polymarket", re.I), "Polymarket order endpoint"),
    (re.compile(r"api\.(exchange\.)?coinbase\.com|api\.coinbase\.com/api/v3/brokerage", re.I), "Coinbase endpoint"),
    (re.compile(r"/api/live(/|\b)|/live/(arm|enable|go|start|orders?)\b|\barm[-_ ]?live\b|\blive[-_ ]?arm", re.I), "ARBITER live/arm"),
    (re.compile(r"\b(solana\s+transfer|spl-token\s+transfer|cast\s+send|cast\s+wallet|seth\s+send|bitcoin-cli\s+send)", re.I), "moving funds"),
    (re.compile(r"\b(wallet|keypair|mnemonic|seed[-_ ]?phrase|private[-_ ]?key)\b", re.I), "wallet keys"),
]
REDACT = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[redacted private key]"),
    (re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[redacted github token]"),
    (re.compile(r"\b(hvs|hvb|s)\.[A-Za-z0-9]{20,}\b"), "[redacted vault token]"),
    (re.compile(r"\b(sk|rk|pk)-[A-Za-z0-9_\-]{16,}\b"), "[redacted api key]"),
    (re.compile(r"\bnol_[A-Za-z0-9]{16,}\b"), "[redacted nolgia token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted aws key]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "[redacted slack token]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"), "[redacted jwt]"),
    (re.compile(r"(?i)\b([a-z0-9_]*(token|secret|password|passwd|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret)"
                r"[a-z0-9_]*)\s*([=:])\s*(?!\[redacted)(\"[^\"]{6,}\"|'[^']{6,}'|[^\s,;]{6,})"), r"\1\3[redacted]"),
    (re.compile(r"(?i)(authorization:\s*(bearer|basic)\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1[redacted]"),
]
ENV_DROP = re.compile(r"(TOKEN|SECRET|PASSWORD|PASSWD|_KEY$|KEY_ID|PRIVATE|CREDENTIAL|^VAULT_|^AWS_|^GH_|^GITHUB_|"
                      r"^GOOGLE_|^GCLOUD|^AZURE_|^OPENAI|^ANTHROPIC|^NOLGIA|^HF_TOKEN|^KUBECONFIG$|SSH_AUTH_SOCK|^GPG_|"
                      r"^DBUS_SESSION_BUS_ADDRESS$)", re.I)


class Refused(Exception):
    pass


def redact(text):
    for rx, rep in REDACT:
        text = rx.sub(rep, text)
    return text


def enabled():
    return not os.path.exists(OFF)


def set_enabled(on):
    os.makedirs(STATE, exist_ok=True)
    if on and os.path.exists(OFF):
        os.unlink(OFF)
    elif not on:
        open(OFF, "w").close()
    return enabled()


def audit(**rec):
    os.makedirs(STATE, exist_ok=True)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}
    if "command" in rec:
        rec["command"] = redact(rec["command"])
    with open(LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------------ parsing
def words_of(command):
    """Every word the shell would see, including inside $(...) and `...`; recursing into
    `sh -c '...'` strings. Raises Refused when the command can't be parsed confidently."""
    try:
        import bashlex
    except ImportError:
        bashlex = None
    out = []
    if bashlex is not None:
        try:
            trees = bashlex.parse(command)
        except Exception as e:
            raise Refused(f"can't parse that command confidently ({type(e).__name__})")

        class V(bashlex.ast.nodevisitor):
            def visitword(self, node, word):
                out.append(word)

            def visitheredoc(self, node, value):
                out.extend(value.split())
        for t in trees:
            V().visit(t)
    else:
        try:
            out = shlex.split(command, posix=True)
        except ValueError as e:
            raise Refused(f"can't parse that command confidently ({e})")
    # recurse into shell -c strings and eval
    more = []
    for i, w in enumerate(out):
        base = os.path.basename(w)
        if (base in SHELLS and i + 2 < len(out) + 1 and "-c" in out[i + 1:i + 3]) or base == "eval":
            idx = out.index("-c", i) + 1 if "-c" in out[i:i + 3] else i + 1
            if idx < len(out):
                more += words_of(out[idx])
    return out + more


def _script_words(w, cwd, depth):
    """If a word names a readable script, scan its text too (shallow)."""
    if depth > 1:
        return []
    p = os.path.realpath(os.path.join(cwd, os.path.expanduser(w)))
    try:
        if os.path.isfile(p) and os.path.getsize(p) < 256 * 1024:
            with open(p, "rb") as f:
                head = f.read(256 * 1024)
            if b"\0" in head[:4096]:
                return []
            text = head.decode("utf-8", "replace")
            if text.startswith("#!") or p.endswith((".sh", ".bash", ".zsh")):
                try:
                    return words_of(text)
                except Refused:
                    return text.split()
    except OSError:
        pass
    return []


def _path_secret(w, cwd):
    w2 = os.path.expandvars(os.path.expanduser(w.replace("${HOME}", HOME).replace("$HOME", HOME)))
    cands = [w2]
    if not w2.startswith("/"):
        cands.append(os.path.normpath(os.path.join(cwd, w2)))
    for c in cands:
        rel = c[len(HOME) + 1:] if c.startswith(HOME + "/") else c
        if SAFE_SSH.search(c):
            continue
        for sp in SECRET_PATHS:
            if sp in rel or (sp.endswith("/") and rel == sp[:-1]):
                return f"a protected path ({sp.rstrip('/')})"
        if SECRET_FILE.search(c) and ("/" in w or w.startswith(".")):
            return "a secret-looking file"
    return None


def check(command, cwd=HOME):
    """-> None when allowed; raises Refused with the reason."""
    if not command.strip():
        raise Refused("empty command")
    if "\x00" in command or len(command) > 8000:
        raise Refused("command too long or binary")
    cw = os.path.realpath(cwd)
    reason = _path_secret(cw, "/")
    if reason:
        raise Refused(f"working directory is {reason}")
    words = words_of(command)
    for w in list(words):
        words += _script_words(w, cw, 0)
    lowered = [os.path.basename(w).lower() for w in words]
    for w in lowered:
        for part in re.split(r"[\s;|&()`$<>]+", w):
            if part in PRIV or part.startswith("pkexec") or part.endswith("polkit-agent-helper-1"):
                raise Refused(f"privilege escalation ({part}) is not allowed")
    for w in lowered:
        if w in SECRET_CMDS:
            raise Refused(f"the {w} CLI reads secrets; not allowed")
    joined = " ".join(words)
    if re.search(r"\bgcloud\b.*\bsecrets?\b", joined):
        raise Refused("gcloud secrets is not allowed")
    if re.search(r"\b(kubectl|kubecolor|k9s|helm)\b", joined) and re.search(r"\bsecrets?\b|\bsecret/", joined, re.I):
        raise Refused("reading Kubernetes secrets is not allowed")
    if re.search(r"\b(env|printenv|export|set|declare)\b", joined) and re.search(r"/proc/\d+/environ|/proc/self/environ", joined):
        raise Refused("reading another process's environment is not allowed")
    if re.search(r"/proc/[^\s/]+/environ", joined):
        raise Refused("reading process environments is not allowed")
    for w in words:
        r = _path_secret(w, cw)
        if r:
            raise Refused(f"that touches {r}")
    for rx, what in MONEY:
        if rx.search(command) or rx.search(joined):
            raise Refused(f"no real money: {what} is off limits")
    return None


def clean_env():
    env = {k: v for k, v in os.environ.items() if not ENV_DROP.search(k)}
    env.setdefault("HOME", HOME)
    env["PATH"] = env.get("PATH") or "/usr/local/bin:/usr/bin:/bin"
    env["TERM"] = "dumb"
    env["PAGER"] = env["GIT_PAGER"] = "cat"
    env["SYSTEMD_PAGER"] = ""
    env["NO_COLOR"] = "1"
    env["SUDO_ASKPASS"] = "/bin/false"
    return env


# ------------------------------------------------------------------ running
class Runner:
    def __init__(self):
        self.lock = threading.Lock()
        self.current = None        # {"proc", "command", "cwd", "t0"}
        self.on_change = None      # callback(current or None) for the UI

    def kill(self, why="stopped"):
        with self.lock:
            cur = self.current
        if cur and cur["proc"].poll() is None:
            try:
                os.killpg(cur["proc"].pid, signal.SIGTERM)
                time.sleep(0.3)
                if cur["proc"].poll() is None:
                    os.killpg(cur["proc"].pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            cur["killed"] = why
            return True
        return False

    def run(self, command, cwd=None, timeout_s=60):
        cwd = os.path.realpath(os.path.expanduser(cwd or "~"))
        timeout_s = max(1, min(int(timeout_s or 60), 600))
        if not enabled():
            audit(event="refused", command=command, cwd=cwd, reason="shell is off (bromigos-holo shell on)")
            return {"refused": "The terminal is switched off. The host can turn it on with: bromigos-holo shell on"}
        if not os.path.isdir(cwd):
            return {"error": f"no such directory: {cwd}"}
        try:
            check(command, cwd)
        except Refused as e:
            audit(event="refused", command=command, cwd=cwd, reason=str(e))
            return {"refused": str(e)}
        t0 = time.monotonic()
        proc = subprocess.Popen(["/bin/bash", "-c", command], cwd=cwd, env=clean_env(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        cur = {"proc": proc, "command": command, "cwd": cwd, "t0": t0}
        with self.lock:
            self.current = cur
        if self.on_change:
            self.on_change(cur)
        buf = bytearray()
        total = 0

        def reader():
            nonlocal total
            while True:
                b = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(65536)
                if not b:
                    break
                total += len(b)
                if len(buf) < MAX_READ:
                    buf.extend(b[:MAX_READ - len(buf)])
        rt = threading.Thread(target=reader, daemon=True)
        rt.start()
        try:
            proc.wait(timeout_s)
        except subprocess.TimeoutExpired:
            cur["killed"] = f"timed out after {timeout_s} s"
            self.kill(cur["killed"])
        rt.join(2)
        with self.lock:
            self.current = None
        if self.on_change:
            self.on_change(None)
        dur = round(time.monotonic() - t0, 2)
        text = redact(buf.decode("utf-8", "replace"))
        if total > MAX_READ:
            text += f"\n…[{total - MAX_READ} more bytes not read]"
        shown = text if len(text) <= MODEL_CHARS else (text[:MODEL_CHARS // 2] + f"\n…[{len(text) - MODEL_CHARS} chars cut]…\n" + text[-MODEL_CHARS // 2:])
        audit(event="ran", command=command, cwd=cwd, exit=proc.returncode, seconds=dur, out_bytes=total,
              killed=cur.get("killed"))
        out = {"exit": proc.returncode, "seconds": dur, "output": shown}
        if cur.get("killed"):
            out["killed"] = cur["killed"]
        return out


RUNNER = Runner()
