#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 itsAllexB
"""Generate the APT index (Packages*, Release) and the Sileo depictions, then the web pages.

Reads every debs/*.deb (control fields via `dpkg-deb -f`) and meta/packages.json.
Only the Python standard library and dpkg-deb are needed, so this runs on macOS
(Homebrew dpkg) and on the Ubuntu GitHub Actions runner alike. Signing is done by
scripts/build-repo.sh. The web pages (index.html, depictions/*.html, add/*.html) are in
scripts/gen_site.py; their stylesheet is depictions/style.css, edited by hand.
"""

import argparse
import bz2
import email.utils
import gzip
import hashlib
import io
import json
import lzma
import os
import re
import subprocess
import sys

from gen_site import bullets_md, image_size, write_if_changed, write_site

# Order used when writing control stanzas (remaining fields follow alphabetically).
FIELD_ORDER = [
    "Package", "Name", "Version", "Architecture", "Description", "Maintainer", "Author",
    "Section", "Depends", "Pre-Depends", "Conflicts", "Replaces", "Provides", "Breaks",
    "Installed-Size", "Homepage", "Depiction", "SileoDepiction", "Icon",
    "Filename", "Size", "MD5sum", "SHA1", "SHA256",
]


def die(msg):
    sys.exit(f"gen_repo: error: {msg}")


def parse_control(text):
    fields, key = {}, None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] in " \t" and key:
            fields[key] += "\n" + line
        else:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
    return fields


def deb_control(path):
    try:
        out = subprocess.run(["dpkg-deb", "-f", path], check=True, capture_output=True, text=True).stdout
    except FileNotFoundError:
        die("dpkg-deb not found (macOS: brew install dpkg; Debian/Ubuntu: apt-get install dpkg)")
    except subprocess.CalledProcessError as e:
        die(f"{path}: not a valid .deb ({e.stderr.strip()})")
    return parse_control(out)


def version_key(v):
    """Rough Debian version ordering (good enough to pick the newest of our own versions)."""
    epoch, _, rest = v.rpartition(":") if ":" in v else ("0", "", v)
    parts = re.findall(r"\d+|[A-Za-z]+|[~]|[^\dA-Za-z~]+", rest)
    key = [int(epoch or 0)]
    for p in parts:
        if p.isdigit():
            key.append((2, int(p), ""))
        elif p == "~":
            key.append((0, 0, ""))
        else:
            key.append((1, 0, p))
    key.append((1, 0, ""))
    return key


def file_hashes(data):
    return {
        "MD5sum": hashlib.md5(data).hexdigest(),
        "SHA1": hashlib.sha1(data).hexdigest(),
        "SHA256": hashlib.sha256(data).hexdigest(),
        "SHA512": hashlib.sha512(data).hexdigest(),
    }


# --- outputs ---

def sileo_depiction(pkg, ctl, meta, base, size):
    shots_dir = f"depictions/screenshots/{meta['short']}"
    groups = {}
    for s in meta.get("screenshots", []):
        w, h = image_size(os.path.join(shots_dir, s["file"]))
        kind = "portrait" if h > w * 1.1 else ("landscape" if w > h * 1.1 else "square")
        groups.setdefault(kind, []).append((s, w, h))
    shot_views = []
    for kind in ("portrait", "landscape", "square"):
        items = groups.get(kind)
        if not items:
            continue
        height = 220 if kind == "landscape" else 300
        ratio = sum(w / h for _, w, h in items) / len(items)
        shot_views.append({
            "class": "DepictionScreenshotsView",
            "itemCornerRadius": 8,
            "itemSize": f"{{{round(height * ratio)}, {height}}}",
            "screenshots": [
                {"url": f"{base}{shots_dir}/{s['file']}", "accessibilityText": s.get("alt", "")}
                for s, _, _ in items
            ],
        })
    repo_url = f"https://github.com/{meta['github']}"
    details = [
        {"class": "DepictionSubheaderView", "title": meta["tagline"], "useBoldText": True},
        {"class": "DepictionMarkdownView", "markdown": meta["description"], "useSpacing": True},
        *shot_views,
        {"class": "DepictionHeaderView", "title": "Features"},
        {"class": "DepictionMarkdownView", "markdown": bullets_md(meta["features"]), "useSpacing": True},
        {"class": "DepictionHeaderView", "title": "Settings"},
        {"class": "DepictionMarkdownView", "markdown": meta["settings"], "useSpacing": True},
        {"class": "DepictionHeaderView", "title": "Compatibility"},
        {"class": "DepictionMarkdownView", "markdown": bullets_md(meta["compatibility"]), "useSpacing": True},
        {"class": "DepictionSeparatorView"},
        {"class": "DepictionTableTextView", "title": "Version", "text": ctl["Version"]},
        {"class": "DepictionTableTextView", "title": "Developer", "text": ctl.get("Author", "itsAllexB")},
        {"class": "DepictionTableTextView", "title": "Size", "text": f"{max(1, round(size / 1024))} KB"},
        {"class": "DepictionTableTextView", "title": "License", "text": "GPL-3.0"},
        {"class": "DepictionTableButtonView", "title": "Source Code", "action": repo_url, "openExternal": True},
        {"class": "DepictionTableButtonView", "title": "Report a Problem", "action": f"{repo_url}/issues", "openExternal": True},
        {"class": "DepictionSpacerView", "spacing": 12},
        {"class": "DepictionLabelView", "text": "Unofficial. Not affiliated with or endorsed by Apple.", "fontSize": 12, "alignment": 1, "textColor": "#8E8E93"},
    ]
    changelog = []
    for entry in meta.get("changelog", []):
        changelog.append({"class": "DepictionSubheaderView", "title": f"Version {entry['version']}", "useBoldText": True})
        changelog.append({"class": "DepictionMarkdownView", "markdown": bullets_md(entry["changes"]), "useSpacing": True})
    return {
        "minVersion": "0.1",
        "class": "DepictionTabView",
        "tintColor": meta.get("tint", "#3478F6"),
        "tabs": [
            {"tabname": "Details", "class": "DepictionStackView", "views": details},
            {"tabname": "Changelog", "class": "DepictionStackView", "views": changelog},
        ],
    }


