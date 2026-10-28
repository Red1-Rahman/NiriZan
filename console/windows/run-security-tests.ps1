$ErrorActionPreference = 'Continue'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Push-Location $repoRoot
try {
    $failed = $false

    Write-Host '=== Python security tests ==='
    & python -m pytest tests/security/ -v --tb=short
    if ($LASTEXITCODE -ne 0) { $failed = $true }

    Write-Host '=== Node workflow and findings checks ==='
    & npm ci --prefix tests/security/js
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    else {
        & node tests/security/js/check-workflow-pins.cjs
        if ($LASTEXITCODE -ne 0) { $failed = $true }
        & node tests/security/js/validate-findings-schema.cjs tests/security/js/known-findings.json
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    }

    if ($failed) { exit 1 }
    Write-Host 'All security suites passed.'
}
finally {
    Pop-Location
}
