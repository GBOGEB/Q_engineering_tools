# CDN Version Pinning — Cryogenic Material Dashboard v0.4.9

> Locked: 2026-05-18

## Pinned Libraries

| Library | Version | CDN URL | Used In |
|---------|---------|---------|---------|
| Plotly.js | **2.35.2** | `https://cdn.plot.ly/plotly-2.35.2.min.js` | `dashboard_modular.html`, `ssot_launcher.html`, `index_slides.html` |
| Reveal.js | **4.6.1** | `https://cdn.jsdelivr.net/npm/reveal.js@4.6.1/` | `index_slides.html` |

## Why Pin?

- **Reproducibility**: Charts and slides render identically across deployments.
- **No surprise breakage**: CDN updates won't silently change behavior.
- **Audit trail**: Each version bump is a deliberate, tested decision.

## Updating CDN Versions

1. Test the new version locally with `npm test` and manual chart inspection.
2. Update all HTML files referencing the library.
3. Update this document.
4. Bump dashboard version in `package.json` and `VERSION`.