def readme_table(latest, meta_all):
    """Package table for README.md, between the packages:start/end markers."""
    rows = ["| Package | Version | What it does |", "| --- | --- | --- |"]
    for pkg in sorted(latest, key=lambda p: latest[p][0].get("Name", p).lower()):
        ctl, _ = latest[pkg]
        m = meta_all["packages"].get(pkg, {})
        if m.get("transitional"):  # empty upgrade packages stay in Packages but aren't listed
            continue
        name = ctl.get("Name", pkg)
        link = f"[{name}](https://github.com/{m['github']})" if m.get("github") else name
        tagline = m.get("tagline") or ctl.get("Description", "").split("\n")[0]
        rows.append(f"| {link} | {ctl['Version']} | {tagline} |")
    return "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=os.environ.get("REPO_URL", "https://itsallexb.github.io/ios-legacy/"))
    ap.add_argument("--fingerprint", default="", help="signing key fingerprint shown on index.html")
    args = ap.parse_args()
    base = args.url if args.url.endswith("/") else args.url + "/"

    with open("meta/packages.json") as f:
        meta_all = json.load(f)
    repo = meta_all["repo"]

    debs = sorted(f for f in os.listdir("debs") if f.endswith(".deb"))
    if not debs:
        die("no .deb files in debs/")
    stanzas, seen, latest = [], {}, {}
    for name in debs:
        path = os.path.join("debs", name)
        with open(path, "rb") as f:
            data = f.read()
        ctl = deb_control(path)
        pkg, ver = ctl.get("Package"), ctl.get("Version")
        if not pkg or not ver:
            die(f"{path}: missing Package or Version")
        if (pkg, ver) in seen:
            die(f"{pkg} {ver} is in both {seen[(pkg, ver)]} and {name}; keep only one")
        seen[(pkg, ver)] = name
        m = meta_all["packages"].get(pkg)
        if m:
            ctl.setdefault("Depiction", f"{base}depictions/{pkg}.html")
            ctl.setdefault("SileoDepiction", f"{base}depictions/{pkg}.json")
            ctl.setdefault("Homepage", f"https://github.com/{m['github']}")
            if os.path.exists(f"icons/{pkg}.png"):
                ctl.setdefault("Icon", f"{base}icons/{pkg}.png")
        h = file_hashes(data)
        ctl.update({"Filename": f"debs/{name}", "Size": str(len(data)),
                    "MD5sum": h["MD5sum"], "SHA1": h["SHA1"], "SHA256": h["SHA256"]})
        keys = [k for k in FIELD_ORDER if k in ctl] + sorted(k for k in ctl if k not in FIELD_ORDER)
        stanzas.append((pkg, version_key(ver), "\n".join(f"{k}: {ctl[k]}" for k in keys)))
        if pkg not in latest or version_key(ver) > version_key(latest[pkg][0]["Version"]):
            latest[pkg] = (ctl, len(data))

    stanzas.sort(key=lambda s: (s[0], s[1]))
    packages = ("\n\n".join(s[2] for s in stanzas) + "\n").encode()

    index_files = {"Packages": packages}
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0, filename="") as g:
        g.write(packages)
    index_files["Packages.gz"] = buf.getvalue()
    index_files["Packages.bz2"] = bz2.compress(packages, 9)
    index_files["Packages.xz"] = lzma.compress(packages, preset=9 | lzma.PRESET_EXTREME)
    for name, data in index_files.items():
        write_if_changed(name, data)

    release = [
        f"Origin: {repo['name']}",
        f"Label: {repo['name']}",
        "Suite: stable",
        "Version: 1.0",
        "Codename: ios",
        "Architectures: iphoneos-arm",
        "Components: main",
        f"Description: {repo['description']}",
        f"Date: {email.utils.formatdate(usegmt=True)}",
    ]
    for algo in ("MD5Sum", "SHA1", "SHA256", "SHA512"):
        release.append(f"{algo}:")
        hk = "MD5sum" if algo == "MD5Sum" else algo
        for name in ("Packages", "Packages.gz", "Packages.bz2", "Packages.xz"):
            data = index_files[name]
            release.append(f" {file_hashes(data)[hk]} {len(data):>8} {name}")
    with open("Release", "w") as f:
        f.write("\n".join(release) + "\n")

    for pkg, (ctl, size) in latest.items():
        m = meta_all["packages"].get(pkg)
        if not m:
            print(f"gen_repo: warning: no meta/packages.json entry for {pkg}; no depiction generated", file=sys.stderr)
            continue
        write_if_changed(f"depictions/{pkg}.json", json.dumps(sileo_depiction(pkg, ctl, m, base, size), indent=2) + "\n")
    write_site(latest, meta_all, base, args.fingerprint)
    with open("README.md") as f:
        readme = f.read()
    start, end = "<!-- packages:start -->\n", "<!-- packages:end -->"
    if start in readme and end in readme:
        head, rest = readme.split(start, 1)
        readme = head + start + readme_table(latest, meta_all) + end + rest.split(end, 1)[1]
        write_if_changed("README.md", readme.encode())

    for pkg, (ctl, _) in sorted(latest.items()):
        print(f"  {pkg} {ctl['Version']}")
    print(f"gen_repo: {len(stanzas)} package version(s) indexed")


if __name__ == "__main__":
    main()
