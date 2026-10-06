# VECTOR's changelog: changes outside any repo

VECTOR (the desktop assistant) records here every change he makes that git can't
track by itself: a Vault entry, an imperative change to a live cluster object, a
package installed in user space, a config outside the dotfiles. Newest first, one
entry per change:

```
## YYYY-MM-DD HH:MM — <what>
- where: <path, Vault path, namespace/kind/name, package>
- why: <the task>
- undo: <how>
```

Changes inside a repo are committed and pushed there instead; this file is not a
substitute for git. Never write a secret value here.
