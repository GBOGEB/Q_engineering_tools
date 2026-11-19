"""W389 read-only score over FIVE owner-original source documents; never an executor."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import statistics

FAMILIES = {
    "SLD-EDB700": "ELECTRICAL_SLD", "SLD-EDB701": "ELECTRICAL_SLD",
    "PID-QCELL": "MECHANICAL_PID", "PID-RFCELL": "MECHANICAL_PID",
    "TS-E07": "THERMAL_TS",
}
SCHEMA = "qps.w389.five-original-score.v1"
WIDTHS = (1, 2, 4)

# Metric release is fail-closed until the owner supplies immutable, reviewed
# per-role source and native-QA contracts. Self-authored manifests/receipts
# cannot bootstrap a "five original" scale result.
OWNER_SOURCE_CONTRACT = {
    ident: {"source_sha256": None, "generator_sha256": None, "checks": ()}
    for ident in FAMILIES
}


def require(condition, error):
    if not condition:
        raise ValueError(error)


def valid_sha(value):
    return (isinstance(value, str) and len(value) == 64
            and set(value) <= set("0123456789abcdef"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def quantile(values, p):
    values = sorted(values)
    if not values:
        return None
    i = (len(values) - 1) * p
    lo, hi = math.floor(i), math.ceil(i)
    return round(values[lo] + (values[hi] - values[lo]) * (i - lo), 6)


def analyze(manifest):
    require(isinstance(manifest, dict) and manifest.get("schema") == SCHEMA,
            "SCHEMA_INVALID")
    require(manifest.get("authority_transfer") is False
            and manifest.get("publication_approval") is False,
            "AUTHORITY_ESCALATION")
    documents = manifest.get("documents")
    require(isinstance(documents, list), "DOCUMENTS_INVALID")
    seen, hashes, rows = set(), set(), []
    for document in documents:
        require(isinstance(document, dict), "DOCUMENT_INVALID")
        ident = document.get("id")
        require(isinstance(ident, str) and ident in FAMILIES
                and ident not in seen, "SOURCE_ID_UNKNOWN_OR_DUPLICATE")
        require(document.get("family") == FAMILIES[ident], "SOURCE_FAMILY_SWAP")
        frozen = document.get("sha256")
        require(valid_sha(frozen) and frozen not in hashes,
                "SOURCE_HASH_INVALID_OR_REUSED")
        contract = OWNER_SOURCE_CONTRACT[ident]
        expected_source = contract.get("source_sha256")
        source_pin_configured = valid_sha(expected_source)
        if source_pin_configured:
            require(frozen == expected_source, "OWNER_SOURCE_PIN_MISMATCH")
        seen.add(ident)
        hashes.add(frozen)
        location = document.get("local_path")
        verified = False
        if location is not None:
            require(isinstance(location, str) and location, "SOURCE_PATH_INVALID")
            file = Path(location)
            require(file.is_file() and not file.is_symlink(),
                    "SOURCE_MISSING_OR_SYMLINK")
            h = hashlib.sha256()
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1048576), b""):
                    h.update(chunk)
            require(h.hexdigest() == frozen, "SOURCE_BYTES_SHA_DRIFT")
            verified = True
        qa = document.get("native_qa") or {}
        require(isinstance(qa, dict), "NATIVE_QA_INVALID")
        receipt = qa.get("receipt_sha256")
        if receipt is not None:
            require(valid_sha(receipt), "NATIVE_QA_RECEIPT_HASH_INVALID")
        qa_declared = (qa.get("status") == "PASS"
                       and qa.get("source_sha256") == frozen
                       and receipt is not None)
        # A string in a manifest is not a verified receipt. Read and hash the
        # receipt bytes, bind the documented source and tested generator, and
        # keep independent owner approval outside this analytical verifier.
        qa_verified = False
        receipt_path = qa.get("receipt_path")
        if receipt_path is not None:
            require(isinstance(receipt_path, str) and receipt_path,
                    "NATIVE_RECEIPT_PATH_INVALID")
            source_receipt = Path(receipt_path)
            require(source_receipt.is_file() and not source_receipt.is_symlink(),
                    "NATIVE_RECEIPT_MISSING_OR_SYMLINK")
            content = source_receipt.read_bytes()
            require(receipt is not None and sha(content) == receipt,
                    "NATIVE_RECEIPT_BYTES_SHA_DRIFT")
            try:
                record = json.loads(content)
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("NATIVE_RECEIPT_JSON_INVALID") from exc
            require(isinstance(record, dict)
                    and record.get("schema") == "qps.w390.native-qa-receipt.v1"
                    and record.get("source_id") == ident
                    and record.get("source_sha256") == frozen
                    and record.get("family") == FAMILIES[ident]
                    and record.get("status") == "PASS"
                    and valid_sha(record.get("generator_sha256"))
                    and isinstance(record.get("checks"), list)
                    and len(record["checks"]) > 0
                    and all(isinstance(check, str) and check
                            for check in record["checks"]),
                    "NATIVE_RECEIPT_SOURCE_OR_TEST_CONTEXT_INVALID")
            expected_generator = contract.get("generator_sha256")
            expected_checks = tuple(contract.get("checks") or ())
            qa_contract_configured = (
                source_pin_configured and valid_sha(expected_generator)
                and bool(expected_checks)
            )
            if qa_contract_configured:
                require(record.get("generator_sha256") == expected_generator,
                        "OWNER_NATIVE_QA_GENERATOR_PIN_MISMATCH")
                require(tuple(record.get("checks") or ()) == expected_checks,
                        "OWNER_NATIVE_QA_CHECK_CONTRACT_MISMATCH")
            qa_verified = qa_declared and qa_contract_configured
        rows.append({"id": ident, "family": FAMILIES[ident], "sha256": frozen,
                     "local_bytes_verified": verified,
                     "owner_source_pin_configured": source_pin_configured,
                     "owner_source_pin_matched": source_pin_configured and frozen == expected_source,
                     "native_qa_receipt_declared": qa_declared,
                     "native_qa_receipt_bytes_verified": qa_verified})
    runs = manifest.get("runs") or []
    require(isinstance(runs, list), "RUNS_INVALID")
    census = {w: [] for w in WIDTHS}
    trials = set()
    semantic = {}
    for run in runs:
        require(isinstance(run, dict), "RUN_INVALID")
        width, trial = run.get("workers"), run.get("trial")
        require(type(width) is int and width in WIDTHS
                and type(trial) is int and trial >= 1, "WORKER_OR_TRIAL_INVALID")
        require((width, trial) not in trials, "DUPLICATE_TRIAL")
        trials.add((width, trial))
        wall = run.get("wall_seconds")
        require(type(wall) in (int, float) and math.isfinite(wall)
                and wall > 0, "WALL_CLOCK_INVALID")
        readings = run.get("documents")
        require(isinstance(readings, list) and len(readings) == len(rows),
                "TRIAL_DOCUMENT_CENSUS_DRIFT")
        found = set()
        for reading in readings:
            require(isinstance(reading, dict), "TRIAL_DOCUMENT_INVALID")
            ident = reading.get("id")
            require(isinstance(ident, str) and ident in seen
                    and ident not in found, "TRIAL_SOURCE_UNKNOWN_OR_DUPLICATE")
            found.add(ident)
            expected = next(d["sha256"] for d in rows if d["id"] == ident)
            require(reading.get("source_sha256") == expected, "TRIAL_SOURCE_SHA_DRIFT")
            digest = reading.get("semantic_sha256")
            require(valid_sha(digest), "SEMANTIC_HASH_INVALID")
            require(ident not in semantic or semantic[ident] == digest,
                    "CROSS_WORKER_SEMANTIC_DRIFT")
            semantic[ident] = digest
            elapsed = reading.get("process_seconds")
            require(type(elapsed) in (int, float) and math.isfinite(elapsed)
                    and elapsed >= 0, "PROCESS_CLOCK_INVALID")
        census[width].append(float(wall))
    owner_contract_complete = (
        set(OWNER_SOURCE_CONTRACT) == set(FAMILIES)
        and all(valid_sha(OWNER_SOURCE_CONTRACT[i].get("source_sha256"))
                and valid_sha(OWNER_SOURCE_CONTRACT[i].get("generator_sha256"))
                and bool(tuple(OWNER_SOURCE_CONTRACT[i].get("checks") or ()))
                for i in FAMILIES)
    )
    complete = (owner_contract_complete
                and seen == set(FAMILIES)
                and all(d["local_bytes_verified"] for d in rows)
                and all(d["owner_source_pin_matched"] for d in rows)
                and all(d["native_qa_receipt_bytes_verified"] for d in rows)
                and all(len(census[w]) >= 5 for w in WIDTHS))
    return {
        "schema": SCHEMA,
        "frozen_originals_expected": 5, "distinct_original_ids_declared": len(seen),
        "source_rows": sorted(rows, key=lambda d: d["id"]),
        "local_byte_hash_verified": sum(d["local_bytes_verified"] for d in rows),
        "native_qa_receipts_declared": sum(d["native_qa_receipt_declared"] for d in rows),
        "native_qa_receipt_bytes_verified": sum(d["native_qa_receipt_bytes_verified"] for d in rows),
        "owner_source_contract_complete": owner_contract_complete,
        "owner_source_pins_matched": sum(d["owner_source_pin_matched"] for d in rows),
        "trials": {str(w): len(census[w]) for w in WIDTHS},
        "semantic_replay_consistent": True,
        "comparability": ("COMPLETE_BYTE_VERIFIED_RECEIPTS_NOT_OWNER_ADMITTED"
                          if complete else
                          ("WITHHELD_OWNER_SOURCE_OR_NATIVE_QA_CONTRACT_NOT_PINNED"
                           if not owner_contract_complete else
                           "WITHHELD_MISSING_FIVE_ORIGINALS_NATIVE_RECEIPTS_OR_FIVE_TRIALS")),
        "p50_seconds": {str(w): quantile(census[w], .5) if complete else None
                        for w in WIDTHS},
        "p95_seconds": {str(w): quantile(census[w], .95) if complete else None
                        for w in WIDTHS},
        "claimed_improvement": None,
        "owner_acceptance": "WITHHELD_EXTERNAL_SIGNATURE_REQUIRED",
        "independent_visual_review": "WITHHELD_EXTERNAL_ACROBAT_RECEIPT",
        "engineering_admission": "HOLD", "publication_admission": "HOLD",
        "merge_admission": "HOLD", "authority_transfer": False,
        "evidence_class": "LOCAL_READ_ONLY_ANALYTICAL_VERIFICATION",
    }


def html_report(result):
    def esc(value):
        return html.escape(str(value))
    cards = [
        ("Distinct owner source IDs", result["distinct_original_ids_declared"]),
        ("Locally verified source bytes", result["local_byte_hash_verified"]),
        ("Native QA receipts (byte-checked)", result["native_qa_receipt_bytes_verified"]),
        ("1 / 2 / 4 trial counts",
         " / ".join(str(result["trials"][str(w)]) for w in WIDTHS)),
        ("p50 / p95 (1 worker)",
         "WITHHELD" if result["p50_seconds"]["1"] is None else
         f'{result["p50_seconds"]["1"]} s / {result["p95_seconds"]["1"]} s'),
        ("Engineering / publication", "HOLD / HOLD"),
    ]
    tiles = "".join(f"<section><small>{esc(label)}</small><strong>{esc(value)}</strong></section>"
                    for label, value in cards)
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>W389 Five Originals</title><style>body{font-family:Arial,sans-serif;"
            "background:#fcf9fc;color:#341441;max-width:1100px;margin:2rem auto;padding:1rem;"
            "overflow-wrap:anywhere;word-break:break-word}"
            "main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));"
            "gap:1rem}section{background:white;border:1px solid #cfb7d7;border-radius:10px;"
            "padding:1rem;overflow-wrap:anywhere}small{display:block;color:#715b76;"
            "margin-bottom:.75rem}strong{font-size:1.3rem}</style>"
            "<h1>W389 · Five original drawings</h1>"
            "<p>Read-only source evidence. No owner, engineering, merge or publication credit.</p>"
            f"<main>{tiles}</main><p>Comparability: {esc(result['comparability'])}</p>"
            "</html>\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--expected-sha256", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    require(valid_sha(args.expected_sha256), "INPUT_MANIFEST_PIN_INVALID")
    raw = args.manifest.read_bytes()
    require(sha(raw) == args.expected_sha256, "INPUT_MANIFEST_SHA_DRIFT")
    report = analyze(json.loads(raw))
    out = args.out.resolve()
    require(out != args.manifest.resolve() and not out.exists(), "OUTPUT_COLLISION_OR_ALIAS")
    for ancestor in (out, *out.parents):
        require(not (ancestor / ".git").exists(), "OUTPUT_INSIDE_GIT_ROOT")
    out.mkdir(parents=True, exist_ok=False)
    score = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    view = html_report(report).encode()
    (out / "score.json").write_bytes(score)
    (out / "index.html").write_bytes(view)
    (out / "SHA256SUMS").write_text(
        f"{sha(score)}  score.json\n{sha(view)}  index.html\n")
    print(json.dumps({"comparability": report["comparability"],
                      "source_count": report["distinct_original_ids_declared"],
                      "merge_admission": "HOLD"}))


if __name__ == "__main__":
    main()
