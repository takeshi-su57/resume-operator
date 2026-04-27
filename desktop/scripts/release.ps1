# Phase 6 (#89) one-shot release build for Windows.
#
#   1. uv sync (Python deps including PyInstaller)
#   2. python pyinstaller/build.py        # PyInstaller → smoke test → copy into binaries/
#   3. pnpm install                       # JS deps
#   4. pnpm tauri:build                   # produces .msi
#
# Output:
#   desktop/src-tauri/target/release/bundle/msi/resume-operator_<ver>_x64_en-US.msi

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path "$PSScriptRoot/../.."
Set-Location $repoRoot

Write-Host "==> uv sync"
uv sync

Write-Host "==> PyInstaller bundle"
uv run python pyinstaller/build.py

Write-Host "==> pnpm install (desktop)"
Set-Location "$repoRoot/desktop"
pnpm install

Write-Host "==> tauri build"
pnpm tauri:build

Write-Host ""
Write-Host "Done. MSI at:"
Get-ChildItem -Recurse "src-tauri/target/release/bundle/msi" -Filter "*.msi" |
  ForEach-Object { Write-Host "  $($_.FullName)" }
