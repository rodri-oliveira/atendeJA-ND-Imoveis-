# Força fechamento de processos que podem estar travando o dev.db
$processes = Get-Process | Where-Object {
    ($_.ProcessName -match "python") -or 
    ($_.ProcessName -match "uvicorn") -or
    ($_.Path -and $_.Path -match "atendeJa")
}

if ($processes) {
    Write-Host "Encontrados processos que podem estar usando o banco:"
    $processes | Format-Table Id, ProcessName, Path -AutoSize
    
    Write-Host "`nMatando processos..." -ForegroundColor Yellow
    $processes | Stop-Process -Force
    Write-Host "✅ Processos encerrados" -ForegroundColor Green
} else {
    Write-Host "Nenhum processo Python/uvicorn encontrado" -ForegroundColor Cyan
}

# Aguardar liberação de locks
Start-Sleep -Seconds 2
Write-Host "`nPronto para executar o backfill" -ForegroundColor Green
