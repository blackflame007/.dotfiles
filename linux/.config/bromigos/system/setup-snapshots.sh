#!/usr/bin/env bash
# Snapshots for the workstation (run once as root: sudo bash setup-snapshots.sh).
#
#   system drive (btrfs, nvme1n1p2)  snapper: @ (root) and @home, kept ~2 weeks
#     - before/after every pacman transaction (snap-pac)
#     - before system-level changes VECTOR makes (he calls `snapper create`)
#     - one daily timeline snapshot, 14 kept
#   boot menu                         grub-btrfs: boot any root snapshot from GRUB
#   off-drive copy                    btrbk: daily @ and @home sent as incremental
#                                     zstd stream files to the NAS (NFS automount at
#                                     /mnt/nas-backups, raw target), a full weekly,
#                                     14 days kept; skipped with a log line when the
#                                     NAS is unreachable (btrbk-nas, next to this file)
#
# The NAS export is private, so it is not in this (public) repo. It comes from
#   --nas-export HOST:/export/path            (argument), or
#   [nas] backup_export = "HOST:/export/path" in ~/.config/bromigos/private/config.toml
# Without either, the snapshots are still set up and the off-drive copy is skipped.
#
# Idempotent: safe to re-run. Config lives next to this script in the dotfiles.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="${SUDO_USER:-blackflame}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
NAS_MNT=/mnt/nas-backups
NAS_EXPORT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --nas-export) NAS_EXPORT="${2:?--nas-export needs HOST:/path}"; shift 2;;
    --nas-export=*) NAS_EXPORT="${1#*=}"; shift;;
    *) echo "unknown argument: $1"; exit 2;;
  esac
done
PRIVATE_CONF="$USER_HOME/.config/bromigos/private/config.toml"
if [ -z "$NAS_EXPORT" ] && [ -f "$PRIVATE_CONF" ]; then
  NAS_EXPORT="$(python3 -c 'import sys,tomllib; print(tomllib.load(open(sys.argv[1],"rb")).get("nas",{}).get("backup_export",""))' "$PRIVATE_CONF")"
fi
case "$NAS_EXPORT" in ""|*:/*) ;; *) echo "NAS export must look like HOST:/path"; exit 2;; esac

pacman -S --needed --noconfirm snapper snap-pac grub-btrfs inotify-tools btrbk nfs-utils python

# --- keep rebuildable bulk out of the root snapshots ---------------------------
# Container images are rebuildable and can be 100+ GB; as their own subvolumes they
# are skipped by root snapshots and by the off-drive copy (snapshots don't cross
# subvolume boundaries). The copy uses reflinks, so it's instant and needs no space.
for d in /var/lib/docker /var/lib/containers; do
  [ -d "$d" ] || continue
  if [ "$(stat -f -c %T "$d")" = btrfs ] && btrfs subvolume show "$d" >/dev/null 2>&1; then
    continue                                        # already a subvolume
  fi
  echo "--- making $d its own subvolume ($(du -sh "$d" | cut -f1))"
  svc=""; case "$d" in */docker) svc="docker.service docker.socket containerd.service";; esac
  [ -n "$svc" ] && systemctl stop $svc 2>/dev/null || true
  mv "$d" "$d.old"
  btrfs subvolume create "$d"
  cp -a --reflink=always "$d.old/." "$d/"
  rm -rf "$d.old"
  [ -n "$svc" ] && systemctl start docker.service 2>/dev/null || true
done
echo "--- root without container images: $(du -sxh / 2>/dev/null | cut -f1)"

# --- snapper: root ----------------------------------------------------------
# The archinstall layout already mounts @.snapshots at /.snapshots, which stops
# `snapper create-config` (it wants to create .snapshots itself). Standard dance:
# let snapper create its config, drop the nested subvolume it makes, remount ours.
if [ ! -f /etc/snapper/configs/root ]; then
  umount /.snapshots
  rmdir /.snapshots
  snapper -c root create-config /
  btrfs subvolume delete /.snapshots
  mkdir /.snapshots
  mount /.snapshots           # from fstab: subvol=/@.snapshots
fi
chmod 750 /.snapshots

# --- snapper: home ----------------------------------------------------------
[ -f /etc/snapper/configs/home ] || snapper -c home create-config /home

# Retention: about two weeks, nothing hourly (operator, 2026-10-06).
for c in root home; do
  snapper -c "$c" set-config \
    ALLOW_USERS="$USER_NAME" SYNC_ACL=yes \
    TIMELINE_CREATE=yes TIMELINE_CLEANUP=yes \
    TIMELINE_MIN_AGE=1800 \
    TIMELINE_LIMIT_HOURLY=0 TIMELINE_LIMIT_DAILY=14 TIMELINE_LIMIT_WEEKLY=2 \
    TIMELINE_LIMIT_MONTHLY=0 TIMELINE_LIMIT_YEARLY=0 \
    NUMBER_CLEANUP=yes NUMBER_MIN_AGE=1800 NUMBER_LIMIT=20 NUMBER_LIMIT_IMPORTANT=6
