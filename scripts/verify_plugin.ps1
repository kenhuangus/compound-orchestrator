param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Push-Location $Root
try {
    & $Python -m unittest discover -s tests -p "test_*.py"
    & $Python scripts/compound_orchestrator.py self-test --root .
}
finally {
    Pop-Location
}
