<#
    scoped-pytest.ps1

    Runs pytest against ONLY the engines a push actually touches, so `git push`
    costs seconds instead of eight minutes.

    Invoked from the pre-push hook in .pre-commit-config.yaml. pre-commit passes
    the files being pushed as arguments; it already solves "what is in this
    push" correctly for new branches, multi-commit pushes and force pushes,
    which is fiddly to derive by hand from git.

    LOCAL ONLY. GitHub Actions does not run pre-commit -- ci.yml calls pytest
    directly and still runs the complete suite across 3 shards. Nothing here
    can weaken CI.

    THE SAFETY RULE
    Ambiguity always widens the run, never narrows it. Anything that could
    affect engines other than the ones changed (core/, conftest.py,
    requirements/, pytest.ini, engines/shared/) forces the FULL suite. So does
    any failure to parse the input. A scoping bug must never produce a green
    push that tested nothing -- that is worse than no gate, because it looks
    like it passed.

    WHY IT IS FAST
    Two separate costs, two separate fixes:

      variable cost   running 775 tests            -> scope to changed engines
      fixed cost      one test database per xdist  -> --reuse-db
                      worker, each replaying
                      ~60 migrations

    Scoping alone leaves the fixed cost. A telemetry-only run took 37s for 22
    tests, nearly all of it database construction. --reuse-db removes that
    floor. Worker count is also lowered for scoped runs: spinning up 12 workers
    to run 20 tests costs more setup than parallelism returns.

    --reuse-db is only safe while the schema is unchanged, so a push containing
    anything under migrations/ switches to --create-db. Without that check a
    schema change would be tested against a stale database and pass for the
    wrong reason.

    ASCII ONLY. Windows PowerShell 5.1 reads .ps1 as ANSI unless there is a
    BOM, so non-ASCII characters here can corrupt parsing. Do not add em
    dashes, arrows or emoji to this file.
#>

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$BackendDir = Join-Path $RepoRoot 'backend'

# Paths under backend/ that can affect EVERY engine.
$GlobalPaths = @(
    'backend/core/',
    'backend/conftest.py',
    'backend/pytest.ini',
    'backend/pyproject.toml',
    'backend/manage.py',
    'backend/requirements/',
    'backend/scripts/',
    'backend/engines/shared/'
)

function Run-Pytest {
    param(
        [string[]] $Targets,
        [string]   $Workers,
        [string]   $DbFlag,
        [string]   $Reason
    )

    Write-Host ""
    Write-Host "  pytest scope: $Reason" -ForegroundColor Cyan
    Write-Host "  (CI always runs the full suite in 3 shards)" -ForegroundColor DarkGray
    Write-Host ""

    $pytestArgs = @('-m', 'pytest')
    $pytestArgs += $Targets
    $pytestArgs += @('-q', '--tb=short', '-p', 'no:cacheprovider', $DbFlag, '-n', $Workers)

    Push-Location $BackendDir
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & python $pytestArgs
    $code = $LASTEXITCODE
    Pop-Location

    # Load-bearing: without propagating pytest's exit code the hook reports
    # success and a failing push goes through.
    exit $code
}

try {
    $changed = @()
    foreach ($a in $args) {
        if ($a) { $changed += ($a -replace '\\', '/') }
    }

    $backendFiles = @()
    foreach ($f in $changed) {
        if ($f.StartsWith('backend/')) { $backendFiles += $f }
    }

    # Nothing under backend/: a frontend-only or docs-only push. Django tests
    # cannot be affected, so run none. jest still runs via its own hook.
    if ($backendFiles.Count -eq 0) {
        Write-Host ""
        Write-Host "  pytest skipped: this push changes no backend files." -ForegroundColor Cyan
        Write-Host ""
        exit 0
    }

    # A schema change invalidates any reused test database.
    $dbFlag = '--reuse-db'
    foreach ($f in $backendFiles) {
        if ($f -like '*/migrations/*') { $dbFlag = '--create-db' }
    }

    # Anything global forces the full suite.
    $globalHit = $null
    foreach ($f in $backendFiles) {
        foreach ($g in $GlobalPaths) {
            if ($f.StartsWith($g)) { $globalHit = $f }
        }
    }

    if ($globalHit) {
        Run-Pytest -Targets @('engines') -Workers 'auto' -DbFlag $dbFlag `
            -Reason "FULL suite ($globalHit affects every engine)"
    }

    # Everything else must live under backend/engines/<name>/
    $engines = @()
    $unaccounted = 0
    foreach ($f in $backendFiles) {
        if ($f.StartsWith('backend/engines/')) {
            $parts = $f.Split('/')
            if ($parts.Length -ge 3 -and $parts[2]) {
                if ($engines -notcontains $parts[2]) { $engines += $parts[2] }
            }
        }
        else {
            $unaccounted = $unaccounted + 1
        }
    }

    # A backend file that is neither global nor inside an engine is something
    # this script does not understand. Widen rather than guess.
    if ($unaccounted -gt 0 -or $engines.Count -eq 0) {
        Run-Pytest -Targets @('engines') -Workers 'auto' -DbFlag $dbFlag `
            -Reason 'FULL suite (unrecognised backend paths in this push)'
    }

    $targets = @()
    foreach ($e in $engines) { $targets += "engines/$e" }

    Run-Pytest -Targets $targets -Workers '2' -DbFlag $dbFlag `
        -Reason ($engines -join ', ')
}
catch {
    # The scoping logic itself failed. Run everything: never let a bug here
    # turn into a push that silently tested nothing.
    Write-Host ""
    Write-Host "  Scoping failed, running FULL suite." -ForegroundColor Yellow
    Write-Host "  Reason: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host ""

    Push-Location $BackendDir
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & python -m pytest engines/ -q --tb=short -p no:cacheprovider -n auto
    $code = $LASTEXITCODE
    Pop-Location
    exit $code
}
