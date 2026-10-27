#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 itsAllexB
#
# Rebuild the APT index (Packages, Packages.gz/.bz2/.xz, Release), the depictions and
# index.html from debs/ + meta/packages.json, then sign Release (Release.gpg, InRelease).
#
# Signing key (first one found):
#   GPG_PRIVATE_KEY   ASCII-armored private key in an environment variable (GitHub Actions secret)
#   GPG_KEY_FILE      path to an ASCII-armored private key file
#                     (default: ~/.config/ios-legacy/ios-legacy-private.asc)
# GPG_PASSPHRASE      passphrase for the key, if it has one
# ALLOW_UNSIGNED=1    build without signing when no key is available (not for publishing)
# REPO_URL            public URL of the repo (default: https://itsallexb.github.io/ios-legacy/)
#
# Needs: bash, python3, dpkg-deb, gpg (+ gpgv). macOS: brew install dpkg gnupg
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_URL="${REPO_URL:-https://itsallexb.github.io/ios-legacy/}"
PUBKEY="$PWD/ios-legacy.gpg"

for tool in python3 dpkg-deb gpg gpgv; do
    command -v "$tool" >/dev/null || { echo "build-repo: $tool is required" >&2; exit 1; }
done

# Throwaway GnuPG home so no key ever lands in a persistent keyring.
GNUPGHOME=$(mktemp -d)
export GNUPGHOME
cleanup() { gpgconf --kill all >/dev/null 2>&1 || true; rm -rf "$GNUPGHOME"; }
trap cleanup EXIT
chmod 700 "$GNUPGHOME"

# Fingerprint of the committed public key: the only key allowed to sign.
FPR=$(gpg --batch --with-colons --import-options show-only --import "$PUBKEY" 2>/dev/null | awk -F: '/^fpr/ {print $10; exit}')
[ -n "$FPR" ] || { echo "build-repo: cannot read $PUBKEY" >&2; exit 1; }

python3 scripts/gen_repo.py --url "$REPO_URL" --fingerprint "$FPR"

rm -f Release.gpg InRelease
KEY_FILE="${GPG_KEY_FILE:-$HOME/.config/ios-legacy/ios-legacy-private.asc}"
if [ -n "${GPG_PRIVATE_KEY:-}" ]; then
    KEY_SOURCE=env
elif [ -f "$KEY_FILE" ]; then
    KEY_SOURCE=file
elif [ "${ALLOW_UNSIGNED:-0}" = 1 ]; then
    echo "build-repo: WARNING: no signing key, Release is NOT signed (ALLOW_UNSIGNED=1)" >&2
    exit 0
else
    echo "build-repo: no signing key (set GPG_PRIVATE_KEY or GPG_KEY_FILE, or ALLOW_UNSIGNED=1)" >&2
    exit 1
fi

if [ "$KEY_SOURCE" = env ]; then
    printf '%s\n' "$GPG_PRIVATE_KEY" | gpg --batch --quiet --import
else
    gpg --batch --quiet --import "$KEY_FILE"
fi
gpg --batch --list-secret-keys --with-colons | grep -q "^fpr:::::::::$FPR:" || {
    echo "build-repo: the private key does not match ios-legacy.gpg ($FPR)" >&2
    exit 1
}

sign() {
    if [ -n "${GPG_PASSPHRASE:-}" ]; then
        printf '%s' "$GPG_PASSPHRASE" | gpg --batch --yes --pinentry-mode loopback --passphrase-fd 0 \
            --local-user "$FPR" --digest-algo SHA256 "$@"
    else
        gpg --batch --yes --pinentry-mode loopback --passphrase '' \
            --local-user "$FPR" --digest-algo SHA256 "$@"
    fi
}
sign --armor --detach-sign --output Release.gpg Release
sign --clearsign --output InRelease Release

# Check both signatures the way apt does (gpgv against the published key only).
gpgv --quiet --keyring "$PUBKEY" Release.gpg Release
gpgv --quiet --keyring "$PUBKEY" InRelease
echo "build-repo: signed with $FPR"
