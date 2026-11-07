#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 AllexB
"""Generate the public web pages: index.html, depictions/<pkg>.html and add/*.html.

The pages are plain HTML for depictions/style.css. They have to work in Safari and Cydia on
iOS 6, so the only script is a few lines of old-style JavaScript, and every page still works
without it. Everything comes from meta/packages.json and the control fields of the debs in
debs/, so a tweak appears here only once it has a deb on the source. See README.md.
"""

import html
import os
import re
import struct


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
    raise SystemExit(f"gen_site: error: cannot read image size of {path}")


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


# --- facts about a package ---

def display_name(ctl, pkg):
    """The Name field without its "(iOS 12)": the page already says which iOS it's for."""
    return re.sub(r"\s*\(iOS [\d.]+\)\s*$", "", ctl.get("Name", pkg))


def ios_version(ctl, meta):
    """The iOS major version a package is for: its firmware dependency, or "ios" in its meta entry."""
    found = re.search(r"firmware\s*\(\s*>=\s*(\d+)", ctl.get("Depends", ""))
    if found:
        return found.group(1)
    return str(meta.get("ios", "")) or None


def short_text(ctl, meta):
    return meta.get("summary") or meta.get("tagline") or ctl.get("Description", "").split("\n")[0]


def plain_person(field):
    """A name from a control field, without any address in angle brackets."""
    return re.sub(r"\s*<[^>]*>", "", field).strip()


def has_icon(pkg):
    return os.path.exists(f"icons/{pkg}.png")


def icon(pkg, meta, prefix, big=False):
    classes = "ic" + (" big" if big else "")
    if not has_icon(pkg):
        return f'<span class="{classes} ic-none"></span>'
    if meta.get("gloss", True):
        classes += " gloss"
    size = 72 if big else 48
    return f'<span class="{classes}"><img src="{prefix}icons/{pkg}.png" alt="" width="{size}" height="{size}"></span>'


# --- shared parts of a page ---

# Old-style JavaScript on purpose. It only adds classes: inapp (inside a package manager, which has
# its own bar), cydiaonly (too old for Sileo and Zebra), notios (a computer, nothing to add it to).
# Cydia's package page shows this page in an iframe, so links there must leave the frame.
HEAD_SCRIPT = (
    "<script>(function(d,u){var m=/\\bOS (\\d+)_\\d/.exec(u),s=' js';"
    "if(/Cydia|Zebra|Sileo|Installer/.test(u))s+=' inapp';"
    "if(m){if(+m[1]<9)s+=' cydiaonly';}"
    "else if(!(navigator.maxTouchPoints>1))s+=' notios';"
    "d.documentElement.className+=s;window.iosMajor=m?m[1]:'';"
    "if(window.top!==window.self)d.write('<base target=\"_top\">');})(document,navigator.userAgent);</script>"
)


def page(title, body, depth, extra_head="", script=""):
    root = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="format-detection" content="telephone=no">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#7d93b0" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#2c384a" media="(prefers-color-scheme: dark)">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{root}depictions/style.css">
<link rel="apple-touch-icon-precomposed" href="{root}CydiaIcon.png">
<link rel="icon" href="{root}CydiaIcon.png">{extra_head}
{HEAD_SCRIPT}
</head>
<body ontouchstart="">
{body}{script}
</body>
</html>
"""


def nav(title, back_label=None, back_href=None):
    back = f'<a class="back" href="{back_href}">{html.escape(back_label)}</a>' if back_href else ""
    return f'<div class="nav"><div class="nav-in">{back}<h1>{html.escape(title)}</h1></div></div>'


def add_urls(base):
    return {
        "Cydia": f"cydia://url/https://cydia.saurik.com/api/share#?source={base}",
        "Sileo": f"sileo://source/{base}",
        "Zebra": f"zbra://sources/add/{base}",
    }


def add_buttons(base, on_package_page=False):
    urls = add_urls(base)
    cls = "addblock pkgadd" if on_package_page else "addblock"
    return f"""<div class="{cls}">
