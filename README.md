# iOS Legacy

<img src="CydiaIcon.png" alt="" width="96" align="right">

A small package source (APT repo) for jailbroken iPads and iPhones on iOS 12, with tweaks by itsAllexB. It works with Sileo, Zebra and Cydia.

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
| [BatteryPlus (iOS 12)](https://github.com/itsAllexB/BatteryPlus-iOS12) | 1.1.1 | Low Power Mode, Battery Health and battery colours for iOS 12 iPads. |
| [DefaultApps (iOS 12)](https://github.com/itsAllexB/DefaultApps-iOS12) | 3.1.0 | Choose your default browser, mail app and maps app. |
| [FilesArchiver (iOS 12)](https://github.com/itsAllexB/FilesArchiver-iOS12) | 1.0.1 | Uncompress and Compress in the Files app, like iOS 13. |
| [FilesExtensions (iOS 12)](https://github.com/itsAllexB/FilesExtensions-iOS12) | 1.0.1 | Show or hide file name extensions in the Files app. |
| [FilesRoot (iOS 12)](https://github.com/itsAllexB/FilesRoot-iOS12) | 1.0.2 | Browse the whole filesystem in the Files app. Read-only by default. |
| [SplitViewEnabler (iOS 12)](https://github.com/itsAllexB/SplitViewEnabler-iOS12) | 2.0.1 | Split View and Slide Over on iPads that only had Slide Over. |
| [WeatherPad (iOS 12)](https://github.com/itsAllexB/WeatherPad-iOS12) | 1.2.3 | Apple's iPhone Weather app, running natively on iPad. |
<!-- packages:end -->

All packages are tested on an iPad mini 2 with iOS 12.5.8 (checkra1n + odysseyra1n / libhooker) and should work on iOS 12.x. Each package page in your package manager has screenshots, settings and compatibility details.

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
meta/packages.json       text, screenshots and changelog for each package page
depictions/              generated package pages (Sileo .json, Cydia/web .html) and their screenshots
icons/                   package icons
add/                     one-tap "add source" pages for Sileo, Zebra and Cydia
scripts/build-repo.sh    regenerates Packages*, Release, depictions and index.html, then signs Release
scripts/gen_repo.py      the generator used by build-repo.sh (Python standard library + dpkg-deb)
```

Build locally (macOS: `brew install dpkg gnupg`):

```sh
scripts/build-repo.sh
```

The script imports the private key from `~/.config/ios-legacy/ios-legacy-private.asc` (or the `GPG_KEY_FILE` / `GPG_PRIVATE_KEY` environment variables) into a temporary keyring, signs, and checks both signatures with `gpgv` against `ios-legacy.gpg`. It refuses to sign with any other key.

### Publishing

The [Publish repo](.github/workflows/publish.yml) workflow runs on every push to `main`, on manual runs, and on a `repository_dispatch` event of type `package-released`. It:

1. downloads the `.deb` files from the latest GitHub release of each tweak repository (SplitViewEnabler, WeatherPad, DefaultApps, FilesArchiver, FilesRoot, FilesExtensions and BatteryPlus), if they have releases,
2. runs `scripts/build-repo.sh` with the `GPG_PRIVATE_KEY` secret (and `GPG_PASSPHRASE`, if the key has one),
3. deploys the result to GitHub Pages.

Setup: in the repository settings set Pages > Source to "GitHub Actions" and add the `GPG_PRIVATE_KEY` secret.

To publish a new tweak version, attach the `.deb` to a release in the tweak's repository, then start the workflow (Actions > Publish repo > Run workflow, or `gh workflow run publish.yml -R itsAllexB/ios-legacy`). You can also commit the `.deb` to `debs/` and push.

## License

GPL-3.0. See [LICENSE](LICENSE).
