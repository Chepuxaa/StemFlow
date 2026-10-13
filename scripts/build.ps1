$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install requirements first.' }
Push-Location $projectRoot
try {
    & $pythonPath -m pip install --no-cache-dir -r requirements/build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    & $pythonPath scripts/check_repository.py
    if ($LASTEXITCODE -ne 0) { throw 'Repository validation failed.' }
    & $pythonPath -m PyInstaller --clean --noconfirm packaging/stemflow.spec
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    & $pythonPath scripts/prepare_release.py
    if ($LASTEXITCODE -ne 0) { throw 'Release preparation failed.' }
    Write-Host 'Build created in dist\StemFlow.exe. Release testing is still required.'
} finally { Pop-Location }