<a class="glass blue" href="{urls['Cydia']}">Add to Cydia</a>
<div class="pair"><a class="glass silver" href="{urls['Sileo']}">Add to Sileo</a><a class="glass silver" href="{urls['Zebra']}">Add to Zebra</a></div>
<p class="foot deskhint">Open this page on your iPhone or iPad.</p>
</div>"""


LEGAL = "Unofficial. Not affiliated with or endorsed by Apple."


# --- package pages ---

SHOT_HEIGHT = 260
SHOT_MAX_WIDTH = 296


def shots_strip(meta):
    """Screenshots from the meta entry. "web": false keeps one off these pages, and "crop_left": 0.42
    shows it without that part of its left side. The Sileo depiction always lists them all."""
    shots_dir = f"screenshots/{meta['short']}"
    items = []
    for s in meta.get("screenshots", []):
        if s.get("web") is False:
            continue
        name = html.escape(s["file"])
        w, h = image_size(f"depictions/{shots_dir}/{s['file']}")
        crop = float(s.get("crop_left", 0))
        scale = SHOT_HEIGHT / h
        if w * (1 - crop) * scale > SHOT_MAX_WIDTH:
            scale = SHOT_MAX_WIDTH / (w * (1 - crop))
        img_w, img_h, box_w = round(w * scale), round(h * scale), round(w * (1 - crop) * scale)
        shift = f' style="margin-left:-{img_w - box_w}px"' if crop else ""
        items.append(
            f'<a href="{shots_dir}/{name}" style="width:{box_w}px;height:{img_h}px">'
            f'<img src="{shots_dir}/{name}" alt="{html.escape(s.get("alt", ""))}" '
            f'width="{img_w}" height="{img_h}"{shift} loading="lazy"></a>'
        )
    return f'<div class="shots">{"".join(items)}</div>' if items else ""


def list_group(items):
    rows = "".join(f'<li><div class="line">{md_inline(i)}</div></li>' for i in items)
    return f'<ul class="group">{rows}</ul>'


def value_row(label, value):
    return f'<li><div class="row"><span class="val">{html.escape(value)}</span>{html.escape(label)}</div></li>'


def link_row(label, href):
    return f'<li><a class="row" href="{href}">{html.escape(label)}</a></li>'


def changes(entry):
    return f'<p class="ver-t">Version {html.escape(entry["version"])}</p><ul>' + "".join(
        f"<li>{md_inline(c)}</li>" for c in entry["changes"]
    ) + "</ul>"


def package_page(pkg, ctl, meta, base, size):
    name = display_name(ctl, pkg)
    developer = plain_person(ctl.get("Author", "AllexB"))
    maintainer = plain_person(ctl.get("Maintainer", ""))
    ios = ios_version(ctl, meta)
    repo_url = f"https://github.com/{meta['github']}"

    log = meta.get("changelog", [])
    whats_new = ""
    if log:
        whats_new = f'<h2 class="sec">What\'s New</h2><ul class="group"><li><div class="text">{changes(log[0])}</div></li></ul>'
    history = ""
    if len(log) > 1:
        older = "".join(f'<div class="text">{changes(e)}</div>' for e in log[1:])
        history = f'<ul class="group"><li><details><summary>Version History</summary>{older}</details></li></ul>'

    info = [value_row("Version", ctl["Version"]), value_row("Developer", developer)]
    if maintainer and maintainer != developer:
        info.append(value_row("Maintainer", maintainer))
    info.append(value_row("Size", f"{max(1, round(size / 1024))} KB"))
    if ios:
        info.append(value_row("Requires", f"iOS {ios}"))
    if meta.get("devices"):
        info.append(value_row("Devices", meta["devices"]))
    info.append(value_row("License", "GPL-3.0"))

    body = f"""{nav(name, "iOS Legacy", "../")}
