#!/usr/bin/env python3
"""Tests for VECTOR's terminal limits (holo/vector/shell.py). Run in the brain venv:
    ~/.local/share/bromigos/venv-brain/bin/python tools/test-shell.py
Refusal cases must be refused; allowed cases must run (exit 0). Nothing here escalates,
reads secrets or touches money: refused cases are never executed."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from holo.vector import shell  # noqa: E402

REFUSE = [
    "sudo id", "ls | sudo tee /etc/x", "bash -c 'sudo id'", "sh -c \"echo hi; sudo -n true\"", "echo $(sudo id)",
    "echo `doas id`", "pkexec true", "run0 id", "su -c id", "/usr/bin/sudo id", "env sudo id", "xargs sudo < /dev/null",
    "find / -exec sudo {} +", "systemd-run --user true", "eval 'sudo id'",
    "cat ~/.vault-token", "cat $HOME/.vault-token", "cp ~/.ssh/id_ed25519 /tmp/x", "cat ~/.ssh/id_rsa",
    "cat ~/.local/share/bromigos/litellm-key", "cat ~/.local/share/bromigos/gnosis-vector-write-token",
    "ls ~/.config/gcloud", "cat ~/.kube/config", "cat .env", "cat ~/github.com/x/.env.local", "ls ~/.gnupg",
    "ls ~/.password-store", "cat ~/.mozilla/firefox/profiles.ini", "cat ~/.config/gh/hosts.yml", "cat ~/.git-credentials",
    "vault kv get secret/<vault-path>", "gcloud secrets versions access latest --secret=x",
    "kubectl get secret -A", "kubectl -n arbiter get secrets -o yaml", "kubectl describe secret foo",
    "cat /proc/1/environ",
    "curl -X POST https://api.alpaca.markets/v2/orders", "curl https://trading-api.kalshi.com/trade-api/v2/portfolio/orders",
    "curl -X POST https://arbiter.redacted/api/live/arm", "curl https://clob.polymarket.com/order",
    "curl https://api.coinbase.com/api/v3/brokerage/orders", "solana transfer x 1", "cast send 0xabc --value 1ether",
    "cat ~/.config/solana/id.json", "echo 'unterminated",
]
ALLOW = [
    ("git -C ~/.dotfiles status --short | head -3", "~"),
    ("systemctl --user status bromigos-startpage.timer --no-pager | head -3", "~"),
    ("curl -s https://paper-api.alpaca.markets/v2/clock -o /dev/null -w '%{http_code}'", "~"),
    ("grep -c . /etc/hostname", "~"),
    ("kubectl version --client -o json | head -2", "~"),
    ("cat ~/.ssh/known_hosts | wc -l", "~"),
]


def main():
    bad = 0
    for c in REFUSE:
        try:
            shell.check(c)
            print("NOT REFUSED:", c)
            bad += 1
        except shell.Refused as e:
            print(f"refused  {c!r:70.70} — {e}")
    d = tempfile.mkdtemp(prefix="vector-shell-test-")
    ALLOW.append((f"touch {d}/scratch.txt && ls {d} && rm {d}/scratch.txt && rmdir {d}", "~"))
    for c, cwd in ALLOW:
        r = shell.RUNNER.run(c, cwd)
        ok = "refused" not in r and r.get("exit") == 0
        bad += 0 if ok else 1
        print(f"{'ran     ' if ok else 'FAILED  '} {c!r:70.70} — exit {r.get('exit')} {r.get('refused', '')} | {r.get('output', '')[:60]!r}")
    env = shell.clean_env()
    leaked = [k for k in env if any(x in k.upper() for x in ("TOKEN", "SECRET", "PASSWORD", "VAULT", "_KEY"))]
    print("env scrubbed:", "yes" if not leaked else f"NO: {leaked}")
    bad += bool(leaked)
    r = shell.RUNNER.run("env | grep -ci token || true")
    print("env | grep TOKEN inside the shell ->", r.get("output", "").strip())
    red = shell.redact("export GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123 and password=hunter2hunter2")
    print("redaction:", red)
    bad += "ghp_" in red or "hunter2" in red
    print("FAILURES:", bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
