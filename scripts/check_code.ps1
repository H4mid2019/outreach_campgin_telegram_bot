# ============================================================
# check_code.ps1 - Code Quality & Security Check Script
# Python Telegram Bot Project
# ============================================================
# Checks:
#   1. Import issues (missing packages, unused imports)
#   2. Linting problems (flake8, pylint)
#   3. Security issues (hardcoded tokens/secrets via bandit + regex)
# ============================================================

param(
    [string]$PythonPath = "python",
    [string]$ProjectRoot = "",
    [switch]$FailFast,
    [switch]$SecurityOnly
)

# Resolve project root: default to parent of the scripts/ folder
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

# ── Colour helpers ──────────────────────────────────────────
function Write-Header {
    param($msg)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Pass { param($msg) Write-Host "[PASS] $msg" -ForegroundColor Green  }
function Write-Fail { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red    }
function Write-Warn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor White  }

# ── Counters ────────────────────────────────────────────────
$script:totalChecks  = 0
$script:passedChecks = 0
$script:failedChecks = 0
$script:exitCode     = 0

function Invoke-Check {
    param(
        [string]      $Name,
        [scriptblock] $Block
    )
    $script:totalChecks++
    Write-Info "Running: $Name"
    $result = & $Block
    if ($result -eq $true) {
        $script:passedChecks++
        Write-Pass "$Name"
    } else {
        $script:failedChecks++
        $script:exitCode = 1
        Write-Fail "$Name"
        if ($FailFast) {
            Write-Host ""
            Write-Host "[ABORT] FailFast enabled - stopping on first failure." -ForegroundColor Red
            exit 1
        }
    }
}

# ── Tool installer helper ────────────────────────────────────
function Install-IfMissing {
    param([string]$Package, [string]$ImportName = "")
    if (-not $ImportName) { $ImportName = $Package }
    $null = & $PythonPath -c "import $ImportName" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "$Package not found - installing..."
        & $PythonPath -m pip install $Package --quiet
    }
}

# ============================================================
# SETUP
# ============================================================
Write-Header "Code Quality & Security Checker"
Write-Info "Project root : $ProjectRoot"
$pyVer = & $PythonPath --version 2>&1
Write-Info "Python       : $pyVer"
Write-Host ""

Set-Location $ProjectRoot

# Ensure required tools are available
if (-not $SecurityOnly) {
    Install-IfMissing "pyflakes"
    Install-IfMissing "flake8"
    Install-IfMissing "pylint"
    Install-IfMissing "isort"
}
Install-IfMissing "bandit"

# Collect all .py files (excluding venv / __pycache__)
$pyFiles = Get-ChildItem -Path $ProjectRoot -Recurse -Filter "*.py" |
    Where-Object { $_.FullName -notmatch '(\.venv|venv|__pycache__|\.git)' } |
    Select-Object -ExpandProperty FullName

if ($pyFiles.Count -eq 0) {
    Write-Warn "No Python files found in $ProjectRoot"
    exit 0
}

Write-Info "Found $($pyFiles.Count) Python file(s) to analyse."

if (-not $SecurityOnly) {

# ============================================================
# 1. IMPORT CHECKS
# ============================================================
Write-Header "1 - Import Checks"

# 1a - pyflakes: undefined names, unused imports, star imports
Invoke-Check "pyflakes - undefined / unused imports" {
    $out = & $PythonPath -m pyflakes $pyFiles 2>&1
    if ($out) {
        Write-Host ($out | Out-String) -ForegroundColor Yellow
        return $false
    }
    return $true
}

# 1b - isort: import ordering
Invoke-Check "isort - import order" {
    $out = & $PythonPath -m isort --check-only --diff $pyFiles 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ($out | Out-String) -ForegroundColor Yellow
        return $false
    }
    return $true
}

# 1c - verify every package in requirements.txt is importable
Invoke-Check "requirements.txt - all packages importable" {
    $reqFile = Join-Path $ProjectRoot "requirements.txt"
    if (-not (Test-Path $reqFile)) {
        Write-Warn "requirements.txt not found - skipping"
        return $true
    }

    $failed = @()
    Get-Content $reqFile | ForEach-Object {
        $pkg = ($_ -split '[=<>!;]')[0].Trim()
        if ($pkg -and -not $pkg.StartsWith('#')) {
            $importName = switch ($pkg.ToLower()) {
                'python-dotenv'  { 'dotenv'           }
                'pillow'         { 'PIL'               }
                'scikit-learn'   { 'sklearn'           }
                'beautifulsoup4' { 'bs4'               }
                'sqlalchemy'     { 'sqlalchemy'        }
                'ddgs'           { 'duckduckgo_search' }
                'tavily-python'  { 'tavily'            }
                default          { $pkg -replace '-','_' }
            }
            $null = & $PythonPath -c "import $importName" 2>&1
            if ($LASTEXITCODE -ne 0) {
                $failed += "$pkg (import $importName)"
            }
        }
    }

    if ($failed.Count -gt 0) {
        Write-Host "  Not importable: $($failed -join ', ')" -ForegroundColor Yellow
        return $false
    }
    return $true
}

