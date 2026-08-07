[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$TestName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$testNames = @($TestName | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$managedEnvironmentVariables = @(
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "MPLBACKEND"
)
$originalEnvironment = @{}

foreach ($name in $managedEnvironmentVariables) {
    $item = Get-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
    $originalEnvironment[$name] = [pscustomobject]@{
        Exists = $null -ne $item
        Value = if ($null -eq $item) { $null } else { $item.Value }
    }
}

$locationPushed = $false
$exitCode = 1

try {
    $env:OMP_NUM_THREADS = "1"
    $env:OPENBLAS_NUM_THREADS = "1"
    $env:MKL_NUM_THREADS = "1"
    $env:NUMEXPR_NUM_THREADS = "1"
    $env:MPLBACKEND = "Agg"

    $pythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($null -eq $pythonLauncher) {
        throw "Python launcher (py.exe) was not found. Install Python 3.12 with the Windows launcher."
    }

    Push-Location $repositoryRoot
    $locationPushed = $true

    $pythonPathOutput = & $pythonLauncher.Source -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version; print(sys.executable)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.12 was not found through py.exe."
    }

    $pythonPath = [string]($pythonPathOutput | Select-Object -Last 1)
    if ([string]::IsNullOrWhiteSpace($pythonPath)) {
        throw "Python 3.12 executable path could not be resolved."
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
        throw "Could not set the unittest process priority to BelowNormal: $($_.Exception.Message)"
    }

    $process.WaitForExit()
    $exitCode = $process.ExitCode
}
catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    $exitCode = 1
}
finally {
    if ($locationPushed) {
        Pop-Location
    }

    foreach ($name in $managedEnvironmentVariables) {
        $original = $originalEnvironment[$name]
        if ($original.Exists) {
            Set-Item -LiteralPath "Env:$name" -Value $original.Value
        }
        else {
            Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        }
    }
}

exit $exitCode
