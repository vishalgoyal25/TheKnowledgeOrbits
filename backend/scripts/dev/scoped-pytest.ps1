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

    WHY IT IS FAST, AND WHERE THE FLOOR IS
    Scoping attacks the variable cost: 775 tests -> only the engines touched.
    That is the whole win, measured at 476s -> ~31s for a telemetry-only run.

    Measured on 2026-09-03, telemetry only (22 tests):

      full suite, -n auto                 476.5s
      scoped, -n 2, first run (db built)   31.8s
      scoped, -n 2, second run (db reused) 39.9s
      scoped, -n 0, db reused              30.8s

    Two things that data says, both against my first assumption:

    1. --reuse-db does NOT remove the floor. I expected database construction
       to dominate; it does not. The flag is kept because it is theoretically
       right and should help on larger scoped runs, but do not expect it to
       show up in a 22-test run.

    2. xdist HURTS at this size. -n 2 was ~9s SLOWER than -n 0, because each
       worker is a separate process that imports Django and all 15 engines
       before running anything. Hence -n 0 for scoped runs; the full-suite
       paths still use -n auto, where parallelism does pay.

    The remaining ~30s is Python import time: Django app loading plus
    langchain, pgvector, sentence-transformers and deepeval. No hook flag
    fixes that; it would take reducing what gets imported at startup.

    --reuse-db is only safe while the schema is unchanged, so a push containing
    anything under migrations/ switches to --create-db. Without that check a
    schema change would be tested against a stale database and pass for the
    wrong reason.

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
    'backend/engines/shared/'
)

# Paths under backend/ that can affect NO test, so they neither scope the run
# nor widen it. backend/scripts/dev/ holds standalone diagnostic and tooling
# scripts -- the secret scanner, the telemetry report, this file. Nothing
# imports them, so changing one cannot break a Django test.
#
# Both halves of this are needed. Simply removing the folder from $GlobalPaths
# is not enough: the fail-safe below treats any backend file that is neither
# global nor inside an engine as "unrecognised" and widens to the full suite.
# Without an explicit ignore list, editing this very script would still cost
# eight minutes.
$IgnorePaths = @(
    'backend/scripts/dev/'
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
        if ($f.StartsWith('backend/')) {
            $ignored = $false
            foreach ($i in $IgnorePaths) {
                if ($f.StartsWith($i)) { $ignored = $true }
            }
            if (-not $ignored) { $backendFiles += $f }
        }
    }

    # Nothing testable under backend/: a frontend-only, docs-only, or
    # tooling-only push. Django tests cannot be affected, so run none. jest
    # still runs via its own hook.
    if ($backendFiles.Count -eq 0) {
        Write-Host ""
        Write-Host "  pytest skipped: this push changes no testable backend files." -ForegroundColor Cyan
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

    # -n 0 (no xdist) deliberately: measured 9s FASTER than -n 2 at this size,
    # because each worker re-imports Django and every engine. See the header.
    Run-Pytest -Targets $targets -Workers '0' -DbFlag $dbFlag `
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
