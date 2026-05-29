# Q Engineering Tools — Dashboard & Tool Portal

> **Web-hosted hub for engineering dashboards and tools**  
> 🌐 Live site: [https://gbogeb.github.io/Q_engineering_tools/](https://gbogeb.github.io/Q_engineering_tools/)

---

## Overview

This repository is the **public display layer** of a three-repo engineering federation.
Everything is served directly via [GitHub Pages](https://pages.github.com) — no server,
no build step, no framework required. Dashboards are plain HTML/JS/CSS files organised
in sub-folders.

---

## Federation Architecture

```
CODEX (upstream_conceptual)
  ├─ Markdown books, YAML metadata, requirements
  └─ W000 drift telemetry (PCA drift monitor)
        │
        │  drift_report.json
        ▼
ABACUS (downstream_functional)
  ├─ Python math engines, DMAIC v4.4.0 pipeline
  └─ Cryogenic analysis + HTML dashboard exports
        │
        │  cryo_data.json, drift_data.json, HTML exports
        ▼
Q_engineering_tools (downstream_display)  ← this repo
  └─ GitHub Pages portal — public web UI
```

The federation topology is declared in [`bridge_manifest.yaml`](bridge_manifest.yaml).
Automated publish workflows (ABACUS → `publish-to-portal.yml`, CODEX → `publish-codex-telemetry.yml`)
will push updated data files to this repo on each ABACUS release or CODEX schedule.

---

## Repository Structure

```
Q_engineering_tools/
├── index.html                         ← Portal home page
├── bridge_manifest.yaml               ← Three-repo federation registry
├── .nojekyll                          ← Disables Jekyll on GitHub Pages
├── .github/workflows/pages.yml        ← Auto-deploy to GitHub Pages
│
├── cryo_dashboard_v0_3_0/             ← Cryo Dashboard v0.3.0
│   ├── index.html                       5-tab interactive dashboard (live)
│   ├── README.md
│   └── data/
│       ├── cryo_data.json               He-4 / LN₂ saturation data (ABACUS feed)
│       └── drift_data.json              CODEX W000 drift telemetry (CODEX feed)
│
└── <future_tool_or_dashboard>/        ← Add new dashboards here
    └── index.html
```

---

## Dashboards

| Dashboard | Version | URL | Status |
| --- | --- | --- | --- |
| 🧊 Cryo Dashboard | v0.3.0 | [`/cryo_dashboard_v0_3_0/`](https://gbogeb.github.io/Q_engineering_tools/cryo_dashboard_v0_3_0/) | Live |

---

## Adding a New Dashboard or Tool

1. **Create a sub-folder** in the repository root, e.g. `my_new_tool/`.
2. **Add an `index.html`** (and any supporting JS/CSS/assets) inside that folder.
3. **Link it on the portal** by editing `index.html` in the repo root — copy one of
   the existing `<a class="card" …>` blocks and update the text.
4. **Commit and push** to `main`. The GitHub Actions workflow (`.github/workflows/pages.yml`)
   will redeploy the site automatically within ~60 seconds.
5. Access your tool at:
   ```
   https://gbogeb.github.io/Q_engineering_tools/<your-folder-name>/
   ```

---

## Enabling GitHub Pages (first-time setup)

If GitHub Pages is not yet enabled on this repository:

1. Go to **Settings → Pages**.
2. Under *Source*, select **GitHub Actions**.
3. Save. The next push to `main` will deploy the site.

---

## Technology

- **Hosting:** GitHub Pages (static, free, zero backend)
- **Deployment:** GitHub Actions (`.github/workflows/pages.yml`)
- **No build tools required** — pure HTML / CSS / JavaScript
- **Federation:** [`bridge_manifest.yaml`](bridge_manifest.yaml) declares CODEX → ABACUS → Q_engineering_tools data flows