# Federation & Ecosystem Bridge

> **Q_engineering_tools** is the **web-hosting layer** of the GBOGEB engineering
> toolchain. It draws assets from CODEX (upstream conceptual) and ABACUS (downstream
> functional) and exposes them as static GitHub Pages dashboards.

---

## Ecosystem Map

```
CODEX  (upstream conceptual)
  │  Requirements, ADRs, glossary, YAML manifests, books
  │
  ├──► bridge_manifest.yaml  ─────────────────────────────────────┐
  │                                                                │
ABACUS  (downstream functional)                              federation
  │  Python engines, calculation schemas, cryo physics,          layer
  │  cryo_dashboard_v0_3_0/index.html (NIST source)              │
  │                                                               │
  └──► Q_engineering_tools  (web-host / presentation layer) ◄───┘
         GitHub Pages · static HTML/JS/CSS · zero backend
         https://gbogeb.github.io/Q_engineering_tools/
```

---

## Repository Roles

| Repo | Role | Bridge Direction |
|------|------|-----------------|
| [GBOGEB/CODEX](https://github.com/GBOGEB/CODEX) | Upstream conceptual — requirements, ADRs, YAML manifests | CODEX → Q_engineering_tools (via ABACUS) |
| [GBOGEB/ABACUS](https://github.com/GBOGEB/ABACUS) | Downstream functional — Python engines, cryo dashboard source | ABACUS → Q_engineering_tools (file promotion) |
| **GBOGEB/Q_engineering_tools** | Web-host / presentation layer | Consumes assets from ABACUS |
| [GBOGEB/document-organization-system](https://github.com/GBOGEB/document-organization-system) | Document archive / original cryo source | Reference only |

---

## Asset Provenance

| Asset in Q_engineering_tools | Source | Last synced |
|-------------------------------|--------|-------------|
| `cryo_dashboard_v0_3_0/index.html` | `ABACUS/cryo_dashboard_v0_3_0/index.html` (SHA `36fa0dc`) | 2026-05-27 |

---

## Sync Policy

1. **Cryo Dashboard** — copy `ABACUS/cryo_dashboard_v0_3_0/index.html` to this
   repo whenever ABACUS ships a new dashboard release. Update the version badge in
   `index.html` and this table.
2. **New tools** — create a sub-folder here, link it in `index.html`, and record
   provenance in the table above.
3. **CODEX federation** — `bridge_manifest.yaml` in CODEX should be updated to add
   `q_engineering_tools` as a third node with `role: web_host`.

---

## Stale / Drift Log

| Item | Status | Action |
|------|--------|--------|
| PR #3 (`copilot/fix-ci-deployment-issue`) | **Stale — already merged** via PR #2 | Close PR #3 |
| `cryo_dashboard_v0_3_0/index.html` placeholder | **Resolved** — replaced with real ABACUS dashboard | Done (2026-05-27) |
| `bridge_manifest.yaml` in CODEX missing Q_engineering_tools | **Open** — CODEX repo update required | Raise in CODEX |
