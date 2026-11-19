"""W389 source-integrity / temporal-score adversarial regression (synthetic data only)."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import five_original_score as gate


def fixture(root, count=5):
    docs = []
    for i, (ident, family) in enumerate(gate.FAMILIES.items()):
        if i >= count:
            break
        source = root / f"synthetic{i}.bin"
        source.write_bytes(f"SYNTHETIC-NOT-OWNER-{i}".encode())
        h = gate.sha(source.read_bytes())
        qa_file = root / f"synthetic_native_qa_{i}.json"
        qa_bytes = (json.dumps({
            "schema": "qps.w390.native-qa-receipt.v1",
            "source_id": ident, "source_sha256": h, "family": family,
            "status": "PASS", "generator_sha256": gate.sha(f"GEN-{i}".encode()),
            "checks": ["SYNTHETIC_FIXTURE_NOT_ENGINEERING_ACCEPTANCE"],
        }, sort_keys=True) + "\n").encode()
        qa_file.write_bytes(qa_bytes)
        docs.append({"id": ident, "family": family, "sha256": h,
                     "local_path": str(source),
                     "native_qa": {"status": "PASS", "source_sha256": h,
                                   "receipt_sha256": gate.sha(qa_bytes),
                                   "receipt_path": str(qa_file)}})
    return {"schema": gate.SCHEMA, "authority_transfer": False,
            "publication_approval": False, "documents": docs, "runs": []}


def trials(data, n=5):
    data["runs"] = [
        {"workers": width, "trial": i, "wall_seconds": 10 / width + i / 10,
         "documents": [{"id": d["id"], "source_sha256": d["sha256"],
                        "semantic_sha256": gate.sha(d["id"].encode()),
                        "process_seconds": 0.1} for d in data["documents"]]}
        for width in (1, 2, 4) for i in range(1, n + 1)
    ]
    return data


class FiveOriginal(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.data = fixture(self.root)

    def test_missing_runs_withhold(self):
        x = gate.analyze(self.data)
        self.assertIsNone(x["p50_seconds"]["1"])
        self.assertEqual(x["merge_admission"], "HOLD")

    def test_complete_synthetic_never_releases_scale_metrics_or_owner_credit(self):
        x = gate.analyze(trials(self.data))
        self.assertEqual(
            x["comparability"],
            "WITHHELD_OWNER_SOURCE_OR_NATIVE_QA_CONTRACT_NOT_PINNED",
        )
        self.assertFalse(x["owner_source_contract_complete"])
        self.assertEqual(x["owner_source_pins_matched"], 0)
        self.assertIsNone(x["p50_seconds"]["1"])
        self.assertIsNone(x["p95_seconds"]["4"])
        self.assertIsNone(x["claimed_improvement"])
        self.assertEqual(x["engineering_admission"], "HOLD")

    def test_self_authored_receipts_cannot_bootstrap_owner_pin_contract(self):
        data = trials(self.data)
        for row in data["documents"]:
            self.assertTrue(Path(row["local_path"]).is_file())
            self.assertTrue(Path(row["native_qa"]["receipt_path"]).is_file())
        x = gate.analyze(data)
        self.assertEqual(x["native_qa_receipt_bytes_verified"], 0)
        self.assertEqual(x["owner_source_pins_matched"], 0)
        self.assertIsNone(x["p50_seconds"]["2"])

    def test_four_originals_withheld(self):
        x = gate.analyze(trials(fixture(self.root, 4)))
        self.assertIsNone(x["p95_seconds"]["4"])

    def test_insufficient_trial_population_withheld(self):
        x = gate.analyze(trials(self.data, 4))
        self.assertIsNone(x["p50_seconds"]["2"])

    def test_duplicate_original_hash_fails(self):
        self.data["documents"][1]["sha256"] = self.data["documents"][0]["sha256"]
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_INVALID_OR_REUSED"):
            gate.analyze(self.data)

    def test_role_swap_fails(self):
        self.data["documents"][0]["family"] = "MECHANICAL_PID"
        with self.assertRaisesRegex(ValueError, "SOURCE_FAMILY_SWAP"):
            gate.analyze(self.data)

    def test_tampered_original_bytes_fails(self):
        Path(self.data["documents"][0]["local_path"]).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SOURCE_BYTES_SHA_DRIFT"):
            gate.analyze(self.data)

    def test_double_trial_rejected(self):
        trials(self.data)
        self.data["runs"].append(copy.deepcopy(self.data["runs"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_TRIAL"):
            gate.analyze(self.data)

    def test_semantic_change_rejected(self):
        trials(self.data)
        self.data["runs"][1]["documents"][0]["semantic_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "CROSS_WORKER_SEMANTIC_DRIFT"):
            gate.analyze(self.data)

    def test_trial_relabel_rejected(self):
        trials(self.data)
        self.data["runs"][0]["documents"][0]["id"] = "PID-QCELL"
        with self.assertRaisesRegex(ValueError, "TRIAL_SOURCE_SHA_DRIFT"):
            gate.analyze(self.data)

    def test_nonfinite_wall_clock_rejected(self):
        trials(self.data)
        self.data["runs"][0]["wall_seconds"] = float("nan")
        with self.assertRaisesRegex(ValueError, "WALL_CLOCK_INVALID"):
            gate.analyze(self.data)

    def test_authority_promotion_rejected(self):
        self.data["authority_transfer"] = True
        with self.assertRaisesRegex(ValueError, "AUTHORITY_ESCALATION"):
            gate.analyze(self.data)

    def test_missing_native_receipt_withheld(self):
        self.data["documents"][0]["native_qa"]["status"] = "DEFER"
        x = gate.analyze(trials(self.data))
        self.assertIsNone(x["p50_seconds"]["1"])

    def test_forged_qa_digest_fails_closed(self):
        doc = self.data["documents"][0]
        doc["native_qa"]["receipt_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "NATIVE_RECEIPT_BYTES_SHA_DRIFT"):
            gate.analyze(self.data)

    def test_declared_receipt_without_bytes_withholds_metrics(self):
        self.data["documents"][0]["native_qa"].pop("receipt_path")
        x = gate.analyze(trials(self.data))
        self.assertEqual(x["native_qa_receipts_declared"], 5)
        self.assertEqual(x["native_qa_receipt_bytes_verified"], 4)
        self.assertIsNone(x["p50_seconds"]["1"])

    def test_qa_receipt_source_context_swap_fails_closed(self):
        doc = self.data["documents"][0]
        receipt_path = Path(doc["native_qa"]["receipt_path"])
        payload = json.loads(receipt_path.read_text())
        payload["source_id"] = "PID-RFCELL"
        raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
        receipt_path.write_bytes(raw)
        doc["native_qa"]["receipt_sha256"] = gate.sha(raw)
        with self.assertRaisesRegex(ValueError,
                                     "NATIVE_RECEIPT_SOURCE_OR_TEST_CONTEXT_INVALID"):
            gate.analyze(self.data)

    def test_qa_receipt_source_digest_swap_fails_closed(self):
        doc = self.data["documents"][0]
        receipt_path = Path(doc["native_qa"]["receipt_path"])
        payload = json.loads(receipt_path.read_text())
        payload["source_sha256"] = "f" * 64
        raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
        receipt_path.write_bytes(raw)
        doc["native_qa"]["receipt_sha256"] = gate.sha(raw)
        with self.assertRaisesRegex(ValueError,
                                     "NATIVE_RECEIPT_SOURCE_OR_TEST_CONTEXT_INVALID"):
            gate.analyze(self.data)

    def test_html_private_paths_excluded(self):
        page = gate.html_report(gate.analyze(self.data))
        self.assertNotIn(str(self.root), page)
        self.assertIn("WITHHELD", page)
        self.assertIn("HOLD", page)

    def test_long_withheld_token_wraps_on_mobile(self):
        report = gate.html_report(gate.analyze(self.data))
        self.assertIn("overflow-wrap:anywhere", report)
        self.assertIn("word-break:break-word", report)
        self.assertIn("WITHHELD", report)

    def test_cli_source_pin_and_output_collision(self):
        manifest = self.root / "private_manifest.json"
        raw = (json.dumps(self.data) + "\n").encode()
        manifest.write_bytes(raw)
        out = self.root / "score"
        args = ["--manifest", str(manifest),
                "--expected-sha256", gate.sha(raw), "--out", str(out)]
        gate.main(args)
        self.assertEqual(json.loads((out / "score.json").read_text())["merge_admission"],
                         "HOLD")
        with self.assertRaisesRegex(ValueError, "OUTPUT_COLLISION_OR_ALIAS"):
            gate.main(args)
        args[3] = "0" * 64
        with self.assertRaisesRegex(ValueError, "INPUT_MANIFEST_SHA_DRIFT"):
            gate.main(args)


if __name__ == "__main__":
    unittest.main()
