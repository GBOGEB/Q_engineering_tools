param(
    [string]$OutputDir = "m08_native_excel_owner_return"
)

$ErrorActionPreference = 'Stop'

$ExpectedSourceCommit = 'd2e495fca88752ed5efff82bd2466432ce5a8e35'
$ExpectedRawSha = 'a01b53014681f8c154c349b273c9db9686abe6f7d00b0e03d9b10f6f685f226a'
$ExpectedNormalizedSha = 'de54d5ccf3da1afcf8d517d7c22244765073798e0572ee1beef14cd0d8b9b18e'

$ExpectedBlobs = [ordered]@{
    'controls/QPS_OFFER_EVAL_SCORING_DOCTRINE_v1.yaml' = '52592fee795bd19d151f0b7612642d28f5a6a88d'
    'controls/QPS_OFFER_EVAL_EQUATION_CURRENT_v1.yaml' = '2bda13cc9a5353986ebe6f9d3adc7a45e3a611c3'
    'controls/QPS_OFFER_EVAL_WORKBOOK_DELTA_2026-09-14_v1.yaml' = '2eed4189bef5361bdf25ef79c2e7d1f32a18590e'
    'scripts/qps_w183_generate_offer_eval_workbook.py' = '77b69c721d84434ac5c81269df757d95c512637a'
    'scripts/qps_ooxml_normalized_release_identity.py' = 'ad9c549a2b205d94dad80d33cd279487f321ac71'
    'scripts/qps_m08_native_excel_roundtrip.ps1' = '0323123732a3b5897881f5c41654bf74fc15069f'
}

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Write-FinalReceipt([hashtable]$Receipt, [string]$Path, [int]$ExitCode) {
    $Receipt.finalized_utc = (Get-Date).ToUniversalTime().ToString('o')
    $Receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding UTF8
    Write-Output ($Receipt | ConvertTo-Json -Depth 12)
    exit $ExitCode
}

$repoRoot = (Get-Location).Path
$out = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDir))
New-Item -ItemType Directory -Force -Path $out | Out-Null

$finalReceiptPath = Join-Path $out 'QPS_M08_NATIVE_EXCEL_OWNER_REENTRY_RECEIPT.json'
$workbookPath = Join-Path $out 'OFFER_EVAL_MIP2A_OWNER_INPUT.xlsx'
$generatorReceipt = Join-Path $out 'W302_GENERATOR_RECEIPT.json'
$identityReceipt = Join-Path $out 'W302_NORMALIZED_IDENTITY.json'
$nativeReceiptPath = Join-Path $out 'QPS_M08_NATIVE_EXCEL_TECHNICAL_RECEIPT.json'

$final = [ordered]@{
    schema = 'qps.m08.native_excel_owner_reentry.v1'
    status = 'UNKNOWN'
    source_repo = 'GBOGEB/cryoplant-project'
    source_commit = $ExpectedSourceCommit
    payload_git_blobs = $ExpectedBlobs
    payload_blob_verification = 'UNKNOWN'
    equation_version = 'OFFER_EVAL_EQ_v1'
    input_file = $workbookPath
    input_raw_sha256 = $null
    input_normalized_release_sha256 = $null
    native_receipt_sha256 = $null
    native_status = $null
    native_output_sha256 = $null
    excel_version = $null
    excel_build = $null
    host = $env:COMPUTERNAME
    user = $env:USERNAME
    operator_confirmed_no_repair_dialog = $false
    finalized_utc = $null
    authority_transfer = $false
    formal_credit_delta = 0
}

