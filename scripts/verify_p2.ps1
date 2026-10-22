param(
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$Python = 'python',
    [switch]$Docker
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
function Invoke-Checked {
    param([string[]]$Arguments)
    if ($Docker) { & docker @Arguments } else { & $Python @Arguments }
    if ($LASTEXITCODE -ne 0) { throw "La verificación terminó con código $LASTEXITCODE." }
}
if ($Docker) {
    $env:DATOS = (Resolve-Path -LiteralPath $DataDir).Path.Replace('\', '/')
    # Usar la imagen preparada según docs/DOCKER.md. No compilar el backend.
    Invoke-Checked @('compose','config','--quiet')
    Invoke-Checked @('compose','run','--rm','--no-build','--entrypoint','python','evaluar','-m','unittest','discover','-s','tests','-v')
    Invoke-Checked @('compose','run','--rm','--no-build','evaluar')
    Invoke-Checked @('compose','run','--rm','--no-build','baseline','baseline','--repetir')
    foreach ($config in 'configs/baseline_dead_ball_disabled.json','configs/baseline_dead_ball.json') {
        Invoke-Checked @('compose','run','--rm','--no-build','modelo','modelo','--config',$config,'--repetir')
    }
    Invoke-Checked @('compose','run','--rm','--no-build','--entrypoint','python','evaluar','scripts/summarize_p2.py','--outputs','/salidas','--out',('/salidas/p2-comparison-' + [guid]::NewGuid().ToString('N') + '.json'))
} else {
    $data = (Resolve-Path -LiteralPath $DataDir).Path
    $env:MTAH_DATA_DIR = $data
    Invoke-Checked @('-m','unittest','discover','-s','tests','-v')
    Invoke-Checked @('docker/pipeline.py','evaluar')
    Invoke-Checked @('docker/pipeline.py','baseline','--repetir')
    foreach ($config in 'configs/baseline_dead_ball_disabled.json','configs/baseline_dead_ball.json') {
        Invoke-Checked @('docker/pipeline.py','modelo','--config',$config,'--data-dir',$data,'--repetir')
    }
    Invoke-Checked @('scripts/summarize_p2.py','--out',('salidas/p2-comparison-' + [guid]::NewGuid().ToString('N') + '.json'))
}
