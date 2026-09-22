param(
    [Parameter(Mandatory=$true)]
    [string]$InputXlsx,

    [string]$OutputXlsx = "",

    [string]$ReceiptPath = "QPS_M08_NATIVE_EXCEL_RECEIPT.json",

    [switch]$Visible,

    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'

function Write-ReceiptAndExit {
    param(
        [System.Collections.IDictionary]$Receipt,
        [int]$ExitCode
    )
    $Receipt.timestamp_utc = (Get-Date).ToUniversalTime().ToString('o')
    $json = $Receipt | ConvertTo-Json -Depth 8
    $json | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
    Write-Output $json
    exit $ExitCode
}

$inputResolved = (Resolve-Path -LiteralPath $InputXlsx).Path
if ([string]::IsNullOrWhiteSpace($OutputXlsx)) {
    $dir = Split-Path -Parent $inputResolved
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($inputResolved)
    $OutputXlsx = Join-Path $dir ($stem + "_NATIVE_EXCEL_ROUNDTRIP.xlsx")
}
$outputFull = [System.IO.Path]::GetFullPath($OutputXlsx)
$receiptFull = [System.IO.Path]::GetFullPath($ReceiptPath)
$receiptDir = Split-Path -Parent $receiptFull
if ($receiptDir -and -not (Test-Path -LiteralPath $receiptDir)) {
    New-Item -ItemType Directory -Force -Path $receiptDir | Out-Null
}

Copy-Item -LiteralPath $inputResolved -Destination $outputFull -Force
$inputSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $inputResolved).Hash.ToLowerInvariant()
$start = Get-Date

$receipt = [ordered]@{
    schema = 'qps.m08.native_excel_roundtrip.v1'
    status = 'UNKNOWN'
    governed_input_path = $inputResolved
    governed_input_sha256 = $inputSha
    output_path = $outputFull
    output_sha256 = $null
    excel_version = $null
    excel_build = $null
    host = $env:COMPUTERNAME
    user = $env:USERNAME
    visible_mode = [bool]$Visible
    operator_confirmed_no_repair_dialog = $false
    repair_mode_observed = $null
    table1_recovery_log_observed = $null
    open_save_close_reopen = $false
    timestamp_utc = $null
    authority_transfer = $false
    formal_credit_delta = 0
}

$excel = $null
$wb = $null
try {
    try {
        $excel = New-Object -ComObject Excel.Application -ErrorAction Stop
    } catch {
        $receipt.status = 'BLOCKED_NATIVE_EXCEL_COM_UNAVAILABLE'
        $receipt.blocker = $_.Exception.Message
        Write-ReceiptAndExit -Receipt $receipt -ExitCode 2
    }

    $receipt.excel_version = [string]$excel.Version
    try { $receipt.excel_build = [string]$excel.Build } catch {}
    $excel.Visible = [bool]$Visible

    # In visible mode alerts remain enabled so the operator can observe any repair dialog.
    # In non-visible mode, the script can prove COM roundtrip mechanics but cannot prove dialog absence.
    $excel.DisplayAlerts = [bool]$Visible

    $wb = $excel.Workbooks.Open($outputFull)
    try {
        $receipt.repair_mode_observed = [bool]$wb.RepairMode
    } catch {
        $receipt.repair_mode_observed = $false
    }

    $wb.Save()
    $wb.Close($true)
    $wb = $null

    $wb = $excel.Workbooks.Open($outputFull)
    try {
        if ([bool]$wb.RepairMode) { $receipt.repair_mode_observed = $true }
    } catch {}

    $wb.Close($false)
    $wb = $null
    $receipt.open_save_close_reopen = $true

    $excel.Quit()
    $excel = $null

    $candidateXml = @()
    foreach ($root in @((Split-Path -Parent $outputFull), $env:TEMP)) {
        if ($root -and (Test-Path -LiteralPath $root)) {
            $candidateXml += Get-ChildItem -LiteralPath $root -Filter '*.xml' -File -ErrorAction SilentlyContinue |
                Where-Object { $_.LastWriteTime -ge $start }
        }
    }

    $recoveryHit = $false
    foreach ($f in $candidateXml) {
        try {
            $m = Select-String -LiteralPath $f.FullName -Pattern 'table1.xml|repairedRecords' -ErrorAction Stop
            if ($m) { $recoveryHit = $true; break }
        } catch {}
    }
    $receipt.table1_recovery_log_observed = $recoveryHit
    $receipt.output_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $outputFull).Hash.ToLowerInvariant()

    if ($receipt.repair_mode_observed -or $receipt.table1_recovery_log_observed) {
        $receipt.status = 'RED_NATIVE_EXCEL_REPAIR_OR_RECOVERY_OBSERVED'
        Write-ReceiptAndExit -Receipt $receipt -ExitCode 4
    }

    if ($Visible -and -not $NonInteractive) {
        Write-Host ''
        $answer = Read-Host 'If NO Excel repair/recovery dialog appeared during either open in THIS transaction, type exactly NO_REPAIR'
        if ($answer -ceq 'NO_REPAIR') {
            $receipt.operator_confirmed_no_repair_dialog = $true
            $receipt.status = 'PASS_NATIVE_EXCEL_CLEAN_ROUNDTRIP'
            Write-ReceiptAndExit -Receipt $receipt -ExitCode 0
        }
        $receipt.status = 'RED_OPERATOR_CONFIRMATION_WITHHELD'
        Write-ReceiptAndExit -Receipt $receipt -ExitCode 5
    }

    $receipt.status = 'PASS_NATIVE_EXCEL_TECHNICAL_ROUNDTRIP_OPERATOR_DIALOG_CONFIRMATION_REQUIRED'
    Write-ReceiptAndExit -Receipt $receipt -ExitCode 3

} finally {
    if ($wb -ne $null) {
        try { $wb.Close($false) } catch {}
    }
    if ($excel -ne $null) {
        try { $excel.Quit() } catch {}
    }
}
