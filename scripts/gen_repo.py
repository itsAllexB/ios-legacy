#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 itsAllexB
"""Generate the APT index (Packages*, Release), the package depictions and index.html.

Reads every debs/*.deb (control fields via `dpkg-deb -f`) and meta/packages.json.
Only the Python standard library and dpkg-deb are needed, so this runs on macOS
(Homebrew dpkg) and on the Ubuntu GitHub Actions runner alike. Signing is done by
scripts/build-repo.sh.
"""

import argparse
import bz2
import email.utils
import gzip
import hashlib
import html
import io
import json
import lzma
import os
import re
import struct
import subprocess
import sys

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


def image_size(path):
    with open(path, "rb") as f:
        head = f.read(26)
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return struct.unpack(">II", head[16:24])
        if head[:2] == b"\xff\xd8":
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    break
                length = struct.unpack(">H", f.read(2))[0]
                if marker[1] in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">xHH", f.read(5))
                    return w, h
                f.seek(length - 2, 1)
    die(f"cannot read image size of {path}")


# --- tiny Markdown subset (paragraphs, "- " lists, **bold**, *italic*, `code`, [text](url)) ---

def md_inline(text):
    out = html.escape(text, quote=False)
    out = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", out)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    return out


def md_to_html(md):
    blocks = []
    for block in re.split(r"\n\s*\n", md.strip()):
        lines = block.splitlines()
        if all(l.startswith("- ") for l in lines):
            blocks.append("<ul>" + "".join(f"<li>{md_inline(l[2:])}</li>" for l in lines) + "</ul>")
        else:
            blocks.append(f"<p>{md_inline(' '.join(lines))}</p>")
    return "\n".join(blocks)


def bullets_md(items):
    return "\n".join(f"- {i}" for i in items)


# --- outputs ---

def write_if_changed(path, data):
    if isinstance(data, str):
        data = data.encode()
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


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


CSS = """
:root{--bg:#f2f2f7;--card:#fff;--text:#1c1c1e;--muted:#6e6e73;--line:#d1d1d6;--accent:#3478f6}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--text:#f2f2f7;--muted:#98989d;--line:#38383a;--accent:#4c8dff}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;-webkit-text-size-adjust:100%}
main{max-width:760px;margin:0 auto;padding:16px}
.card{background:var(--card);border-radius:12px;padding:16px;margin:0 0 16px}
h1{font-size:26px;margin:4px 0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:0 0 8px;font-weight:600}
p{margin:0 0 10px}ul{margin:0 0 10px;padding-left:20px}li{margin:3px 0}
a{color:var(--accent);text-decoration:none}
code{font:14px ui-monospace,Menlo,monospace;background:var(--bg);padding:1px 5px;border-radius:5px;word-break:break-all}
.muted{color:var(--muted)}.small{font-size:13px}
.head{display:flex;gap:14px;align-items:center}.head img{width:64px;height:64px;border-radius:14px;flex:none}
.shots{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px;-webkit-overflow-scrolling:touch}
.shots img{height:280px;width:auto;border-radius:8px;border:1px solid var(--line);flex:none}
table{width:100%;border-collapse:collapse}td{padding:6px 0;border-top:1px solid var(--line)}td:last-child{text-align:right;color:var(--muted)}
.buttons{display:flex;flex-wrap:wrap;gap:10px;margin:8px 0}
.btn{display:inline-block;padding:10px 16px;border-radius:10px;background:var(--accent);color:#fff;font-weight:600}
.btn.alt{background:var(--bg);color:var(--accent)}
.pkg{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-top:1px solid var(--line)}.pkg:first-of-type{border-top:0}
.pkg img{width:48px;height:48px;border-radius:11px;flex:none}.pkg h3{margin:0;font-size:17px}
"""