<main class="wrap">
<div class="side">
<div class="hero">{icon(pkg, meta, "../", big=True)}<h2>{html.escape(name)}</h2><p>{html.escape(short_text(ctl, meta))}</p></div>
{add_buttons(base, on_package_page=True)}
</div>
<div class="main">
<ul class="group"><li><div class="text">{md_to_html(meta['description'])}</div></li></ul>
{shots_strip(meta)}
<h2 class="sec">Features</h2>
{list_group(meta['features'])}
<h2 class="sec">Compatibility</h2>
{list_group(meta['compatibility'])}
<ul class="group"><li><details><summary>Settings</summary><div class="text">{md_to_html(meta['settings'])}</div></details></li></ul>
{whats_new}
{history}
</div>
<div class="side">
<h2 class="sec">Information</h2>
<ul class="group">{"".join(info)}</ul>
<ul class="group">{link_row("Source Code", repo_url)}{link_row("Report a Problem", repo_url + "/issues")}</ul>
</div>
<p class="legal">{LEGAL}</p>
</main>"""
    return page(name, body, 1)


# --- home page ---

# Filters the list when the control is tapped, and starts on the visitor's own iOS version.
# Without JavaScript the segments are plain links that jump to each group.
INDEX_SCRIPT = """
<script>(function(){
var seg=document.getElementById('seg');if(!seg)return;
var links=seg.getElementsByTagName('a'),all=document.getElementById('tweaks').getElementsByTagName('div'),blocks=[],i;
for(i=0;i<all.length;i++){if(all[i].getAttribute('data-ios'))blocks.push(all[i]);}
function has(v){for(var j=0;j<blocks.length;j++){if(blocks[j].getAttribute('data-ios')===v)return true;}return false;}
function pick(v){
for(i=0;i<links.length;i++){links[i].className=links[i].getAttribute('data-ios')===v?'on':'';}
for(i=0;i<blocks.length;i++){blocks[i].style.display=(!v||blocks[i].getAttribute('data-ios')===v)?'':'none';}
}
seg.onclick=function(e){
var t=(e||window.event).target;if(!t||t.nodeName!=='A')return;
pick(t.getAttribute('data-ios'));return false;
};
var own=document.getElementById('ios'+window.iosMajor);if(own)own.className+=' yours';
var h=/^#ios(\\d+)$/.exec(location.hash);
pick(h&&has(h[1])?h[1]:(has(window.iosMajor)?window.iosMajor:''));
})();</script>"""


def group_order(found, site):
    listed = [str(g["ios"]) for g in site.get("groups", [])]
    extra = sorted((v for v in found if v not in listed and v != "other"), key=int, reverse=True)
    order = [v for v in listed if v in found] + extra
    if "other" in found:
        order.append("other")
    return order


def package_row(pkg, ctl, meta):
    name = display_name(ctl, pkg)
    devices = f'<span class="m">{html.escape(meta["devices"])}</span>' if meta.get("devices") else ""
    inner = (
        f'{icon(pkg, meta, "")}<b>{html.escape(name)}</b><span class="ver">{html.escape(ctl["Version"])}</span>'
        f'<span class="d">{html.escape(short_text(ctl, meta))}</span>{devices}'
    )
    if not meta:  # a deb with no meta entry has no page to open
        return f'<li><div class="row tw">{inner}</div></li>'
    return f'<li><a class="row tw" href="depictions/{pkg}.html">{inner}</a></li>'


def fingerprint_groups(fpr):
    if re.fullmatch(r"[0-9A-Fa-f]{40}", fpr or ""):
        return " ".join(fpr[i:i + 4] for i in range(0, 40, 4))
    return "see ios-legacy.asc"


def index_page(latest, meta_all, base, fingerprint):
    repo = meta_all["repo"]
    site = meta_all.get("site", {})
    footers = {str(g["ios"]): g.get("footer", "") for g in site.get("groups", [])}

    grouped = {}
    for pkg, (ctl, _) in latest.items():
        meta = meta_all["packages"].get(pkg, {})
        if meta.get("transitional"):  # empty upgrade packages stay in Packages but aren't listed
            continue
        grouped.setdefault(ios_version(ctl, meta) or "other", []).append((pkg, ctl, meta))

    order = group_order(grouped, site)
    segments = '<a class="on" href="#tweaks" data-ios="">All</a>'
    blocks = []
    for v in order:
        title = "Other" if v == "other" else f"iOS {v}"
        rows = "".join(
            package_row(pkg, ctl, meta)
            for pkg, ctl, meta in sorted(grouped[v], key=lambda r: display_name(r[1], r[0]).lower())
        )
        foot = f'<p class="foot">{html.escape(footers[v])}</p>' if footers.get(v) else ""
        blocks.append(
            f'<div class="block" id="ios{v}" data-ios="{v}"><h2 class="sec">{title}<span class="here">This device</span></h2>'
            f'<ul class="group">{rows}</ul>{foot}</div>'
        )
        segments += f'<a href="#ios{v}" data-ios="{v}">{title}</a>'
    seg = f'<div class="seg-w"><div class="seg" id="seg">{segments}</div></div>' if len(order) > 1 else ""

    fpr_text = fingerprint_groups(fingerprint)
    body = f"""{nav(repo['name'])}
