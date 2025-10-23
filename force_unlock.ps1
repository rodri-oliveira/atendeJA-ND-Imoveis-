# Forca desbloqueio do SQLite removendo journal e matando processos
Write-Host "Forcando desbloqueio do dev.db..." -ForegroundColor Yellow

# 1. Matar processos Python/uvicorn
$procs = Get-Process -ErrorAction SilentlyContinue | Where-Object {
    ($_.ProcessName -match "python") -or ($_.ProcessName -match "uvicorn")
}
if ($procs) {
    Write-Host "Matando $($procs.Count) processo(s)..." -ForegroundColor Red
    $procs | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# 2. Remover arquivos de lock/journal
$files = @("dev.db-journal", "dev.db-shm", "dev.db-wal")
foreach ($f in $files) {
    if (Test-Path $f) {
        Write-Host "Removendo $f..." -ForegroundColor Cyan
        Remove-Item $f -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 2
Write-Host "Desbloqueio concluido. Pronto para backfill." -ForegroundColor Green
