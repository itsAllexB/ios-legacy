# iOS Legacy

<img src="CydiaIcon.png" alt="" width="96" align="right">

A small package source (APT repo) for jailbroken iPads and iPhones on iOS 12 and iOS 6, with tweaks by AllexB. It works with Sileo, Zebra and Cydia (including Cydia on iOS 6).

Source URL:

```
https://itsallexb.github.io/ios-legacy/
```

## Add the source

On your jailbroken device, tap one of these:

- [Add to Sileo](https://itsallexb.github.io/ios-legacy/add/sileo.html)
- [Add to Zebra](https://itsallexb.github.io/ios-legacy/add/zebra.html)
- [Add to Cydia](https://itsallexb.github.io/ios-legacy/add/cydia.html)

Or open your package manager, go to Sources, tap Add (or Edit, then Add) and enter the URL above.

## Packages

<!-- packages:start -->
| Package | Version | What it does |
| --- | --- | --- |
| [BatteryPlus (iOS 12)](https://github.com/itsAllexB/BatteryPlus-iOS12) | 1.2.0 | Low Power Mode, Automatic Low Power Mode, Battery Health and the percentage inside the battery icon for iOS 12 iPads. |
| [DefaultApps (iOS 12)](https://github.com/itsAllexB/DefaultApps-iOS12) | 3.1.0 | Choose your default browser, mail app and maps app. |
| [FilesArchiver (iOS 12)](https://github.com/itsAllexB/FilesArchiver-iOS12) | 1.0.1 | Uncompress and Compress in the Files app, like iOS 13. |
| [FilesExtensions (iOS 12)](https://github.com/itsAllexB/FilesExtensions-iOS12) | 1.0.1 | Show or hide file name extensions in the Files app. |
| [FilesRoot (iOS 12)](https://github.com/itsAllexB/FilesRoot-iOS12) | 1.0.2 | Browse the whole filesystem in the Files app. Read-only by default. |
| [OldSend](https://github.com/itsAllexB/OldSend) | 2.0 | Send files, photos, links and text between an iOS 6 iPhone and any device running LocalSend. |
| [SafariScale (iOS 6)](https://github.com/itsAllexB/SafariScale-iOS6) | 1.1.0 | Smaller web pages in Safari on iOS 6, like zooming out in a desktop browser. |
| [SplitViewEnabler (iOS 12)](https://github.com/itsAllexB/SplitViewEnabler-iOS12) | 2.0.1 | Split View and Slide Over on iPads that only had Slide Over. |
| [WeatherPad (iOS 12)](https://github.com/itsAllexB/WeatherPad-iOS12) | 1.2.3 | Apple's iPhone Weather app, running natively on iPad. |
<!-- packages:end -->

The iOS 12 packages are tested on an iPad mini 2 with iOS 12.5.8 (checkra1n + odysseyra1n / libhooker) and should work on iOS 12.x. SafariScale and OldSend are tested on an iPhone 4S with iOS 6.1.3 (Cydia Substrate) and install on iOS 6.x only. Every package only installs on the iOS version it was made for. Each package page in your package manager has screenshots, settings and compatibility details.

These are unofficial tweaks. They are not affiliated with or endorsed by Apple.

## Signing key

`Release` is signed (`Release.gpg` and `InRelease`) with this key:

```
iOS Legacy Repo (itsAllexB)
FC19 4D0E 4C4D 77E5 0B3E  153A 724C CD61 F96D E214
```

The public key is in [`ios-legacy.asc`](ios-legacy.asc) and, as a binary keyring for `/etc/apt/trusted.gpg.d/`, in [`ios-legacy.gpg`](ios-legacy.gpg). Sileo, Zebra and Cydia add the source without the key, so you don't need to install it there. If you use `apt` from the command line, it refuses the source until it knows the key:

```sh
curl -fsSL https://itsallexb.github.io/ios-legacy/ios-legacy.gpg -o /etc/apt/trusted.gpg.d/ios-legacy.gpg
```

## How the repo is built

```
debs/                    the .deb packages
meta/packages.json       text, screenshots and changelog for each package page, and the home page's groups
depictions/              generated package pages (Sileo .json, Cydia/web .html) and their screenshots
depictions/style.css     the stylesheet for every web page, edited by hand
icons/                   package icons
add/                     generated one-tap "add source" pages for Sileo, Zebra and Cydia
scripts/build-repo.sh    regenerates Packages*, Release, depictions, add pages and index.html, then signs Release
scripts/gen_repo.py      the APT index and Sileo depictions (Python standard library + dpkg-deb)
scripts/gen_site.py      the web pages: index.html, depictions/*.html, add/*.html
```

Build locally (macOS: `brew install dpkg gnupg`):

```sh
scripts/build-repo.sh
```

The script imports the private key from `~/.config/ios-legacy/ios-legacy-private.asc` (or the `GPG_KEY_FILE` / `GPG_PRIVATE_KEY` environment variables) into a temporary keyring, signs, and checks both signatures with `gpgv` against `ios-legacy.gpg`. It refuses to sign with any other key.

### The website

The home page, package pages and add pages look like iOS 6 and have to work in Safari and Cydia on iOS 6 as well as on today's phones and computers. So they are plain HTML and one CSS file, with no build tools:

- No CSS custom properties, flexbox or grid. Gradients are written twice, `-webkit-` first. Extras for newer browsers (dark mode, the sticky bar, safe areas) sit in `@media` and `@supports` blocks that iOS 6 skips.
- Everything is drawn with CSS or inline SVG. Colours and sizes were measured from iOS 6's own Settings. No images from Apple.
- The only script is a few lines of old-style JavaScript. Without it every page still works: all groups show, and the segments are plain links.

Inside Cydia, Zebra and Installer the page hides its own bar and Add buttons, since the app has its own.

Don't change these URLs. Packages already installed point to them: `depictions/<package>.html`, `depictions/<package>.json`, `icons/<package>.png`, `add/*.html` and `depictions/style.css`.

### Add a tweak

One entry in `meta/packages.json`, under `packages`, keyed by the package id:

```json
"com.itsallexb.example": {
  "short": "example",
  "github": "itsAllexB/Example-iOS6",
  "tint": "#3478F6",
  "tagline": "One sentence for Sileo and the table above.",
  "summary": "A few words for the home page.",
  "devices": "iPhone 4S",
  "description": "What it does, as Markdown.",
  "features": ["One line each"],
  "compatibility": ["Tested on iPhone 4S, iOS 6.1.3"],
  "settings": "Settings > Example:\n\n- **Enabled**: turns it on or off.",
  "screenshots": [{"file": "settings.png", "alt": "Example settings page"}],
  "changelog": [{"version": "1.0.0", "changes": ["First public release."]}]
}
```

Then add `icons/<package>.png` (120 x 120) and the screenshots in `depictions/screenshots/<short>/`, and add the tweak's repository to the list in [publish.yml](.github/workflows/publish.yml).

That's all. The tweak appears once its `.deb` is on the source, and the deb's `firmware (>= N)` dependency decides its iOS group. A new iOS version gets its own group and segment by itself; `site.groups` in the same file sets the order and the footers. A tweak with no `.deb` never appears on the site, but **`meta/packages.json` is public as soon as it's pushed, so add the entry only when the tweak is ready to publish.**

Optional fields: `"gloss": false` for an icon that has its own shine, and `"ios": "6"` for a package with no firmware dependency. On a screenshot, `"web": false` keeps it off the web pages, and `"crop_left": 0.417` hides that share of its left side, for an iPad Settings sidebar. Sileo's depiction always lists them all.

To see the pages locally, run `ALLOW_UNSIGNED=1 scripts/build-repo.sh`, then `python3 -m http.server`. This rewrites the APT files, so run `git checkout -- Packages Packages.gz Packages.bz2 Packages.xz Release Release.gpg InRelease` before you commit.

Known limitations: on iOS 6 it has been tested on an iPhone 4 emulator (LightTouch) with iOS 6.1.3, not yet on a real iPhone or an iPad. Landscape text couldn't be checked there, as the emulator garbles it on any page.

### Publishing

The [Publish repo](.github/workflows/publish.yml) workflow runs on every push to `main`, on manual runs, and on a `repository_dispatch` event of type `package-released`. It:

1. downloads the `.deb` files from the latest GitHub release of each tweak repository (SplitViewEnabler, WeatherPad, DefaultApps, FilesArchiver, FilesRoot, FilesExtensions and BatteryPlus), if they have releases,
2. runs `scripts/build-repo.sh` with the `GPG_PRIVATE_KEY` secret (and `GPG_PASSPHRASE`, if the key has one),
3. deploys the result to GitHub Pages.

Setup: in the repository settings set Pages > Source to "GitHub Actions" and add the `GPG_PRIVATE_KEY` secret.

To publish a new tweak version, attach the `.deb` to a release in the tweak's repository, then start the workflow (Actions > Publish repo > Run workflow, or `gh workflow run publish.yml -R itsAllexB/ios-legacy`). You can also commit the `.deb` to `debs/` and push.

## License

GPL-3.0. See [LICENSE](LICENSE).