<main class="wrap">
<div class="side">
<div class="hero"><span class="ic big"><img src="CydiaIcon.png" alt="" width="72" height="72"></span><h2>{html.escape(repo['name'])}</h2><p>{html.escape(site.get('tagline', repo['description']))}</p><p>By {html.escape(repo['maintainer'])}</p></div>
{add_buttons(base)}
<ul class="group"><li><div class="row"><span class="lbl">Or add this URL in Sources</span><span class="url">{html.escape(base)}</span></div></li></ul>
</div>
<div class="main" id="tweaks">
{seg}
{"".join(blocks)}
</div>
<div class="side">
<h2 class="sec">About</h2>
<ul class="group">{link_row("Source Code", "https://github.com/" + repo['github'])}{value_row("License", "GPL-3.0")}{link_row("Signing Key", "ios-legacy.asc")}{link_row("Key for apt", "ios-legacy.gpg")}</ul>
<p class="foot">Key fingerprint<br>{html.escape(fpr_text)}</p>
</div>
<p class="legal">{LEGAL}</p>
</main>"""
    tagline = html.escape(site.get("tagline", repo["description"]))
    extra = (
        f'\n<meta name="description" content="{tagline}">'
        f'\n<meta property="og:title" content="{html.escape(repo["name"])}">'
        f'\n<meta property="og:description" content="{tagline}">'
        f'\n<meta property="og:image" content="{base}CydiaIcon.png">'
    )
    return page(repo["name"], body, 0, extra_head=extra, script=INDEX_SCRIPT)


# --- one-tap add pages ---

def add_page(manager, url, base, repo_name):
    body = f"""{nav("Add Source", repo_name, "../")}
<main class="wrap">
<div class="hero"><span class="ic big"><img src="../CydiaIcon.png" alt="" width="72" height="72"></span><h2>{html.escape(repo_name)}</h2><p>{html.escape(manager)} should open now.</p></div>
<a class="glass blue" href="{url}">Open {html.escape(manager)}</a>
<p class="foot deskhint">Open this page on your iPhone or iPad.</p>
<ul class="group"><li><div class="row"><span class="lbl">Or add this URL in Sources</span><span class="url">{html.escape(base)}</span></div></li></ul>
</main>"""
    redirect = f'\n<script>window.location.replace("{url}");</script>'
    return page(f"Add {repo_name} to {manager}", body, 1, extra_head=redirect)


# --- all of it ---

def write_site(latest, meta_all, base, fingerprint):
    for pkg, (ctl, size) in latest.items():
        meta = meta_all["packages"].get(pkg)
        if meta:
            write_if_changed(f"depictions/{pkg}.html", package_page(pkg, ctl, meta, base, size))
    write_if_changed("index.html", index_page(latest, meta_all, base, fingerprint))
    for manager, url in add_urls(base).items():
        write_if_changed(f"add/{manager.lower()}.html", add_page(manager, url, base, meta_all["repo"]["name"]))
