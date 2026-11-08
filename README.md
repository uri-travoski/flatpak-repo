# flathub-publisher

Publishes selected apps to Flathub.

Edit `repos.yml` and set `enabled: true` for the repos to publish. The workflow
runs on every push to `repos.yml`, daily, and on demand (Actions → Run workflow).

* New app: opens an "Add <app_id>" PR on flathub/flathub (human review, once).
* Already accepted: opens an update PR on flathub/<app_id> when a new release exists.

Secret `FLATHUB_TOKEN`: a GitHub token with `repo` scope.
Local check without submitting: `python3 scripts/publish.py --dry-run`
(needs `pip install pyyaml aiohttp tomlkit`; downloads flatpak-cargo-generator.py).
