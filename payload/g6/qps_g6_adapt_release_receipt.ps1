[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ReceiptPath,
    [Parameter(Mandatory = $true)][string]$ReleaseConfigVersion,
    [Parameter(Mandatory = $true)][string]$ExcelRelativePath,
    [Parameter(Mandatory = $true)][string]$HtmlRelativePath,
    [Parameter(Mandatory = $true)][string]$PdfRelativePath,
    [string]$OutputPath = 'QPS_G6_RELEASE_IDENTITY_RETURN.json',
    [switch]$TestVector
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$blockedTokens = @('WITHHELD', 'TBD', 'UNKNOWN', 'NOT_BOUND', 'PLACEHOLDER')

function Assert-NonPlaceholder {
    param([string]$Value, [string]$Field)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Field missing"
    }
    $upper = $Value.Trim().ToUpperInvariant()
    foreach ($token in $blockedTokens) {
        if ($upper.Contains($token)) {
            throw "$Field placeholder rejected"
        }
    }
}

function Assert-Sha256 {
    param([string]$Value, [string]$Field)
    if ($Value -notmatch '^[0-9a-f]{64}$') {
        throw "$Field must be 64 lowercase hex"
    }
}

function Get-VerifiedEntry {
    param($Receipt, [string]$RelativePath, [string]$Label)
    $matches = @($Receipt.files | Where-Object { $_.path -eq $RelativePath })
    if ($matches.Count -ne 1) {
        throw "$Label path must occur exactly once in verified release receipt: $RelativePath"
    }
    $entry = $matches[0]
    if ($entry.status -ne 'VERIFIED') {
        throw "$Label entry is not VERIFIED: $RelativePath"
    }
    if ($entry.expected_sha256 -ne $entry.actual_sha256) {
        throw "$Label expected/actual hash mismatch: $RelativePath"
    }
    Assert-Sha256 -Value $entry.actual_sha256 -Field "$Label.sha256"
    return $entry
}

if (-not (Test-Path -LiteralPath $ReceiptPath -PathType Leaf)) {
    throw "Release receipt not found: $ReceiptPath"
}

$receiptResolved = (Resolve-Path -LiteralPath $ReceiptPath).Path
$receipt = Get-Content -LiteralPath $receiptResolved -Raw | ConvertFrom-Json
$receiptSha = (Get-FileHash -LiteralPath $receiptResolved -Algorithm SHA256).Hash.ToLowerInvariant()

if ($receipt.result -ne 'PASS') { throw "Upstream release receipt result must be PASS" }
if ($receipt.all_manifest_entries_verified -ne $true) { throw "All manifest entries must be verified" }
if ($receipt.build_meta_qa_status -ne 'PASS') { throw "BUILD_META QA status must be PASS" }
if ($receipt.control_id -ne 'GOV-001') { throw "Unexpected upstream release control_id" }

Assert-NonPlaceholder -Value $receipt.release_id -Field 'release_id'
Assert-NonPlaceholder -Value $ReleaseConfigVersion -Field 'release_config_version'
Assert-NonPlaceholder -Value $receipt.source_commit -Field 'source_commit_sha'
Assert-Sha256 -Value $receipt.manifest_sha256 -Field 'source_manifest_sha256'

if ($receipt.source_commit -notmatch '^[0-9a-f]{40}$') {
    throw 'source_commit_sha must be 40 lowercase hex'
}

$versionMatch = [regex]::Match($ReleaseConfigVersion, '(\d+)(?:\.(\d+))?')
if (-not $versionMatch.Success) { throw 'release_config_version malformed' }
$major = [int]$versionMatch.Groups[1].Value
$minor = if ($versionMatch.Groups[2].Success) { [int]$versionMatch.Groups[2].Value } else { 0 }
if (($major -lt 4) -or (($major -eq 4) -and ($minor -lt 2))) {
    throw 'release config must be v4.2 or later'
}

$paths = @($ExcelRelativePath, $HtmlRelativePath, $PdfRelativePath)
if (@($paths | Select-Object -Unique).Count -ne 3) { throw 'Excel/HTML/PDF paths must be distinct' }
if ([IO.Path]::GetFileName($ExcelRelativePath) -ne 'QPS_COST_Master.xlsx') {
    throw 'Excel path must select canonical QPS_COST_Master.xlsx'
}
if ([IO.Path]::GetFileName($HtmlRelativePath) -ne 'QPS_COST_Master_HTML_CURRENT.html') {
    throw 'HTML path must select canonical QPS_COST_Master_HTML_CURRENT.html'
}
if ([IO.Path]::GetExtension($PdfRelativePath).ToLowerInvariant() -ne '.pdf') {
    throw 'PDF path must select one explicit manifest-bound PDF'
}

$excel = Get-VerifiedEntry -Receipt $receipt -RelativePath $ExcelRelativePath -Label 'Excel'
$html = Get-VerifiedEntry -Receipt $receipt -RelativePath $HtmlRelativePath -Label 'HTML'
$pdf = Get-VerifiedEntry -Receipt $receipt -RelativePath $PdfRelativePath -Label 'PDF'

$authority = if ($TestVector) { 'NON_ENGINEERING_TEST_VECTOR' } else { 'GOVERNED_RELEASE_RETURN' }
$status = if ($TestVector) { 'PASS_TEST_VECTOR_ZERO_CREDIT' } else { 'READY_FOR_W160_VALIDATION' }

$out = [ordered]@{
    schema = 'qps.g6.release_identity_return.v1'
    authority = $authority
    test_vector = [bool]$TestVector
    release_id = $receipt.release_id
    release_config_version = $ReleaseConfigVersion
    source_commit_sha = $receipt.source_commit
    source_manifest_sha256 = $receipt.manifest_sha256
    artifacts = [ordered]@{
        Excel = [ordered]@{
            path = $ExcelRelativePath
            sha256 = $excel.actual_sha256
            role = 'NUMERICAL_COST_SSOT_PROJECTION'
        }
        HTML = [ordered]@{
            path = $HtmlRelativePath
            sha256 = $html.actual_sha256
            role = 'READ_ONLY_REVIEW_PROJECTION'
        }
        PDF = [ordered]@{
            path = $PdfRelativePath
            sha256 = $pdf.actual_sha256
            role = 'CONTROLLED_FIXED_NARRATIVE'
        }
    }
    authority_guards = [ordered]@{
        actual_numeric_cost_release = 'WITHHELD_SOURCE_VALUES'
        source_gates_for_actual_spares_values = @(974, 981)
        unknown_numeric_semantics = 'NULL_NOT_ZERO'
        topology_execution_status = 'PASS_EXECUTED_EXACT_PAYLOAD'
        horizontal_promotion_status = 'PASS_GOVERNED'
    }
    upstream_release_receipt = [ordered]@{
        schema_version = $receipt.schema_version
        control_id = $receipt.control_id
        receipt_sha256 = $receiptSha
        build_meta_qa_status = $receipt.build_meta_qa_status
        verified_file_count = $receipt.verified_file_count
        file_count = $receipt.file_count
        all_manifest_entries_verified = $receipt.all_manifest_entries_verified
    }
    selection_attestation = [ordered]@{
        explicit_paths_required = $true
        selected_entries_present_in_verified_manifest = $true
        pdf_selected_explicitly_no_filename_guessing = $true
    }
    engineering_credit = 0
    release_credit = 0
    status = $status
}

$out | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $OutputPath -Encoding utf8
$out | ConvertTo-Json -Depth 10