done
# /home holds big model caches and venvs; skip them from the home snapshots by
# making them their own subvolumes later if space gets tight (snapshots don't
# cross subvolume boundaries).

# --- btrbk: off-drive copy of @ and @home to the NAS --------------------------
install -d -m 755 /mnt/btrfs-top
grep -q '/mnt/btrfs-top' /etc/fstab || \
  echo "UUID=$(findmnt -no UUID /) /mnt/btrfs-top btrfs rw,noatime,subvolid=5,noauto,x-systemd.automount 0 0" >> /etc/fstab
mkdir -p "$NAS_MNT"     # no chmod: on a re-run this is the live NFS mount
if [ -n "$NAS_EXPORT" ]; then
  # NFS automount that can never hang the desktop: mounted on first access,
  # unmounted after 10 idle minutes (no long-lived mount to go stale), soft
  # with a bounded retry (~1 min) so a dead NAS returns errors instead of
  # D-state threads. nfsvers=3/tcp like the k3s nodes; nolock (no statd).
  NAS_OPTS="nfsvers=3,proto=tcp,soft,timeo=100,retrans=2,nolock,noatime,noauto,x-systemd.automount,x-systemd.idle-timeout=10min,x-systemd.mount-timeout=30s,_netdev,nofail"
  NAS_LINE="$NAS_EXPORT $NAS_MNT nfs $NAS_OPTS 0 0"
  if ! grep -qxF "$NAS_LINE" /etc/fstab; then
    awk -v m="$NAS_MNT" '$2 != m' /etc/fstab > /etc/fstab.new   # drop an older line for the mount
    echo "$NAS_LINE" >> /etc/fstab.new
    cat /etc/fstab.new > /etc/fstab && rm -f /etc/fstab.new
  fi
fi
systemctl daemon-reload
ls /mnt/btrfs-top >/dev/null            # trigger the automount
install -d /mnt/btrfs-top/@btrbk_snaps  # btrbk's snapshot dir, outside @ so it isn't nested
install -d /etc/btrbk /usr/local/lib/bromigos /etc/systemd/system/btrbk.service.d
install -m 644 "$HERE/btrbk.conf" /etc/btrbk/btrbk.conf
install -m 755 "$HERE/btrbk-nas" /usr/local/lib/bromigos/btrbk-nas
cat > /etc/systemd/system/btrbk.service.d/nas.conf <<'EOF'
# From setup-snapshots.sh (dotfiles): skip cleanly when the NAS is away,
# weekly full send, prune raw chains past 14 days.
[Service]
ExecCondition=/usr/local/lib/bromigos/btrbk-nas check
ExecStart=
ExecStart=/usr/local/lib/bromigos/btrbk-nas run
EOF
systemctl daemon-reload
NAS_OK=no
if [ -n "$NAS_EXPORT" ]; then
  systemctl start "$(systemd-escape -p --suffix=automount "$NAS_MNT")"
  # root is squashed on the share; the target dir is created as the squash user
  if timeout 90 mkdir -p "$NAS_MNT/btrbk"; then
    NAS_OK=yes
    echo "--- NAS target: $(timeout 30 df -h "$NAS_MNT" | tail -1)"
  else
    echo "!!! NAS export $NAS_EXPORT not reachable: off-drive copy stays off until it is (re-run this script)"
  fi
else
  echo "!!! no NAS export (--nas-export or [nas] backup_export in $PRIVATE_CONF): off-drive copy not enabled"
fi
if [ -d /mnt/Data/btrbk ]; then
  echo "!!! /mnt/Data/btrbk is the old off-drive target and is no longer used: delete it with"
  echo "      sudo rm -rf /mnt/Data/btrbk"
fi

# --- timers and boot menu -----------------------------------------------------
systemctl enable --now snapper-timeline.timer snapper-cleanup.timer
systemctl enable --now grub-btrfsd.service
if [ "$NAS_OK" = yes ]; then systemctl enable --now btrbk.timer; else systemctl disable --now btrbk.timer 2>/dev/null || true; fi
grub-mkconfig -o /boot/grub/grub.cfg

snapper -c root create -c number -d "snapshots set up" --userdata important=yes
echo "--- done"
snapper list-configs
if [ "$NAS_OK" = yes ]; then
  btrbk -c /etc/btrbk/btrbk.conf dryrun | tail -n 8 || true
  echo "--- first copy: sudo systemctl start btrbk.service  (a full send of @ and @home; hours)"
fi
