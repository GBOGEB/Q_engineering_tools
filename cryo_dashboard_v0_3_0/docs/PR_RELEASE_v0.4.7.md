# PR Release Notes — v0.4.7

## PR Title

`release(v0.4.7): comparison normalization modes + canonical artifact refresh`

## Description

Adds comparison-view mode control with raw, normalized, and split modes. Resolves overlay duplication and adds overlay count limit.

## Changes

### Added
- B1 comparison mode selector: raw, normalized, split
- B1N panel in split mode for shape comparison
- `MAX_COMPARISON_OVERLAYS = 4` limit with status messaging

### Fixed
- Comparison selector now disables unavailable properties per material
- Primary material not duplicated in comparison overlays
- Theme toggle label shows explicit state
