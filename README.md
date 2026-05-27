# Q Engineering Tools — Dashboard & Tool Portal

> **Web-hosted hub for engineering dashboards and tools**  
> 🌐 Live site: [https://gbogeb.github.io/Q_engineering_tools/](https://gbogeb.github.io/Q_engineering_tools/)

---

## Overview

This repository is a **standalone, statically-hosted platform** for engineering
dashboards and tools. Everything is served directly via
[GitHub Pages](https://pages.github.com) — no server, no build step, no framework
required. Dashboards are plain HTML/JS/CSS files organised in sub-folders.

---

## Repository Structure

```
Q_engineering_tools/
├── index.html                    ← Portal home page (lists all dashboards & tools)
├── .nojekyll                     ← Disables Jekyll processing on GitHub Pages
├── .github/workflows/pages.yml  ← Auto-deploy workflow (pushes to GitHub Pages)
├── FEDERATION.md                 ← Ecosystem bridge & asset provenance log
│
├── cryo_dashboard_v0_3_0/        ← Cryo Dashboard v0.3.0 (NIST data, from ABACUS)
│   ├── index.html                  (live dashboard — Chart.js, NIST reference data)
│   └── README.md
│
└── <future_tool_or_dashboard>/   ← Add new tools/dashboards here
    └── index.html
```

---

## Dashboards

| Dashboard | Version | URL | Status |
| --- | --- | --- | --- |
| 🧊 Cryo Dashboard | v0.3.0 | [`/cryo_dashboard_v0_3_0/`](https://gbogeb.github.io/Q_engineering_tools/cryo_dashboard_v0_3_0/) | ✅ Live |

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

## Deploying Cryo Dashboard v0.3.0

The `cryo_dashboard_v0_3_0/index.html` contains the **live NIST cryo dashboard**
(sourced from [GBOGEB/ABACUS](https://github.com/GBOGEB/ABACUS)).  
It uses Chart.js 4.4.0 (CDN) and requires no backend.

To update to a newer version of the dashboard:

1. Copy the updated `index.html` from `ABACUS/cryo_dashboard_v0_3_0/index.html`.
2. Update the version badge in the root `index.html` card and in `FEDERATION.md`.
3. Push to `main` — GitHub Pages will update automatically.

---

## Technology

- **Hosting:** GitHub Pages (static, free, zero backend)
- **Deployment:** GitHub Actions (`.github/workflows/pages.yml`)
- **No build tools required** — pure HTML / CSS / JavaScript

---

## Ecosystem & Federation

This repo is the **web-host layer** of a three-repo engineering toolchain:

| Repo | Role |
|------|------|
| [GBOGEB/CODEX](https://github.com/GBOGEB/CODEX) | Upstream conceptual — requirements, ADRs, YAML manifests |
| [GBOGEB/ABACUS](https://github.com/GBOGEB/ABACUS) | Downstream functional — Python engines, cryo dashboard source |
| **GBOGEB/Q_engineering_tools** | Web-host — static GitHub Pages presentation layer |

See [`FEDERATION.md`](FEDERATION.md) for the full ecosystem map, asset provenance
table, and stale/drift log.