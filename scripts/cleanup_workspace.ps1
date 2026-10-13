$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
$dataRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'StemFlow')).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'stemflow.py'))) {
    throw 'Expected StemFlow source workspace.'
}
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in 'StemFlow.exe','StemFlow-worker.exe' -or
    ($_.Name -in 'python.exe','pythonw.exe' -and $_.CommandLine -and $_.CommandLine.Contains($projectRoot))
}
if ($running) { throw 'Close StemFlow and its workers before cleaning the workspace.' }
$previous = [IO.Path]::GetFullPath((Join-Path $dataRoot 'previous-results'))
if (-not $previous.StartsWith($dataRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid previous-results path.' }
if (Test-Path -LiteralPath $previous) {
    $musicRoot = [IO.Path]::GetFullPath([Environment]::GetFolderPath('MyMusic')).TrimEnd('\')
    $exportRoot = [IO.Path]::GetFullPath((Join-Path $musicRoot 'StemFlow exports')).TrimEnd('\')
    if (-not $exportRoot.StartsWith($musicRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid export destination.' }
    Get-ChildItem -LiteralPath $previous -Directory | Where-Object { $_.Name.StartsWith('gotlibgotlibgotlib - aromat-') } | ForEach-Object {
        $source = [IO.Path]::GetFullPath($_.FullName)
        $destination = [IO.Path]::GetFullPath((Join-Path $exportRoot $_.Name))
        if (-not $source.StartsWith($previous + '\', [StringComparison]::OrdinalIgnoreCase) -or -not $destination.StartsWith($exportRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid export paths.' }
        if (Test-Path -LiteralPath $destination) { throw "Export already exists: $destination" }
        New-Item -ItemType Directory -Path $exportRoot -Force | Out-Null
        Move-Item -LiteralPath $source -Destination $destination
        Write-Host "Preserved export: $destination"
    }
}
$targets = @('.cache','__pycache__','build','build-log.txt','dist\StemFlow-windows-x64-alpha.zip') | ForEach-Object {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $_))
}
$inputRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'input'))
if ((Test-Path -LiteralPath $inputRoot) -and -not (Get-ChildItem -LiteralPath $inputRoot -File -Recurse -Force | Select-Object -First 1)) { $targets += $inputRoot }
$targets += @('development-archive','exe-check','repository-check','previous-results','reports','StemFlow-source.zip') | ForEach-Object {
    [IO.Path]::GetFullPath((Join-Path $dataRoot $_))
}
$workspaceModels = [IO.Path]::GetFullPath((Join-Path $projectRoot 'models'))
if (Test-Path -LiteralPath $workspaceModels) {
    $checkpoint = Join-Path $dataRoot 'models\melband-4stem-syh-v2\ver2.ckpt'
    $manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'config\model.json') -Raw | ConvertFrom-Json
    if (-not (Test-Path -LiteralPath $checkpoint)) { throw 'Central model missing; workspace model preserved.' }
    if ((Get-Item -LiteralPath $checkpoint).Length -ne $manifest.weights_bytes -or (Get-FileHash -LiteralPath $checkpoint -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.weights_sha256) { throw 'Central model invalid; workspace model preserved.' }
    $targets += $workspaceModels
}
$environmentRoot = Join-Path $projectRoot '.venv'
Get-ChildItem -LiteralPath $projectRoot -Directory -Recurse -Force -Filter '__pycache__' | ForEach-Object {
    $candidate = [IO.Path]::GetFullPath($_.FullName)
    if (-not $candidate.StartsWith($environmentRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        $targets += $candidate
    }
}
foreach ($target in $targets) {
    if (-not ($target.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $target.StartsWith($dataRoot + '\', [StringComparison]::OrdinalIgnoreCase))) {
        throw "Outside workspace: $target"
    }
}
foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force -Recurse }
}
Write-Host 'Cleaned. Source, .venv, current release, central model, runtime and settings preserved.'
