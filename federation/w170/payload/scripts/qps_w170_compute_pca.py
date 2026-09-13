#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "triage/w170/QPS_W170_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"


def main():
    data = json.loads(MATRIX.read_text(encoding="utf-8"))
    cols = data["pca_feature_columns"]
    rows = data["rows"]
    X = np.array([[float(r[c]) for c in cols] for r in rows], dtype=float)
    means = X.mean(axis=0)
    std = X.std(axis=0, ddof=1)
    if np.any(std == 0):
        raise SystemExit("W170 PCA REJECT: zero-variance feature admitted")
    Z = (X - means) / std
    U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    scores = U * S
    loadings = Vt.T
    for k in range(min(2, loadings.shape[1])):
        pivot = int(np.argmax(np.abs(loadings[:, k])))
        if loadings[pivot, k] < 0:
            loadings[:, k] *= -1
            scores[:, k] *= -1
    eig = (S ** 2) / (len(rows) - 1)
    ratios = eig / eig.sum()
    ref = data["candidate_pca_reference"]
    if not np.allclose(ratios[:2], np.array(ref["explained_variance_ratio"]), atol=1e-8):
        raise SystemExit(f"W170 PCA REJECT: explained variance mismatch {ratios[:2]}")
    for i, r in enumerate(rows):
        expected = np.array(ref["scores"][r["sample_id"]])
        if not np.allclose(scores[i, :2], expected, atol=1e-7):
            raise SystemExit(f"W170 PCA REJECT: score mismatch {r['sample_id']} {scores[i, :2]}")
    for j, c in enumerate(cols):
        expected = np.array(ref["loadings"][c])
        if not np.allclose(loadings[j, :2], expected, atol=1e-7):
            raise SystemExit(f"W170 PCA REJECT: loading mismatch {c} {loadings[j, :2]}")
    out = {
        "schema": "qps-w170-small-n-pca-runtime/v1",
        "state": "CANDIDATE_COMPUTED_WITHHELD_PENDING_SAMPLE3_ACCEPTANCE",
        "n_rows": len(rows),
        "n_features": len(cols),
        "explained_variance_ratio": [float(x) for x in ratios[:2]],
        "scores": {r["sample_id"]: [float(x) for x in scores[i, :2]] for i, r in enumerate(rows)},
        "guard": "SMALL_N_DESCRIPTIVE_ONLY_NO_CAUSAL_OR_GLOBAL_FLEET_CLAIM"
    }
    dest = ROOT / "triage/w170/QPS_W170_PCA_RUNTIME_RECEIPT.json"
    dest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("W170 PCA PASS: n=3 candidate PCA reproduced; admission still withheld pending Sample #3 acceptance")


if __name__ == "__main__":
    main()
