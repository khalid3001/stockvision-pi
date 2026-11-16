# Windows equivalent of the Makefile.  Usage:  .\tasks.ps1 <target> [source]
# Targets: install, init-db, train, infer, dashboard, capture, report, demo, demo-stub, test
# If PowerShell blocks the script, run once:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
param(
    [Parameter(Position = 0)][string]$Target = "help",
    [Parameter(Position = 1)][string]$Src = "data/samples"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$Py = ".venv\Scripts\python.exe"

switch ($Target) {
    "install" {
        # Use Python 3.11 if it's on this machine (via the py launcher), otherwise
        # whatever `python`/`py` resolves to (3.10-3.13 all work fine for this project).
        $usedPy311 = $false
        if (Get-Command py -ErrorAction SilentlyContinue) {
            $has311 = (py -0p 2>$null) -join "`n" -match "3\.11"
            if ($has311) {
                py -3.11 -m venv .venv
                $usedPy311 = $true
            }
        }
        if (-not $usedPy311) {
            if (Get-Command py -ErrorAction SilentlyContinue) { py -m venv .venv } else { python -m venv .venv }
        }
        & $Py -m pip install --upgrade pip
        & $Py -m pip install -r requirements.txt
        & $Py scripts/init_db.py
        & $Py --version
    }
    "init-db"   { & $Py scripts/init_db.py }
    "train"     { & $Py scripts/open_colab.py }
    "infer"     { & $Py scripts/infer.py $Src }
    "dashboard" { & $Py -m streamlit run app/dashboard.py }
    "capture"   { & $Py scripts/capture.py }   # photo from the webcam (stands in for the Pi camera), then verify
    "report"    { & $Py scripts/make_report.py }
    "demo"      { & $Py scripts/demo.py }
    "demo-stub" { & $Py scripts/demo.py --stub }
    "test"      { & $Py -m pytest -q }
    default     { Write-Host "Usage: .\tasks.ps1 <install|init-db|train|infer|dashboard|capture|report|demo|demo-stub|test> [source]" }
}
