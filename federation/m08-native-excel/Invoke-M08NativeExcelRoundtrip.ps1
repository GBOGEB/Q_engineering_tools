param(
  [Parameter(Mandatory=$true)][string]$InputXlsx,
  [Parameter(Mandatory=$true)][string]$OutDir,
  [Parameter(Mandatory=$true)][string]$AttemptId
)

$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Get-Sha256([string]$Path) {
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
}

function Get-NewRepairLogs([datetime]$StartUtc, [string]$WorkbookName) {
  $roots = @($env:TEMP, (Join-Path $env:LOCALAPPDATA "Microsoft\Office\UnsavedFiles")) | Where-Object { $_ -and (Test-Path $_) }
  $hits = @()
  foreach ($root in $roots) {
    Get-ChildItem -LiteralPath $root -File -Recurse -ErrorAction SilentlyContinue |
      Where-Object { $_.LastWriteTimeUtc -ge $StartUtc -and $_.Extension -in @(".xml",".txt",".html",".htm",".log") } |
      ForEach-Object {
        $text = ""
        try { $text = Get-Content -LiteralPath $_.FullName -Raw -ErrorAction Stop } catch {}
        if ($text -match "table1\.xml|Repaired Records|Errors were detected|Removed Records|Repair Result" -or $text -match [regex]::Escape($WorkbookName)) {
          $hits += [pscustomobject]@{ path=$_.FullName; modified_utc=$_.LastWriteTimeUtc.ToString("o") }
        }
      }
  }
  return @($hits)
}

$startUtc = [datetime]::UtcNow
$inputResolved = (Resolve-Path -LiteralPath $InputXlsx).Path
$inputHash = Get-Sha256 $inputResolved
$workPath = Join-Path (Resolve-Path -LiteralPath $OutDir).Path ("native_roundtrip_" + $AttemptId + ".xlsx")
Copy-Item -LiteralPath $inputResolved -Destination $workPath -Force

$receipt = [ordered]@{
  schema = "qps-m08-native-excel-roundtrip-attempt/1.0"
  attempt_id = $AttemptId
  started_utc = $startUtc.ToString("o")
  runner_os = $env:RUNNER_OS
  runner_name = $env:RUNNER_NAME
  runner_arch = $env:RUNNER_ARCH
  computer_name = $env:COMPUTERNAME
  input_xlsx = (Split-Path -Leaf $inputResolved)
  governed_input_sha256 = $inputHash
  excel_com_available = $false
  excel_version = $null
  excel_build = $null
  open_save_close_reopen = $false
  no_modal_block_observed = $false
  no_table1_xml_part_after_save = $false
  repair_log_count = $null
  repair_logs = @()
  output_sha256 = $null
  status = "BLOCKED_NATIVE_EXCEL_COM_UNAVAILABLE"
  error = $null
  authority_transfer = $false
  formal_credit_delta = 0
}

$excel = $null
$wb = $null
try {
  try {
    $excel = New-Object -ComObject Excel.Application
  } catch {
    $receipt.error = $_.Exception.Message
    throw
  }

  $receipt.excel_com_available = $true
  $receipt.excel_version = [string]$excel.Version
  try { $receipt.excel_build = [string]$excel.Build } catch {}
  $excel.Visible = $false
  $excel.DisplayAlerts = $false
  try { $excel.AskToUpdateLinks = $false } catch {}

  $wb = $excel.Workbooks.Open($workPath, 0, $false)
  $wb.Save()
  $wb.Close($false)
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb)
  $wb = $null

  $wb = $excel.Workbooks.Open($workPath, 0, $false)
  $wb.Close($false)
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb)
  $wb = $null

  $receipt.open_save_close_reopen = $true
  $receipt.no_modal_block_observed = $true

  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [System.IO.Compression.ZipFile]::OpenRead($workPath)
  try {
    $table1 = @($zip.Entries | Where-Object { $_.FullName -ieq "xl/tables/table1.xml" })
    $receipt.no_table1_xml_part_after_save = ($table1.Count -eq 0)
  } finally {
    $zip.Dispose()
  }

  $logs = Get-NewRepairLogs -StartUtc $startUtc -WorkbookName (Split-Path -Leaf $workPath)
  $receipt.repair_logs = @($logs)
  $receipt.repair_log_count = @($logs).Count
  $receipt.output_sha256 = Get-Sha256 $workPath

  if ($receipt.open_save_close_reopen -and $receipt.no_modal_block_observed -and $receipt.no_table1_xml_part_after_save -and $receipt.repair_log_count -eq 0) {
    $receipt.status = "PASS_NATIVE_MICROSOFT_EXCEL_CLEAN_ROUNDTRIP"
  } else {
    $receipt.status = "RED_NATIVE_EXCEL_REPAIR_OR_INTEGRITY_SIGNAL"
  }
} catch {
  if (-not $receipt.error) { $receipt.error = $_.Exception.Message }
} finally {
  if ($wb -ne $null) {
    try { $wb.Close($false) } catch {}
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) } catch {}
  }
  if ($excel -ne $null) {
    try { $excel.Quit() } catch {}
    try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) } catch {}
  }
  [gc]::Collect()
  [gc]::WaitForPendingFinalizers()
}

$receipt["finished_utc"] = [datetime]::UtcNow.ToString("o")
$receiptPath = Join-Path $OutDir ("native_excel_receipt_" + $AttemptId + ".json")
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Get-Content -LiteralPath $receiptPath -Raw