try {
    foreach ($entry in $ExpectedBlobs.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $entry.Key)) {
            $final.status = 'RED_OWNER_SOURCE_FILE_MISSING'
            $final.failure = $entry.Key
            Write-FinalReceipt $final $finalReceiptPath 10
        }
        $actual = (& git hash-object -- $entry.Key).Trim()
        if ($LASTEXITCODE -ne 0 -or $actual -ne $entry.Value) {
            $final.status = 'RED_OWNER_SOURCE_BLOB_MISMATCH'
            $final.failure = "$($entry.Key):$actual"
            Write-FinalReceipt $final $finalReceiptPath 11
        }
    }
    $final.payload_blob_verification = 'PASS_EXACT'

    python -c "import yaml,openpyxl" 2>$null
    if ($LASTEXITCODE -ne 0) {
        $final.status = 'BLOCKED_PYTHON_DEPENDENCIES_MISSING'
        $final.failure = 'Install pyyaml and openpyxl for the governed workbook generator.'
        Write-FinalReceipt $final $finalReceiptPath 12
    }

    & python scripts/qps_w183_generate_offer_eval_workbook.py --out $workbookPath --receipt $generatorReceipt
    if ($LASTEXITCODE -ne 0) {
        $final.status = 'RED_GOVERNED_WORKBOOK_GENERATION_FAILED'
        Write-FinalReceipt $final $finalReceiptPath 13
    }

    & python scripts/qps_ooxml_normalized_release_identity.py $workbookPath --receipt $identityReceipt | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $final.status = 'RED_NORMALIZED_INPUT_IDENTITY_FAILED'
        Write-FinalReceipt $final $finalReceiptPath 14
    }

    $identityObject = Get-Content -Raw -LiteralPath $identityReceipt | ConvertFrom-Json
    $identity = $identityObject.PSObject.Properties.Value | Select-Object -First 1
    $final.input_raw_sha256 = [string]$identity.raw_sha256
    $final.input_normalized_release_sha256 = [string]$identity.normalized_release_sha256

    if ($final.input_raw_sha256 -ne $ExpectedRawSha) {
        $final.status = 'RED_OWNER_INPUT_RAW_SHA_MISMATCH'
        $final.failure = "$($final.input_raw_sha256) != $ExpectedRawSha"
        Write-FinalReceipt $final $finalReceiptPath 15
    }
    if ($final.input_normalized_release_sha256 -ne $ExpectedNormalizedSha) {
        $final.status = 'RED_OWNER_INPUT_NORMALIZED_SHA_MISMATCH'
        $final.failure = "$($final.input_normalized_release_sha256) != $ExpectedNormalizedSha"
        Write-FinalReceipt $final $finalReceiptPath 16
    }

    Write-Host ''
    Write-Host 'The governed workbook identity is exact. Microsoft Excel will now open visibly.'
    Write-Host 'Do not dismiss or conceal any Excel repair/recovery dialog.'
    Write-Host ''

    & powershell -ExecutionPolicy Bypass -File scripts/qps_m08_native_excel_roundtrip.ps1 -InputXlsx $workbookPath -ReceiptPath $nativeReceiptPath -Visible
    $nativeExit = $LASTEXITCODE

    if (-not (Test-Path -LiteralPath $nativeReceiptPath)) {
        $final.status = 'RED_NATIVE_EXCEL_RECEIPT_MISSING'
        $final.failure = "native runner exit=$nativeExit"
        Write-FinalReceipt $final $finalReceiptPath 17
    }

    $native = Get-Content -Raw -LiteralPath $nativeReceiptPath | ConvertFrom-Json
    $final.native_receipt_sha256 = Get-Sha256 $nativeReceiptPath
    $final.native_status = [string]$native.status
    $final.native_output_sha256 = [string]$native.output_sha256
    $final.excel_version = [string]$native.excel_version
    $final.excel_build = [string]$native.excel_build
    $final.host = [string]$native.host
    $final.user = [string]$native.user

    if ($native.status -ne 'PASS_NATIVE_EXCEL_TECHNICAL_ROUNDTRIP_OPERATOR_DIALOG_CONFIRMATION_REQUIRED') {
        $final.status = [string]$native.status
        $final.failure = 'Native Excel technical transaction did not reach clean operator-confirmation state.'
        Write-FinalReceipt $final $finalReceiptPath 18
    }

    if ($native.open_save_close_reopen -ne $true -or $native.repair_mode_observed -ne $false -or $native.table1_recovery_log_observed -ne $false) {
        $final.status = 'RED_NATIVE_EXCEL_TECHNICAL_GUARD_MISMATCH'
        Write-FinalReceipt $final $finalReceiptPath 19
    }

    Write-Host ''
    $answer = Read-Host 'If NO Excel repair/recovery dialog appeared during either open, type exactly NO_REPAIR'
    if ($answer -cne 'NO_REPAIR') {
        $final.status = 'RED_OPERATOR_CONFIRMATION_WITHHELD'
        Write-FinalReceipt $final $finalReceiptPath 20
    }

    $final.operator_confirmed_no_repair_dialog = $true
    $final.status = 'PASS_OWNER_NATIVE_EXCEL_CLEAN_ROUNDTRIP'
    Write-FinalReceipt $final $finalReceiptPath 0

} catch {
    $final.status = 'RED_OWNER_REENTRY_UNHANDLED_EXCEPTION'
    $final.failure = $_.Exception.Message
    Write-FinalReceipt $final $finalReceiptPath 99
}
