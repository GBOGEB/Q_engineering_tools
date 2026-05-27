<!-- markdownlint-disable MD060 -->

# 🧊 Cryogenic Material Property Dashboard — v0.4.9

**SCK CEN Engineering Tool** — 10 NIST materials · k(T) + cp(T) + Thermal
Contraction · 1–300 K

## 🌐 Quickest Access — No Install Required

### Option 1 — GitHub Pages (primary, recommended)

Open the hosted URL in any browser. No Python, no server, no install.

```text
https://gbogeb.github.io/Q_engineering_tools/cryo_dashboard_v0_3_0/index.html
```

All pages — including `dashboard_modular.html` — work directly over HTTPS. For
setup steps see
[`docs/GITHUB_PAGES_PUBLISH_GUIDE.md`](docs/GITHUB_PAGES_PUBLISH_GUIDE.md).

### Option 2 — Double-click (file://) fallback

**Legacy dashboard only** — `material_properties_dashboard_v1_10.html` is fully
self-contained. Double-click the file in Windows Explorer or macOS Finder. Opens
in any browser, no server needed.

> Note: `dashboard_modular.html` uses ES6 `import` modules which browsers block
> from `file://`. Use Option 1 or Option 3 for the modular dashboard.

### Option 3 — Local Python server (dev/test)

```bash
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/index.html
```

## 📋 Access Matrix

| Page | GitHub Pages | Double-click file:// | Local http:// |
|---|---|---|---|
| `index.html` (landing) | ✅ | ✅ | ✅ |
| `dashboard_modular.html` *(primary v0.4.9)* | ✅ | ❌ ES6 modules blocked | ✅ |
| `material_properties_dashboard_v1_10.html` *(legacy v1.10)* | ✅ | ✅ self-contained | ✅ |
| `files.html` (this navigator) | ✅ | ✅ | ✅ |
| `html_preview_hub.html` | ✅ | ✅ | ✅ |

## 📞 Contact

Organization: Studiecentrum voor Kernenergie (SCK CEN)
Version: v0.4.9
Last Updated: 2026-05-18
