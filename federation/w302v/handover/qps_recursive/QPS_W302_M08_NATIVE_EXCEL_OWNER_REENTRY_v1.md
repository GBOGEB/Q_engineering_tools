# QPS W302 — M08 native Excel owner re-entry

## Current state

M08 is internally green through the exact post-W299 equation implementation proof and controlled Word/Excel/PPT binding. The sole remaining M08 promotion gate is a real desktop Microsoft Excel clean roundtrip.

GitHub-hosted Windows retry budget is already exhausted at 2/2. Do not run a third equivalent hosted attempt.

## Why W302 exists

W291 provided a generic native-Excel runner and receipt validator. After W301, that was not strong enough for final promotion because it did not bind the external owner transaction to one exact current workbook release identity. W302 closes that stale-input gap before the external return.

Independent preparation in `GBOGEB/Q_engineering_tools#75` generated the exact current owner input and bound:

- source snapshot: `d2e495fca88752ed5efff82bd2466432ce5a8e35`
- owner input raw SHA-256: `a01b53014681f8c154c349b273c9db9686abe6f7d00b0e03d9b10f6f685f226a`
- normalized OOXML release SHA-256: `de54d5ccf3da1afcf8d517d7c22244765073798e0572ee1beef14cd0d8b9b18e`
- preparation run: `35370048827`
- job: `105681613060`
- artifact: `10558465889`
- artifact digest: `sha256:7537c3c0ed5f96d5e3749fb4f7e881dcc8bc1093b16f5b29ff1a5d6f1e6aa0d3`

Current main later advanced only through unrelated W287 closure; the five M08 payload Git blobs remain unchanged.

## Owner execution

Run from the repository root on a Windows host with installed, licensed and COM-registered desktop Microsoft Excel:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_qps_m08_native_excel_owner_reentry.ps1
```

The wrapper will:

1. verify the exact governed M08 Git blobs;
2. regenerate the workbook;
3. require the exact W302 raw and normalized release identities;
4. launch the existing native Excel transaction visibly;
5. require open-save-close-reopen with no repair mode or recovery XML signal;
6. ask the operator to type exactly `NO_REPAIR` only after observing that no repair/recovery dialog appeared;
7. emit `m08_native_excel_owner_return/QPS_M08_NATIVE_EXCEL_OWNER_REENTRY_RECEIPT.json`.

Do not edit that receipt.

Validate the returned receipt with:

```powershell
python scripts/qps_m08_validate_native_excel_owner_reentry.py m08_native_excel_owner_return/QPS_M08_NATIVE_EXCEL_OWNER_REENTRY_RECEIPT.json
```

## PASS branch

Only `PASS_VALIDATED_OWNER_NATIVE_EXCEL_CLEAN_ROUNDTRIP` admits the final M08 propagation.

Then execute exactly one:

`CODEX semantic/controller receiver -> ABACUS independent consumer -> QPS child ACCEPT/REJECT/DEFER`

and STOP/CONTROL unless a new structural red is observed.

## RED branch

If Excel actually opens and exposes a repair/recovery or workbook defect, recurse only on that observed native-Excel red.

If Microsoft Excel is unavailable on the owner host, remain externally blocked. Do not substitute LibreOffice or openpyxl.

## Guards

- no stale workbook can satisfy the owner return;
- no third equivalent hosted retry;
- no document polish creates engineering/compliance/acceptance credit;
- issue #923, G6, W152 and N200 remain independent and non-compensating;
- authority transfer remains false;
- formal credit delta remains zero.
