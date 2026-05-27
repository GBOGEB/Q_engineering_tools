# Q Engineering Tools — Dashboard & Tool Portal

> **Web-hosted hub for engineering dashboards and tools**  
> 🌐 Live site: [https://gbogeb.github.io/Q_engineering_tools/](https://gbogeb.github.io/Q_engineering_tools/)

---

## Overview

This repository is the **web-portal layer** of the three-repo engineering ecosystem:

| Repo | Role |
| --- | --- |
| **Q_engineering_tools** (this repo) | Static GitHub Pages portal — dashboard cards, tool links |
| [**ABACUS**](https://github.com/GBOGEB/ABACUS) | Downstream functional layer — Python engines, DMAIC, 12-cluster, cryo analysis |
| [**CODEX**](https://github.com/GBOGEB/CODEX) | Upstream conceptual layer — requirements, metadata, YAML glossary, federation bridge |

Everything in this repo is served directly via [GitHub Pages](https://pages.github.com) —
no server, no build step, no framework required. Dashboards are plain HTML/JS/CSS files organised in sub-folders.

---

## Repository Structure

```
Q_engineering_tools/
├── index.html                    ← Portal home page (lists all dashboards & tools)
├── .nojekyll                     ← Disables Jekyll processing on GitHub Pages
├── .github/workflows/pages.yml  ← Auto-deploy workflow (pushes to GitHub Pages)
│
├── cryo_dashboard_v0_3_0/        ← Cryo Dashboard v0.3.0 (NIST data) — LIVE
│   ├── index.html                  (full interactive dashboard from ABACUS)
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

### ABACUS Ecosystem (external)

| Dashboard | URL | Status |
| --- | --- | --- |
| 📊 ABACUS Main Dashboard | [gbogeb.github.io/ABACUS/](https://gbogeb.github.io/ABACUS/) | External |
| 🧊 Cryo Overview | [gbogeb.github.io/ABACUS/cryo/](https://gbogeb.github.io/ABACUS/cryo/) | External |
| 🔬 12-Cluster Navigator | [gbogeb.github.io/ABACUS/12-cluster/](https://gbogeb.github.io/ABACUS/12-cluster/) | External |

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

> The deploy workflow (`pages.yml`) uses `enablement: true` on the
> `configure-pages` step, so it will attempt to auto-provision Pages on first run.

---

## Technology

- **Hosting:** GitHub Pages (static, free, zero backend)
- **Deployment:** GitHub Actions (`.github/workflows/pages.yml`)
- **No build tools required** — pure HTML / CSS / JavaScript