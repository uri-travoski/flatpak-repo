#!/usr/bin/env python3
"""Submit or update apps listed in repos.yml on Flathub.

New app (no github.com/flathub/<app_id> yet): opens a PR "Add <app_id>" on
flathub/flathub against its `new-pr` branch, from a fork.
Accepted app: opens a PR on flathub/<app_id> with the new tag.

Env: GH_TOKEN (needs repo scope). `--dry-run` builds the files into ./out
and only reads from GitHub.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request
from pathlib import Path

import yaml

API = "https://api.github.com"
TOKEN = os.environ.get("GH_TOKEN", "")
CARGO_GENERATOR = (
    "https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/"
    "master/cargo/flatpak-cargo-generator.py"
)


def api(method, path, body=None, ok_404=False):
    req = urllib.request.Request(
        API + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        if e.code == 404 and ok_404:
            return None
        raise SystemExit(f"{method} {path}: {e.code} {e.read().decode()[:300]}")


def run(*cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True)


def build_files(app, out: Path):
    """Write <app_id>.yml (+ cargo-sources.json) for the latest release."""
    repo, app_id = app["repo"], app["app_id"]
    tag = api("GET", f"/repos/{repo}/releases/latest")["tag_name"]
    commit = api("GET", f"/repos/{repo}/commits/{tag}")["sha"]
    src = Path(tempfile.mkdtemp())
    run("git", "clone", "-q", "--depth", "1", "--branch", tag, f"https://github.com/{repo}.git", str(src))
    manifest = yaml.safe_load((src / "packaging/flatpak" / f"{app_id}.yml").read_text())
    for mod in manifest["modules"]:
        srcs = []
        for s in mod.get("sources", []):
            if isinstance(s, dict) and s.get("type") == "dir":
                s = {
                    "type": "git",
                    "url": f"https://github.com/{repo}.git",
                    "tag": tag,
                    "commit": commit,
                    "x-checker-data": {"type": "git", "tag-pattern": r"^v([\d.]+)$"},
                }
            srcs.append(s)
        if srcs:
            mod["sources"] = srcs
    out.mkdir(parents=True, exist_ok=True)
    if (src / "Cargo.lock").exists():
        gen = out.parent / "flatpak-cargo-generator.py"
        if not gen.exists():
            urllib.request.urlretrieve(CARGO_GENERATOR, gen)
        run(sys.executable, str(gen), str(src / "Cargo.lock"), "-o", str(out / "cargo-sources.json"))
    (out / f"{app_id}.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    shutil.rmtree(src, ignore_errors=True)
    return tag


def publish(app, dry):
    app_id = app["app_id"]
    work = Path(tempfile.mkdtemp())
    files = Path("out") / app_id if dry else work / "files"
    tag = build_files(app, files)
    if dry:
        print(f"{app_id} {tag}: files written to {files}")
        return
    me = api("GET", "/user")["login"]
    existing = api("GET", f"/repos/flathub/{app_id}", ok_404=True)
    branch = f"update-{tag}" if existing else f"add-{app_id}"
    if existing:
        repo, base = f"flathub/{app_id}", existing["default_branch"]
        remote = f"https://x-access-token:{TOKEN}@github.com/{repo}.git"
        head = branch
    else:
        repo, base = "flathub/flathub", "new-pr"
        if not api("GET", f"/repos/{me}/flathub", ok_404=True):
            api("POST", "/repos/flathub/flathub/forks", {"default_branch_only": False})
            time.sleep(30)
        remote = f"https://x-access-token:{TOKEN}@github.com/{me}/flathub.git"
        head = f"{me}:{branch}"
    if api("GET", f"/repos/{repo}/pulls?state=open&head={head}"):
        print(f"{app_id}: PR for {branch} is already open, skipping")
        return
    clone = work / "clone"
    run("git", "clone", "-q", "--branch", base, "--depth", "1", remote, str(clone))
    run("git", "checkout", "-q", "-b", branch, cwd=clone)
    for f in files.iterdir():
        shutil.copy(f, clone / f.name)
    run("git", "add", "-A", cwd=clone)
    if not subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=clone).returncode:
        print(f"{app_id}: nothing changed since {tag}, skipping")
        return
    title = f"Update {app_id} to {tag}" if existing else f"Add {app_id}"
    run("git", "-c", "user.name=flathub-publisher",
        "-c", "user.email=noreply@users.noreply.github.com",
        "commit", "-q", "-m", title, cwd=clone)
    run("git", "push", "-q", "origin", branch, cwd=clone)
    pr = api("POST", f"/repos/{repo}/pulls", {
        "title": title, "head": head, "base": base,
        "body": f"Release {tag} of https://github.com/{app['repo']}",
    })
    print(f"{app_id}: opened {pr['html_url']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="app_id to process even if disabled")
    a = ap.parse_args()
    for app in yaml.safe_load(Path("repos.yml").read_text())["apps"]:
        if app["app_id"] == a.only or (not a.only and app.get("enabled")):
            publish(app, a.dry_run)
        else:
            print(f"{app['app_id']}: disabled, skipping")
