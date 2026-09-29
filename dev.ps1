# Arranca el entorno de desarrollo completo: API, worker y web, cada uno en su ventana.
# Uso: doble clic en dev.cmd, o `.\dev.ps1` desde PowerShell.
# Para pararlo todo, cierra las ventanas (o Ctrl+C en cada una).
#
# Si el .env tiene CLIPASO_WORKER__DISPATCHER=modal, los vídeos los procesa Modal
# y no se abre el worker local.

$root = $PSScriptRoot
$useModal = Select-String -Path (Join-Path $root ".env") -Pattern '^\s*CLIPASO_WORKER__DISPATCHER\s*=\s*modal' -Quiet

$services = @(
    @{ Title = "Clipaso - API"; Dir = $root; Cmd = ".venv\Scripts\clipaso api --reload" }
)
if (-not $useModal) {
    $services += @{ Title = "Clipaso - Worker"; Dir = $root; Cmd = ".venv\Scripts\clipaso worker" }
}
$services += @{ Title = "Clipaso - Web"; Dir = (Join-Path $root "web"); Cmd = "npm run dev" }

foreach ($s in $services) {
    # -NoExit: si algo falla, la ventana se queda abierta para poder leer el error.
    $command = "`$Host.UI.RawUI.WindowTitle = '$($s.Title)'; $($s.Cmd)"
    Start-Process powershell -WorkingDirectory $s.Dir -ArgumentList "-NoExit", "-NoProfile", "-Command", $command
}

if ($useModal) { Write-Host "Worker: Modal (no se abre el worker local)" }
Write-Host "Arrancando... API en http://localhost:8000 y web en http://localhost:3000"
