<#
  End-to-end smoke test: starts the server (stub providers), starts the client, simulates a
  push-to-talk press with a harmless key (F13), and checks that a pilot transcript, an ATC
  reply and audio playback come back.

  Usage:  .\scripts\smoke-test.ps1            # real SimConnect if MSFS is running + SDK found
          .\scripts\smoke-test.ps1 -Mock      # mock sim
#>
param([switch]$Mock)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
if (-not $env:MSFS2024_SDK -and (Test-Path "C:\MSFS 2024 SDK")) { $env:MSFS2024_SDK = "C:\MSFS 2024 SDK\" }

Write-Host "Building client..."
dotnet build "$root\client\MsfsAtc.Client" -nologo -v q | Out-Null
if ($LASTEXITCODE -ne 0) { throw "client build failed" }

Add-Type -Namespace Win -Name Keys -MemberDefinition @'
[DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
'@
$F13 = 0x7C

$env:ATC_STT_PROVIDER = "stub"; $env:ATC_LLM_PROVIDER = "stub"; $env:ATC_TTS_PROVIDER = "stub"
$srvOut = "$env:TEMP\atc_smoke_srv.log"; $cliOut = "$env:TEMP\atc_smoke_cli.log"
$srv = Start-Process "$root\server\.venv\Scripts\python.exe" -ArgumentList "-m", "atc_server.main" `
    -WorkingDirectory "$root\server" -RedirectStandardError $srvOut -RedirectStandardOutput "$env:TEMP\atc_smoke_srv.out" -WindowStyle Hidden -PassThru
Start-Sleep 3

$binDir = "$root\client\MsfsAtc.Client\bin\Debug\net8.0-windows"
$cliArgs = @("--Audio:PttKey=0x7C")
if ($Mock) { $cliArgs += "--Sim:Mode=Mock" }
$cli = Start-Process "$binDir\MsfsAtc.Client.exe" -ArgumentList $cliArgs -WorkingDirectory $binDir `
    -RedirectStandardOutput $cliOut -RedirectStandardError "$env:TEMP\atc_smoke_cli.err" -WindowStyle Hidden -PassThru
try {
    Start-Sleep 5
    Write-Host "Simulating push-to-talk (1.5 s)..."
    [Win.Keys]::keybd_event($F13, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 1500
    [Win.Keys]::keybd_event($F13, 0, 2, [UIntPtr]::Zero)
    Start-Sleep 4
}
finally {
    Stop-Process -Id $cli.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
}

$c = Get-Content $cliOut -Raw
$checks = [ordered]@{
    "sim data read"        = $c -match "SIM:"
    "server connected"     = $c -match "Session \w+ ready"
    "PTT transmitted"      = $c -match "TX COM"
    "pilot transcript"     = $c -match "PILOT:"
    "ATC reply"            = $c -match "ATC \["
}
$checks.GetEnumerator() | ForEach-Object { "{0,-18} {1}" -f $_.Key, $(if ($_.Value) { "OK" } else { "FAIL" }) }
Write-Host "`n--- client log ---"; Write-Host $c
if ($checks.Values -contains $false) { Write-Host "--- server log ---"; Get-Content $srvOut | Select-Object -Last 15; exit 1 }
