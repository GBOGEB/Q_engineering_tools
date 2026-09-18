param(
  [Parameter(Mandatory=$true)][string]$InputXlsx,
  [Parameter(Mandatory=$true)][string]$ReceiptJson,
  [string]$OutputXlsx = ""
)

$ErrorActionPreference = "Stop"
$start = Get-Date
if (-not $OutputXlsx) {
  $dir = Split-Path -Parent (Resolve-Path $InputXlsx)
  $name = [System.IO.Path]::GetFileNameWithoutExtension($InputXlsx)
  $OutputXlsx = Join-Path $dir ($name + ".native_excel_roundtrip.xlsx")
}

function Get-Sha256([string]$Path) {
  return (Get-FileHash -Path $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$receipt = [ordered]@{
  schema = "qps-m08-native-excel-roundtrip-receipt/1.0"
  mission = "M08_OFFER_EVAL_METHOD"
  gate = "MIP2D_NATIVE_EXCEL_CLEAN_ROUNDTRIP"
  timestamp_start_utc = $start.ToUniversalTime().ToString("o")
  runner = $env:RUNNER_NAME
  runner_os = $env:RUNNER_OS
  machine = $env:COMPUTERNAME
  input_path = (Resolve-Path $InputXlsx).Path
  input_sha256 = Get-Sha256 $InputXlsx
  output_path = $OutputXlsx
  excel_available = $false
  excel_version = $null
  open_save_close_reopen = $false
  repair_dialog_observed = $null
  recovery_log_paths = @()
  table1_xml_recovery_log_observed = $false
  result = "BLOCKED_NATIVE_EXCEL_RUNTIME_UNAVAILABLE"
  authority_transfer = $false
  formal_credit_delta = 0
}

$excel = $null
$wb = $null
$wb2 = $null
try {
  try {
    $excel = New-Object -ComObject Excel.Application
  } catch {
    $receipt.blocker = "Excel.Application COM ProgID unavailable on runner"
    throw
  }

  $receipt.excel_available = $true
  $receipt.excel_version = [string]$excel.Version
  $excel.Visible = $false
  $excel.DisplayAlerts = $true
  $excel.AskToUpdateLinks = $false

  $src = (Resolve-Path $InputXlsx).Path
  Copy-Item -LiteralPath $src -Destination $OutputXlsx -Force

  $wb = $excel.Workbooks.Open($OutputXlsx, 0, $false, 5, "", "", $true, 1, "", $false, $false, 0, $false, $true, 0)
  $wb.Save()
  $wb.Close($true)
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null
  $wb = $null

  $wb2 = $excel.Workbooks.Open($OutputXlsx, 0, $false, 5, "", "", $true, 1, "", $false, $false, 0, $false, $true, 0)
  $sheetCount = $wb2.Worksheets.Count
  $wb2.Close($false)
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb2) | Out-Null
  $wb2 = $null

  $receipt.open_save_close_reopen = $true
  $receipt.worksheet_count_after_reopen = $sheetCount
  $receipt.repair_dialog_observed = $false
  $receipt.output_sha256 = Get-Sha256 $OutputXlsx

  $candidateLogs = @()
  $scanRoots = @($env:TEMP, (Split-Path -Parent $OutputXlsx))
  foreach ($root in $scanRoots | Select-Object -Unique) {
    if (-not (Test-Path $root)) { continue }
    Get-ChildItem -Path $root -File -Recurse -ErrorAction SilentlyContinue |
      Where-Object {
        $_.LastWriteTimeUtc -ge $start.ToUniversalTime().AddSeconds(-5) -and
        ($_.Extension -in @(".xml",".log",".txt"))
      } |
      ForEach-Object {
        try {
          $txt = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction Stop
          if ($txt -match "Repaired Records|table1\.xml|recovery log|Errors were detected") {
            $candidateLogs += $_.FullName
          }
        } catch {}
      }
  }
  $receipt.recovery_log_paths = @($candidateLogs | Sort-Object -Unique)
  $receipt.table1_xml_recovery_log_observed = [bool]($candidateLogs | Where-Object {
    try { (Get-Content -LiteralPath $_ -Raw) -match "table1\.xml" } catch { $false }
  })

  if ($receipt.recovery_log_paths.Count -gt 0) {
    $receipt.result = "FAIL_EXCEL_RECOVERY_LOG_OBSERVED"
  } else {
    $receipt.result = "PASS_NATIVE_EXCEL_SAVE_CLOSE_REOPEN_NO_RECOVERY_LOG"
  }
}
catch {
  if (-not $receipt.blocker) {
    $receipt.blocker = $_.Exception.Message
  }
  if ($receipt.excel_available) {
    $receipt.result = "FAIL_NATIVE_EXCEL_ROUNDTRIP"
  }
}
finally {
  if ($wb2 -ne $null) {
    try { $wb2.Close($false) } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb2) | Out-Null } catch {}
  }
  if ($wb -ne $null) {
    try { $wb.Close($false) } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null } catch {}
  }
  if ($excel -ne $null) {
    try { $excel.Quit() } catch {}
    try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null } catch {}
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
  $receipt.timestamp_end_utc = (Get-Date).ToUniversalTime().ToString("o")
  $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReceiptJson -Encoding UTF8
  Get-Content -LiteralPath $ReceiptJson
}

if ($receipt.result -ne "PASS_NATIVE_EXCEL_SAVE_CLOSE_REOPEN_NO_RECOVERY_LOG") {
  exit 42
}
