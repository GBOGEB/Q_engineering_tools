# Q Engineering Tools — Dashboard & Tool Portal

> **Web-hosted hub for engineering dashboards and tools**  
> 🌐 Live site: [https://gbogeb.github.io/Q_engineering_tools/](https://gbogeb.github.io/Q_engineering_tools/)

---

## Overview

This repository is a **standalone, statically-hosted platform** for engineering
dashboards and tools. Everything is served directly via
[GitHub Pages](https://pages.github.com) — no server, no build step, no framework
required. Dashboards are plain HTML/JS/CSS files organised in sub-folders.

It is the **display layer** of the three-repo federation:

| Repo | Role |
|------|------|
| **Q_engineering_tools** | `downstream_display` — this portal |
| **[ABACUS](https://github.com/GBOGEB/ABACUS)** | `downstream_functional` — 12-Cluster analysis framework |
| **[CODEX](https://github.com/GBOGEB/CODEX)** | `upstream_conceptual` — federation/telemetry bootstrap |

Federation thresholds (W000): drift ≤ 0.45 · federation ≥ 0.40  
See [`bridge_manifest.yaml`](bridge_manifest.yaml) for the full federation declaration.

---

## Repository Structure

```
Q_engineering_tools/
├── index.html                         ← Portal home page (all dashboards & tools)
├── bridge_manifest.yaml               ← Three-repo federation declaration (W000)
├── .nojekyll                          ← Disables Jekyll on GitHub Pages
├── .github/
│   └── workflows/
│       ├── pages.yml                  ← Auto-deploy to GitHub Pages on push to main
│       └── federation-check.yml      ← CODEX W000 drift/federation gate
│
├── cryo_dashboard_v0_3_0/             ← Cryo Dashboard (NIST material properties)
│   ├── index.html                       Version picker + launcher
│   ├── material_properties_dashboard_v1_10.html  ← Main interactive dashboard
│   ├── dashboard_modular.html           Modular JS dashboard
│   ├── style.css
│   ├── data/
│   │   └── materials.json              NIST cryogenic material properties
│   └── js/                             Modular JS files
│
└── tools/drift_report/                ← Federation drift reports (CI artefacts)
    └── latest.json
```

---

## Dashboards

| Dashboard | Version | URL | Status |
| --- | --- | --- | --- |
| 🧊 Cryo Dashboard | v0.4.9 | [`/cryo_dashboard_v0_3_0/`](https://gbogeb.github.io/Q_engineering_tools/cryo_dashboard_v0_3_0/) | Live |
| 🔬 ABACUS Cryo Analysis | v4.4.0 | [`ABACUS/cryo/`](https://gbogeb.github.io/ABACUS/cryo/index.html) | ABACUS Pages |
| 🗺️ 12-Cluster Navigator | v4.4.0 | [`ABACUS/12-cluster/`](https://gbogeb.github.io/ABACUS/12-cluster/index.html) | ABACUS Pages |
| 📊 Deep Analysis Dashboard | v4.4.0 | [`ABACUS/deep_analysis_dashboard.html`](https://gbogeb.github.io/ABACUS/deep_analysis_dashboard.html) | ABACUS Pages |
| 📈 Progress Tracker | v4.4.0 | [`ABACUS/progress_tracker.html`](https://gbogeb.github.io/ABACUS/progress_tracker.html) | ABACUS Pages |

## Tools

| Tool | Repo | Description |
| --- | --- | --- |
| 📡 CODEX Drift Monitor | [CODEX](https://github.com/GBOGEB/CODEX/blob/main/telemetry/pca/drift_monitor.py) | W000 PCA drift check |
| 📋 DOW Governance | [ABACUS](https://gbogeb.github.io/ABACUS/dow/index.html) | Workflow compliance |
| 🧪 Testing Dashboard | [ABACUS](https://gbogeb.github.io/ABACUS/testing/index.html) | CI/CD + coverage |

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
- **Federation CI gate:** GitHub Actions (`.github/workflows/federation-check.yml`)
- **No build tools required** — pure HTML / CSS / JavaScript
