# flatpak-repo

A signed Flatpak repository for my apps, hosted on GitHub Pages:
https://uri-travoski.github.io/flatpak-repo/

```sh
flatpak remote-add --user --if-not-exists uri-travoski https://uri-travoski.github.io/flatpak-repo/uri-travoski.flatpakrepo
flatpak install uri-travoski io.github.uri_travoski.Calc
```

## Choosing which apps are published

Edit `repos.yml` and set `enabled: true` or `false` per app. The workflow runs when
`repos.yml` changes, daily, and on demand (Actions → Run workflow). Each app is the
Flatpak bundle attached to its repo's latest GitHub release.

Signing: the private key is the `GPG_PRIVATE_KEY` secret (`GPG_KEY_ID` variable);
`public.gpg` is the public key, also embedded in the `.flatpakrepo`.

`scripts/flathub_submit.py` is an unused helper for opening Flathub submissions; Flathub
requires a manual checklist and video, so it is not wired to any workflow.
