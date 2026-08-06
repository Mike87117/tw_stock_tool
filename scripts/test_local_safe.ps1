[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$TestName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$testNames = @($TestName | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })

$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"
$env:MPLBACKEND = "Agg"

$pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($null -eq $pythonLauncher) {
    Write-Error "Python launcher (py.exe) was not found. Install Python 3.12 with the Windows launcher."
    exit 1
}

Push-Location $repositoryRoot
try {
    $pythonPathOutput = & $pythonLauncher.Source -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python 3.12 was not found through py.exe."
        exit 1
    }

    $pythonPath = [string]($pythonPathOutput | Select-Object -Last 1)
    if ([string]::IsNullOrWhiteSpace($pythonPath)) {
        Write-Error "Python 3.12 executable path could not be resolved."
        exit 1
    }
    $pythonPath = $pythonPath.Trim()

    if ($testNames.Count -eq 0) {
        $unittestArguments = @("discover", "-s", "tests")
    }
    else {
        $unittestArguments = $testNames
    }

    $process = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList (@("-m", "unittest") + $unittestArguments) `
        -NoNewWindow `
        -PassThru

    try {
        $process.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
    }
    catch {
        try {
            $process.Kill()
            $process.WaitForExit()
        }
        catch {
            # The original priority error is the actionable failure.
        }
        Write-Error "Could not set the unittest process priority to BelowNormal: $($_.Exception.Message)"
        exit 1
    }

    $process.WaitForExit()
    exit $process.ExitCode
}
finally {
    Pop-Location
}
