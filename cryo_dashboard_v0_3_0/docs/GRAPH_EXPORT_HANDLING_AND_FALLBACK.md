# Graph Export Handling and Fallback

## Export Options

The dashboard provides three export formats:

| Format | Action | Notes |
|--------|--------|-------|
| PNG | Plotly `downloadImage` | Uses Plotly's SVG-to-canvas pipeline; requires modern browser |
| CSV | Custom export via `js/export.js` | All visible traces exported as delimited data |
| JSON | Full state snapshot | Includes material selection, T range, and computed integral |

## Fallback Behavior

If `Plotly.downloadImage` fails (e.g., cross-origin iframe context):
1. The app catches the error and logs to console.
2. A user-visible status message in the export panel explains the issue.
3. CSV and JSON export remain available as fallbacks.

## Implementation

See `js/export.js` — `exportPNG()`, `exportCSV()`, `exportJSON()` functions.

Export state is tracked in `js/state.js`.
