# NiriZan dependency graph generator (Windows PowerShell 5.1 and PowerShell 7+).
# Regenerates docs/dependency-graph.md locally.
# Never commits, pushes, or stages anything.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$RepoRoot  = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$Generator = Join-Path $RepoRoot ".github/scripts/gen_dependency_graph.py"
$OutputRel = "docs/dependency-graph.md"

if (-not (Test-Path -LiteralPath $Generator -PathType Leaf)) {
    throw "Dependency graph generator not found: $Generator"
}

# Returns $true when the given interpreter is Python 3.11 or newer.
# Runs with errors relaxed because a non-working interpreter (for example
# the Microsoft Store "python" stub) must not abort the search.
function Test-PythonVersion {
    param(
        [Parameter(Mandatory)] [string] $Executable,
        [string[]] $Prefix = @()
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $Executable @Prefix -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

# Pick the first interpreter that is actually Python 3.11 or newer (CI uses 3.11).
# "py -3" selects the newest installed Python 3 via the Python launcher.
$Candidates = @(
    @{ Name = "py";      Prefix = @("-3") },
    @{ Name = "python3"; Prefix = @() },
    @{ Name = "python";  Prefix = @() }
)

$PythonExe = $null
$PythonPrefix = @()
foreach ($Candidate in $Candidates) {
    $Command = Get-Command $Candidate.Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $Command) { continue }
    if (Test-PythonVersion -Executable $Command.Source -Prefix $Candidate.Prefix) {
        $PythonExe = $Command.Source
        $PythonPrefix = $Candidate.Prefix
        break
    }
}

if (-not $PythonExe) {
    throw "Python 3.11 or newer is required (CI uses 3.11). Install it with: winget install Python.Python.3.11"
}

& $PythonExe @PythonPrefix $Generator
if ($LASTEXITCODE -ne 0) {
    throw "Dependency graph generation failed with exit code $LASTEXITCODE."
}

# Read-only summary. Skipped when git is missing or this is not a checkout.
$Git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($Git) {
    $ErrorActionPreference = "Continue"
    $Changes = & $Git.Source -C $RepoRoot status --short -- $OutputRel 2>$null
    $GitOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = "Stop"

    if ($GitOk) {
        Write-Host ""
        if ($Changes) {
            Write-Host $Changes
            Write-Host "Review with: git diff -- $OutputRel"
        }
        else {
            Write-Host "No changes: $OutputRel is already up to date."
        }
    }
}
