#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "triage/w170/QPS_W170_CROSS_SURFACE_FEATURE_MATRIX_v0.1.json"


def main():
    data = json.loads(MATRIX.read_text(encoding="utf-8"))
    cols, rows = data["pca_feature_columns"], data["rows"]
    if len(rows) != 3 or sum(int(r["accepted_sample"]) for r in rows) != 3:
        raise SystemExit("W170R PCA REJECT: requires three accepted rows")
    X = np.array([[float(r[c]) for c in cols] for r in rows], dtype=float)
    std = X.std(axis=0, ddof=1)
    if np.any(std == 0):
        raise SystemExit("W170R PCA REJECT: zero-variance feature admitted")
    Z = (X - X.mean(axis=0)) / std
    U, S, Vt = np.linalg.svd(Z, full_matrices=False)
    scores, loadings = U * S, Vt.T
    for k in range(min(2, loadings.shape[1])):
        pivot = int(np.argmax(np.abs(loadings[:, k])))
        if loadings[pivot, k] < 0:
            loadings[:, k] *= -1
            scores[:, k] *= -1
    eig = (S ** 2) / (len(rows) - 1)
    ratios = eig / eig.sum()
    ref = data["measured_small_n_pca"]
    if not np.allclose(ratios[:2], np.array(ref["explained_variance_ratio"]), atol=1e-8):
        raise SystemExit(f"W170R PCA REJECT: variance mismatch {ratios[:2]}")
    for i, row in enumerate(rows):
        if not np.allclose(scores[i, :2], np.array(ref["scores"][row["sample_id"]]), atol=1e-7):
            raise SystemExit(f"W170R PCA REJECT: score mismatch {row['sample_id']}")
    for j, col in enumerate(cols):
        if not np.allclose(loadings[j, :2], np.array(ref["loadings"][col]), atol=1e-7):
            raise SystemExit(f"W170R PCA REJECT: loading mismatch {col}")
    out = {
        "schema": "qps-w170-small-n-pca-runtime/v2",
        "state": "MEASURED_SMALL_N_ACCEPTED",
        "n_rows": 3,
        "n_features": len(cols),
        "explained_variance_ratio": [float(x) for x in ratios[:2]],
        "scores": {row["sample_id"]: [float(x) for x in scores[i, :2]] for i, row in enumerate(rows)},
        "guard": "DESCRIPTIVE_SMALL_N_ONLY_NO_CAUSAL_OR_GLOBAL_FLEET_CLAIM"
    }
    dest = ROOT / "triage/w170/QPS_W170_PCA_RUNTIME_RECEIPT.json"
    dest.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("W170R PCA PASS: measured accepted n=3 PCA reproduced")


if __name__ == "__main__":
    main()
