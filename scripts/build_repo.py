#!/usr/bin/env python3
"""Build the signed Flatpak repository site from repos.yml into ./site.

For every enabled app: download the Flatpak bundle from the repo's latest
GitHub release, import it, sign it, then write the repo, a .flatpakrepo, one
.flatpakref per app and an index page.

Env: GPG_KEY_ID (the key in the keyring), SITE_URL (public base URL).
"""
import base64, fnmatch, html, json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path

import yaml

KEY = os.environ["GPG_KEY_ID"]
SITE_URL = os.environ.get("SITE_URL", "https://uri-travoski.github.io/flatpak-repo").rstrip("/")
FLATHUB = "https://dl.flathub.org/repo/flathub.flatpakrepo"
SITE = Path("site")
REPO = SITE / "repo"


def get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def run(*cmd):
    subprocess.run(cmd, check=True)


def app_ref(app_id):
    """The `app/<id>/<arch>/<branch>` ref imported into the repo."""
    out = subprocess.run(["ostree", "refs", f"--repo={REPO}"], check=True, capture_output=True, text=True).stdout
    for ref in out.split():
        if ref.startswith(f"app/{app_id}/"):
            return ref
    sys.exit(f"{app_id}: no app ref in the repo after import")


def main():
    shutil.rmtree(SITE, ignore_errors=True)
    SITE.mkdir()
    run("ostree", "init", f"--repo={REPO}", "--mode=archive-z2")
    key_b64 = base64.b64encode(Path("public.gpg").read_bytes()).decode()
    published = []
    for app in yaml.safe_load(Path("repos.yml").read_text())["apps"]:
        if not app.get("enabled"):
            print(f"{app['name']}: disabled, skipping")
            continue
        rel = get_json(f"https://api.github.com/repos/{app['repo']}/releases/latest")
        asset = next((a for a in rel["assets"] if fnmatch.fnmatch(a["name"], app["asset"])), None)
        if not asset:
            sys.exit(f"{app['name']}: no asset matching {app['asset']} in {rel['tag_name']}")
        bundle = Path("bundle.flatpak")
        print(f"{app['name']}: {rel['tag_name']} {asset['name']}")
        urllib.request.urlretrieve(asset["browser_download_url"], bundle)
        run("flatpak", "build-import-bundle", str(REPO), str(bundle))
        bundle.unlink()
        ref = app_ref(app["app_id"])
        branch = ref.split("/")[-1]
        run("flatpak", "build-sign", f"--gpg-sign={KEY}", str(REPO), app["app_id"], branch)
        published.append({**app, "branch": branch, "version": rel["tag_name"]})
    if not published:
        sys.exit("No enabled apps")
    run("flatpak", "build-update-repo", f"--gpg-sign={KEY}", "--generate-static-deltas", "--prune", str(REPO))

    (SITE / "public.gpg").write_bytes(Path("public.gpg").read_bytes())
    (SITE / "uri-travoski.flatpakrepo").write_text(
        "[Flatpak Repo]\n"
        "Title=uri-travoski apps\n"
        f"Url={SITE_URL}/repo\n"
        "Homepage=https://github.com/uri-travoski\n"
        "Comment=Apps by uri-travoski\n"
        f"GPGKey={key_b64}\n"
    )
    rows = []
    for a in published:
        (SITE / f"{a['app_id']}.flatpakref").write_text(
            "[Flatpak Ref]\n"
            f"Title={a['name']}\n"
            f"Name={a['app_id']}\n"
            f"Branch={a['branch']}\n"
            f"Url={SITE_URL}/repo\n"
            "IsRuntime=False\n"
            f"GPGKey={key_b64}\n"
            f"RuntimeRepo={FLATHUB}\n"
        )
        rows.append(
            f"<li><b>{html.escape(a['name'])}</b> {html.escape(a['version'])}: {html.escape(a['summary'])}<br>"
            f"<code>flatpak install uri-travoski {html.escape(a['app_id'])}</code> "
            f"(<a href=\"{a['app_id']}.flatpakref\">.flatpakref</a>, "
            f"<a href=\"https://github.com/{a['repo']}\">source</a>)</li>"
        )
    (SITE / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>uri-travoski Flatpak repository</title>"
        "<body style='font:16px system-ui;max-width:42rem;margin:2rem auto;padding:0 16px'>"
        "<h1>uri-travoski Flatpak repository</h1>"
        "<p>Add the repository once, then install and update apps like any Flatpak:</p>"
        f"<pre>flatpak remote-add --user --if-not-exists uri-travoski {SITE_URL}/uri-travoski.flatpakrepo</pre>"
        f"<ul>{''.join(rows)}</ul></body>"
    )
    print("published:", ", ".join(a["name"] for a in published))


if __name__ == "__main__":
    main()