# ============================================================
# 2. LINTING CHECKS
# ============================================================
Write-Header "2 - Linting Checks"

# 2a - flake8: PEP-8 style + common errors
Invoke-Check "flake8 - PEP-8 / syntax errors" {
    $out = & $PythonPath -m flake8 `
        --max-line-length=120 `
        --extend-ignore=E501,W503 `
        --statistics `
        $pyFiles 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ($out | Out-String) -ForegroundColor Yellow
        return $false
    }
    return $true
}

# 2b - pylint: deeper static analysis (score threshold >= 7.0)
Invoke-Check "pylint - static analysis (score >= 7.0)" {
    $out = & $PythonPath -m pylint `
        --disable=C0114,C0115,C0116,R0903,W0611 `
        --max-line-length=120 `
        --score=yes `
        $pyFiles 2>&1

    $scoreLine = $out | Where-Object { $_ -match 'Your code has been rated' }
    if ($scoreLine) {
        $score = [double]($scoreLine -replace '.*rated at ([0-9\.\-]+).*','$1')
        Write-Info "  pylint score: $score / 10"
        if ($score -lt 7.0) {
            Write-Host ($out | Where-Object { $_ -match '^[A-Z]:' } | Out-String) -ForegroundColor Yellow
            return $false
        }
    } else {
        Write-Host ($out | Out-String) -ForegroundColor Yellow
        return $false
    }
    return $true
}

}  # end if (-not $SecurityOnly)

# ============================================================
# 3. SECURITY CHECKS
# ============================================================
Write-Header "3 - Security Checks"

# 3a - bandit: common Python security issues
Invoke-Check "bandit - security vulnerabilities" {
    $out = & $PythonPath -m bandit `
        -r $ProjectRoot `
        --exclude .venv,venv,__pycache__,.git `
        --severity-level low `
        --confidence-level low `
        -f txt 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host ($out | Out-String) -ForegroundColor Yellow
        return $false
    }
    return $true
}

# 3b - Regex scan for hardcoded secrets / tokens
Invoke-Check "Hardcoded secrets / tokens scan" {
    $secretPatterns = @(
        '\b\d{8,12}:[A-Za-z0-9_-]{35}\b',
        '(?i)(api_key|apikey|api_secret|secret_key|access_token|auth_token|bot_token)\s*=\s*["''][A-Za-z0-9_\-\.]{10,}["'']',
        '(?i)AKIA[0-9A-Z]{16}',
        '(?i)(password|passwd|pwd)\s*=\s*["''][^"'']{6,}["'']',
        'sk-[A-Za-z0-9]{20,}',
        '(?i)Bearer\s+[A-Za-z0-9\-_\.]{20,}'
    )

    $found = @()
    foreach ($file in $pyFiles) {
        $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
        if (-not $content) { continue }
        foreach ($pattern in $secretPatterns) {
            if ($content -match $pattern) {
                $found += "  $file  ->  matched pattern: $pattern"
            }
        }
    }

    $envExample = Join-Path $ProjectRoot ".env.example"
    if (Test-Path $envExample) {
        $envContent = Get-Content $envExample -Raw
        if ($envContent -match '=\s*[A-Za-z0-9_\-]{20,}') {
            Write-Warn "  .env.example may contain real secret values - review it."
        }
    }

    if ($found.Count -gt 0) {
        Write-Host "  Potential hardcoded secrets found:" -ForegroundColor Red
        $found | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        return $false
    }
    return $true
}

# 3c - Ensure .env is in .gitignore
Invoke-Check ".env listed in .gitignore" {
    $gitignore = Join-Path $ProjectRoot ".gitignore"
    if (-not (Test-Path $gitignore)) {
        Write-Warn ".gitignore not found"
        return $false
    }
    $content = Get-Content $gitignore -Raw
    if ($content -match '(?m)^\.env\s*$') {
        return $true
    }
    Write-Host "  .env is NOT in .gitignore - secrets could be committed!" -ForegroundColor Red
    return $false
}

# 3d - Ensure no .env file is tracked by git
Invoke-Check ".env not tracked by git" {
    $null = & git ls-files --error-unmatch .env 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  .env IS tracked by git - run: git rm --cached .env" -ForegroundColor Red
        return $false
    }
    return $true
}

# ============================================================
# SUMMARY
# ============================================================
Write-Header "Summary"
Write-Host "  Total checks : $($script:totalChecks)"  -ForegroundColor White
Write-Host "  Passed       : $($script:passedChecks)" -ForegroundColor Green

$failColor = if ($script:failedChecks -gt 0) { 'Red' } else { 'Green' }
Write-Host "  Failed       : $($script:failedChecks)" -ForegroundColor $failColor
Write-Host ""

if ($script:exitCode -eq 0) {
    Write-Host "All checks passed!" -ForegroundColor Green
} else {
    Write-Host "Some checks failed. Please review the output above." -ForegroundColor Red
}

exit $script:exitCode
