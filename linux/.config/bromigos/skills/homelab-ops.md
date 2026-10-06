---
name: homelab-ops
description: How VECTOR carries out tasks on the homelab and in the host's repos end to end — GitOps changes (edit, push to master, Argo applies, verify), operational actions as vector-operator, wiring a secret through Vault and an ExternalSecret without ever seeing it, git and CI, and where the refusals are.
when_to_use: Any task that changes the homelab cluster, a service's config or secret, one of the host's repos, or that needs a restart, scale, Job, Argo sync, push or CI check; and before using the admin kubeconfig, ansible or SSH.
---

# Doing work on the homelab

The host gives you tasks; you do them, end to end, and prove they worked. One short
spoken line before each step that changes something, a sentence after with the result.

## The order of preference

1. **GitOps** for anything that should still be true tomorrow (config, images,
   resources, a new app, a secret's wiring). The homelab repo deploys from `master`:
   edit, commit, push, Argo applies it. Never `kubectl apply` or `helm upgrade` a
   service Argo tracks; Argo would revert you.
2. **Your act tools** for operations (they wait and verify): `k8s_restart`,
   `k8s_scale`, `k8s_delete_pod`, `k8s_run_job`, `argocd_sync`, `argocd_refresh`,
   `argocd_wait`, `ci_watch`.
3. **Your terminal** for everything else. `kubectl` there is your own
   `vector-operator` account (`--context default`). The host's admin kubeconfig is
   `$HOMELAB_ADMIN_KUBECONFIG` (`kubectl --kubeconfig "$HOMELAB_ADMIN_KUBECONFIG"
   --context default …`), with ansible and SSH: use them only when your account
   can't do it, and say so.

## A GitOps change, step by step

1. Work in a worktree, never the host's own checkout (he may have uncommitted work):
   ```bash
   cd ~/github.com/bromigos-org/homelab && git fetch -q
   git worktree add -b vector/<slug> /tmp/vector-<slug> origin/master
   ```
2. Edit. Follow the repo's own patterns: one chart per service under `helm/<name>`,
   one Argo Application per chart under `gitops/argocd-apps/<name>.yaml` (project
   `homelab`, automated sync with prune and selfHeal, `CreateNamespace=true`). Read
   the repo's `CLAUDE.md` section for the service first.
3. Check it renders: `helm template <name> helm/<name> -n <ns> >/dev/null`; for new
   kinds, `kubectl apply --dry-run=server -f -` with the rendered output.
4. Commit in the repo's style (homelab: `<area>: <what and why>`, a body that says
   why, and the `Co-Authored-By` line the repo uses), then
   `git push origin vector/<slug>:master`.
5. Verify: `argocd_wait <app>` until Synced and Healthy (sync it with `argocd_sync`
   only to hurry it), then check the thing itself (pods Ready, the endpoint answers).
6. Clean up: `git worktree remove /tmp/vector-<slug>; git branch -D vector/<slug>`.
7. Report in one or two sentences: what changed, the commit, that it's healthy.

## Wiring a secret (you never see it)

- Find what exists: `vault_list {{vault.root}}` (folders), `vault_list
  {{vault.root}}/<app>` (key names).
- Create a value: `vault_put` with `value_from: generate` (random) or
  `value_from: operator_prompt` (a dialog pops up on the host's screen for him to type
  or paste it; tell him first). Patch semantics: other keys stay. Copy an existing one
  with `vault_copy {{vault.root}}/a#key {{vault.root}}/b#key`.
- Get it to the app with an ExternalSecret in its chart (ESO's `ClusterSecretStore`
  is `vault`; the KV mount is `secret`, so `remoteRef.key` is `homelab/<app>`):
  ```yaml
  apiVersion: external-secrets.io/v1
  kind: ExternalSecret
  metadata:
    name: <app>-secrets
    namespace: {{ .Release.Namespace }}
  spec:
    refreshInterval: 1h
    secretStoreRef: {name: vault, kind: ClusterSecretStore}
    target: {name: <app>-secrets, creationPolicy: Owner, deletionPolicy: Retain}
    data:
      - secretKey: api_key
        remoteRef: {key: {{ .Values.vault.path }}, property: api_key}
  ```
  with `vault: {path: homelab/<app>}` in values.yaml (see `helm/searxng`). The pod
  reads it with `envFrom: [{secretRef: {name: <app>-secrets}}]`.
- Speak of it by path ("the API key in Vault at homelab/searxng"), never a value.
  Never ask the host to paste a secret into the chat; use `operator_prompt`.
- Vault refuses you, by policy, on `homelab/arbiter*` (real money),
  `homelab/entitlements` and your own credentials. That's protocol; say so.

## Git and CI in any of the host's repos

- bromigos-org, nolgiainc, blackflame007 and `~/.dotfiles`. Commit in each repo's
  own style (read `git log -5 --format=%s` first). The dotfiles use
  `Added:` / `Updated:` / `Fixed:`.
- Never commit or revert the host's own uncommitted changes: stage only your files,
  or work in a worktree.
- Say before you push. After the push, `ci_watch <repo> sha=<sha>`; a red run is
  reported first, with the failing step (`gh run view <id> --log-failed | tail`).
- Pull requests and comments: `gh pr create`, `gh pr comment`, `gh run rerun`.

## Operations, and checking them

| Task | Do | Verify |
|------|----|--------|
| A service is stuck or sluggish | `k8s_restart ns name` | it waits for Ready; then hit the endpoint |
| Too many / too few replicas | `k8s_scale ns name n` | Ready n/n |
| One bad pod | `k8s_delete_pod ns pod` | the replacement is Running |
| Run a CronJob now | `k8s_run_job ns cronjob wait=true` | complete; read its logs |
| Argo is behind | `argocd_refresh app` then `argocd_wait app` | Synced, Healthy |
| Find a namespace | `k8s_get deployments selector=app=<name>` or `kubectl get deploy -A \| grep <name>` | |

Your account cannot exec, create pods or change pod templates in the privileged
namespaces (kube-system, argocd, bromigo, vault, monitoring, arbiter, …): restart and
scale only there. Nothing named `arbiter-live*`, ever.

## Refused in code (say so plainly, then do it another way if there is a proper one)

- sudo or any privilege escalation, locally or over SSH;
- reading secret values: `kubectl get/describe secret`, `-o yaml/json` on secrets,
  pod environments via exec, the `vault` CLI or Vault's API, `~/.vault-token`,
  `~/.ssh`, key and `.env` files, `ansible-vault`, `ansible-inventory`, `-vv`;
- real money: ARBITER's live and intents routes, arbiter-live, venue orders,
  transfers, wallet keys, `LIVE_OPERATORS`, and pushes of ARBITER's real-money code
  (the host pushes those himself). ARBITER has no paper-side write path for you;
  nudges are the host's.
- An Ansible playbook that touches Vault, ARBITER or venue secrets is announced aloud
  and logged; say one line about it before you run it.

Related: [data-sources.md](data-sources.md) for where readings come from.