def page(title, body, base, depth):
    css = "../" * depth + "depictions/style.css"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{css}">
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def cydia_depiction(pkg, ctl, meta, base, size):
    shots_dir = f"screenshots/{meta['short']}"
    shots = "".join(
        f'<img src="{shots_dir}/{html.escape(s["file"])}" alt="{html.escape(s.get("alt", ""))}" loading="lazy">'
        for s in meta.get("screenshots", [])
    )
    changelog = "".join(
        f"<p><strong>Version {html.escape(e['version'])}</strong></p><ul>"
        + "".join(f"<li>{md_inline(c)}</li>" for c in e["changes"]) + "</ul>"
        for e in meta.get("changelog", [])
    )
    repo_url = f"https://github.com/{meta['github']}"
    body = f"""<div class="card head"><img src="../icons/{pkg}.png" alt="">
<div><h1>{html.escape(ctl.get('Name', pkg))}</h1><div class="muted">{html.escape(meta['tagline'])}</div></div></div>
<div class="card">{md_to_html(meta['description'])}</div>
<div class="card"><h2>Screenshots</h2><div class="shots">{shots}</div></div>
<div class="card"><h2>Features</h2>{md_to_html(bullets_md(meta['features']))}</div>
<div class="card"><h2>Settings</h2>{md_to_html(meta['settings'])}</div>
<div class="card"><h2>Compatibility</h2>{md_to_html(bullets_md(meta['compatibility']))}</div>
<div class="card"><h2>Changelog</h2>{changelog}</div>
<div class="card"><h2>Information</h2><table>
<tr><td>Version</td><td>{html.escape(ctl['Version'])}</td></tr>
<tr><td>Developer</td><td>{html.escape(ctl.get('Author', 'itsAllexB'))}</td></tr>
<tr><td>Size</td><td>{max(1, round(size / 1024))} KB</td></tr>
<tr><td>License</td><td>GPL-3.0</td></tr>
<tr><td>Source code</td><td><a href="{repo_url}">GitHub</a></td></tr>
<tr><td>Problems</td><td><a href="{repo_url}/issues">Report an issue</a></td></tr>
</table></div>
<p class="muted small">Unofficial. Not affiliated with or endorsed by Apple.</p>"""
    return page(ctl.get("Name", pkg), body, base, 1)


def index_page(latest, meta_all, base):
    repo = meta_all["repo"]
    enc = base
    rows = []
    for pkg in sorted(latest, key=lambda p: latest[p][0].get("Name", p).lower()):
        ctl, _ = latest[pkg]
        m = meta_all["packages"].get(pkg, {})
        tagline = m.get("tagline") or ctl.get("Description", "").split("\n")[0]
        gh = f'<a href="https://github.com/{m["github"]}">Source</a>' if m.get("github") else ""
        rows.append(f"""<div class="pkg"><img src="icons/{pkg}.png" alt="">
<div><h3><a href="depictions/{pkg}.html">{html.escape(ctl.get('Name', pkg))}</a> <span class="muted small">{html.escape(ctl['Version'])}</span></h3>
<div>{html.escape(tagline)}</div><div class="small"><a href="depictions/{pkg}.html">Details</a> &middot; {gh}</div></div></div>""")
    body = f"""<div class="card head"><img src="CydiaIcon.png" alt="">
<div><h1>{html.escape(repo['name'])}</h1><div class="muted">{html.escape(repo['description'])}</div></div></div>
<div class="card"><h2>Add this source</h2>
<p>Open this page on your jailbroken device and tap your package manager:</p>
<div class="buttons">
<a class="btn" href="sileo://source/{enc}">Add to Sileo</a>
<a class="btn" href="zbra://sources/add/{enc}">Add to Zebra</a>
<a class="btn" href="cydia://url/https://cydia.saurik.com/api/share#?source={enc}">Add to Cydia</a>
</div>
<p class="small muted">Or add it by hand in Sources: <code>{html.escape(base)}</code></p></div>
<div class="card"><h2>Packages</h2>{''.join(rows)}</div>
<div class="card"><h2>Signing key</h2>
<p class="small">The index is signed with <a href="ios-legacy.asc">ios-legacy.asc</a> (also <a href="ios-legacy.gpg">ios-legacy.gpg</a>), fingerprint <code>{{FPR}}</code>.</p></div>
<p class="muted small">Unofficial tweaks. Not affiliated with or endorsed by Apple. Source code on <a href="https://github.com/{repo['github']}">GitHub</a>, GPL-3.0.</p>"""
    return page(repo["name"], body, base, 0)


def readme_table(latest, meta_all):
    """Package table for README.md, between the packages:start/end markers."""
    rows = ["| Package | Version | What it does |", "| --- | --- | --- |"]
    for pkg in sorted(latest, key=lambda p: latest[p][0].get("Name", p).lower()):
        ctl, _ = latest[pkg]
        m = meta_all["packages"].get(pkg, {})
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

    write_if_changed("depictions/style.css", CSS.lstrip())
    for pkg, (ctl, size) in latest.items():
        m = meta_all["packages"].get(pkg)
        if not m:
            print(f"gen_repo: warning: no meta/packages.json entry for {pkg}; no depiction generated", file=sys.stderr)
            continue
        write_if_changed(f"depictions/{pkg}.json", json.dumps(sileo_depiction(pkg, ctl, m, base, size), indent=2) + "\n")
        write_if_changed(f"depictions/{pkg}.html", cydia_depiction(pkg, ctl, m, base, size))
    write_if_changed("index.html", index_page(latest, meta_all, base).replace("{FPR}", html.escape(args.fingerprint or "see ios-legacy.asc")))
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
