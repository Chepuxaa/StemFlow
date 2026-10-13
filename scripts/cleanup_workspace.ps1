$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..')).TrimEnd('\')
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'stemflow.py'))) {
    throw 'Expected StemFlow source workspace.'
}
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in 'python.exe','pythonw.exe' -and $_.CommandLine -and $_.CommandLine.Contains($projectRoot)
}
if ($running) { throw 'Close StemFlow and its workers before cleaning the workspace.' }
$targets = @('.cache','__pycache__','build') | ForEach-Object {
    [IO.Path]::GetFullPath((Join-Path $projectRoot $_))
}
$environmentRoot = Join-Path $projectRoot '.venv'
Get-ChildItem -LiteralPath $projectRoot -Directory -Recurse -Force -Filter '__pycache__' | ForEach-Object {
    $candidate = [IO.Path]::GetFullPath($_.FullName)
    if (-not $candidate.StartsWith($environmentRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        $targets += $candidate
    }
}
foreach ($target in $targets) {
    if (-not $target.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Outside workspace: $target"
    }
}
foreach ($target in $targets) {
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force -Recurse }
}
Write-Host 'Workspace caches cleaned. Environment, model weights, input tracks and dist preserved.'
