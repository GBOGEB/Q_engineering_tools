# Q_engineering_tools — hosted Engineering Outpost and QPS federation proof lanes

<!-- markdownlint-disable MD001 MD013 MD022 MD029 MD031 MD032 MD033 MD040 MD060 -->

[![Pages deploy](https://img.shields.io/github/actions/workflow/status/GBOGEB/Q_engineering_tools/pages.yml?branch=main&style=flat-square&label=Pages%20deploy)](https://github.com/GBOGEB/Q_engineering_tools/actions/workflows/pages.yml)
[![Live site](https://img.shields.io/badge/site-gbogeb.github.io%2FQ__engineering__tools-blue?style=flat-square)](https://gbogeb.github.io/Q_engineering_tools/)
[![State: quiet since 31 Oct 2026](https://img.shields.io/badge/state-quiet%20since%2031%20Oct%202026-lightgrey?style=flat-square)](#6-status-and-open-gates)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square)](LICENSE)

> **Publishes the Engineering Outpost — the cryogenic material dashboard rebuilt byte-exact from document-organization-system with a QPS provenance overlay — on GitHub Pages, and keeps the exact-head proof lanes of the QPS federation waves.**

## At a glance

| | |
|---|---|
| **Domain** | Hosted engineering tools (cryogenic material properties) and exact-head proof workflows for QPS federation waves W162–W329: visual convergence, namespace control, offer-evaluation doctrine, reliability, native Excel round-trips |
| **EPICs carried here** | **M02A Engineering Outpost** ([`mission/M02A/`](mission/M02A/)) · **QPS federation waves** W162–W329 ([`federation/`](federation/)) · **Pages ownership** ([#104](https://github.com/GBOGEB/Q_engineering_tools/issues/104)) |
| **Owner and decision authority** | Repository owner **GBOGEB**: admission to the default branch, releases and every external grant. No agent, bot or CI verdict holds this authority. |
| **Role in the federation** | The *public outpost*: a derived, provenance-stamped publication of tools whose source of record lives elsewhere, plus proof lanes run against exact heads. |
| **Owns** | `scripts/build_cryo_pages.py` and the Pages overlay, the M02A probes, the wave proof workflows and their receipts under `federation/` |
| **Does not own** | The dashboard source and NIST data (document-organization-system) · QPS engineering truth and OCD/ADR (cryoplant-project) · federation governance (CODEX) |
| **Status snapshot** | `main@5005f53`, read 15 November 2026 — 1 open issues, 0 open PRs. [Details ↓](#6-status-and-open-gates) |

**New here?** Read [§1](#1-why-q_engineering_tools-exists--bios), then the route that matches you:

| I want to… | Open this first |
|---|---|
| Use the tools | [Live site](https://gbogeb.github.io/Q_engineering_tools/) |
| See how the site is built | [`scripts/build_cryo_pages.py`](scripts/build_cryo_pages.py) and [`pages.yml`](.github/workflows/pages.yml) |
| Find a wave's proof | [`federation/`](federation/) (one folder per wave) |
| Know what is red | [Status and open gates](#6-status-and-open-gates) |

## 1. Why Q_engineering_tools exists — BIOS

**B — Baseline.** The hosted dashboard is built from document-organization-system at pinned SHA `cea7bfb5` (11 Sep 2026), with overlay `qps-m02a-w3-pages-overlay/v1`.

**I — Identity and integrity.** The builder verifies byte identity of the source before copying; the deploy checks that the checked-out SHA equals the workflow SHA.

**O — Orchestration with ownership.** The source of record stays in document-organization-system; this repo only derives and publishes. Each wave keeps its own proof workflow and folder.

**S — Safety and source-qualified status.** The `cryo_dashboard_v0_3_0/` folder in this repo is still the old placeholder; the live site comes from the build, not from that folder.

**Where authority lives:** [`scripts/build_cryo_pages.py`](scripts/build_cryo_pages.py) (pinned source) · [`mission/M02A/FEDERATION.json`](mission/M02A/FEDERATION.json) · [`.github/workflows/pages.yml`](.github/workflows/pages.yml).

## 2. From source to decision

1. Check out document-organization-system at the pinned SHA.
2. Verify byte identity of the dashboard runtime closure.
3. Apply the QPS provenance overlay to the derived copy.
4. Run the Pages bundle tests.
5. Deploy to GitHub Pages from the exact workflow SHA.
6. Wave proof lanes run separately on exact heads and write receipts under `federation/`.

## 3. What is inside

| Block | Native source | Input → output | Boundary |
|---|---|---|---|
| Pages builder | [`scripts/build_cryo_pages.py`](scripts/build_cryo_pages.py), [`tests/test_pages_bundle.py`](tests/test_pages_bundle.py) | Pinned source → Outpost site | Derived view; source stays authoritative elsewhere |
| M02A probes | [`mission/M02A/`](mission/M02A/) | Recovered dashboard → numerics, material and NIST parity spot-checks | Probe receipts |
| Reliability lanes | [`scripts/`](scripts/) (`qps_reliability_g2…g5`) | Shared state, math, beam, cost/RCM/spares | Proof lanes, not engineering acceptance |
| Wave proofs | [`federation/`](federation/), [`carriers/`](carriers/), [`controls/`](controls/) | Exact heads → receipts per wave | Dated, wave-scoped |
| Portal | [`index.html`](index.html) | Links to hosted tools | — |

## 4. Where Q_engineering_tools sits in the federation

| Neighbour | Keeps | Interface with Q_engineering_tools |
|---|---|---|
| [document-organization-system](https://github.com/GBOGEB/document-organization-system) | Dashboard source and NIST data | Pinned source of the Pages build |
| [cryoplant-project](https://github.com/GBOGEB/cryoplant-project) (private) | QPS engineering SSOT and release identity | Engineering truth the waves serve |
| [CODEX](https://github.com/GBOGEB/CODEX) | Federation governance, contracts, wave roll-up | Governance and roll-up |

## 5. Process diagrams

Declared architecture, not a run receipt.

```mermaid
flowchart LR
  S[document-organization-system<br/>@ cea7bfb5] --> B[build_cryo_pages.py<br/>byte check + overlay]
  B --> T[test_pages_bundle] --> P[GitHub Pages<br/>Engineering Outpost]
```

## 6. Status and open gates

**Snapshot: `main@5005f53`, read 15 November 2026.** Rows point at live owners; open the link for the current position.

| Gate | Status | What would close it |
|---|---|---|
| Pages deploy | Custom deploy **succeeded** on 31 Oct 2026; the branch-source *pages build and deployment* run **fails** (looks for `/docs`) | Owner sets Pages source to GitHub Actions ([#104](https://github.com/GBOGEB/Q_engineering_tools/issues/104)) |
| Pinned source age | The build pins document-organization-system `cea7bfb5`; that commit is from 11 Sep 2026 and the dashboard has changed since | Re-pin to a current verified SHA in its own PR |
| Placeholder folder | `cryo_dashboard_v0_3_0/` still holds the placeholder page | Remove it or point it at the built site |
| Activity | Last merge 31 Oct 2026 ([#108](https://github.com/GBOGEB/Q_engineering_tools/pull/108)) | — |

## 7. Run it locally

Python **3.12** is the CI runtime.

```bash
python -m pip install pytest
python -m pytest tests -q
python scripts/build_cryo_pages.py --help   # needs a checkout of document-organization-system at the pinned SHA
```

## 8. Evidence rules and non-compensation

- **Derived is not source**: the dashboard's truth stays in document-organization-system.
- **Byte identity before publish.**
- **Exact head**: deploys and proofs bind the workflow SHA.
- **A proof lane is not acceptance.**

## 9. Repository map and next actions

| Folder | Open it for |
|---|---|
| [`scripts/`](scripts/) | Pages builder and proof scripts |
| [`mission/`](mission/) | M02A Outpost mission |
| [`federation/`](federation/) | Wave proof receipts |
| [`ocd-adr/`](ocd-adr/) | Analysis copies |
| [`tests/`](tests/) | Tests |
| [`triage/`](triage/) | Publication portal and runtime health |

**Next actions** (match §6): owner switches Pages source (#104) → re-pin the dashboard source → retire the placeholder folder.

---

BIOS: Baseline · Identity · Orchestration · Safety. Admission authority: **GBOGEB**. Licence: [Apache-2.0](LICENSE). Landing R2 on the [GEMINI skeleton](https://github.com/GBOGEB/GEMINI/blob/main/docs/landing/LANDING_SKELETON.md), snapshot `main@5005f53`.
