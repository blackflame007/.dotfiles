#!/usr/bin/env bash
# Snapshots for the workstation (run once as root: sudo bash setup-snapshots.sh).
#
#   system drive (btrfs, nvme1n1p2)  snapper: @ (root) and @home, kept ~2 weeks
#     - before/after every pacman transaction (snap-pac)
#     - before system-level changes VECTOR makes (he calls `snapper create`)
#     - one daily timeline snapshot, 14 kept
#   boot menu                         grub-btrfs: boot any root snapshot from GRUB
#   off-drive copy                    btrbk: daily root snapshot sent as incremental
#                                     stream files to /mnt/Data/btrbk (ext4), 14 days
#
# Idempotent: safe to re-run. Config lives next to this script in the dotfiles.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
HERE="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="${SUDO_USER:-blackflame}"

pacman -S --needed --noconfirm snapper snap-pac grub-btrfs inotify-tools btrbk

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

# --- btrbk: off-drive copy of root to /mnt/Data -------------------------------
install -d -m 700 /mnt/Data/btrbk
install -d -m 755 /mnt/btrfs-top
grep -q '/mnt/btrfs-top' /etc/fstab || \
  echo "UUID=$(findmnt -no UUID /) /mnt/btrfs-top btrfs rw,noatime,subvolid=5,noauto,x-systemd.automount 0 0" >> /etc/fstab
systemctl daemon-reload
ls /mnt/btrfs-top >/dev/null            # trigger the automount
install -d /mnt/btrfs-top/@btrbk_snaps  # btrbk's snapshot dir, outside @ so it isn't nested
install -m 644 "$HERE/btrbk.conf" /etc/btrbk/btrbk.conf

# --- timers and boot menu -----------------------------------------------------
systemctl enable --now snapper-timeline.timer snapper-cleanup.timer
systemctl enable --now grub-btrfsd.service
systemctl enable --now btrbk.timer
grub-mkconfig -o /boot/grub/grub.cfg

snapper -c root create -c number -d "snapshots set up" --userdata important=yes
echo "--- done"
snapper list-configs
btrbk -c /etc/btrbk/btrbk.conf dryrun | tail -n 5 || true
