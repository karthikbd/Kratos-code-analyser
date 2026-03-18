# Start Kratos backend + frontend dev servers

$Root = $PSScriptRoot

Write-Host "Starting Kratos backend (uvicorn) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", `
    "cd '$Root'; pipenv run server" `
    -WindowStyle Normal

Write-Host "Starting Kratos frontend (Vite) ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList `
    "-NoExit", "-Command", `
    "cd '$Root\frontend'; npm run dev" `
    -WindowStyle Normal

Write-Host "Both servers are starting in separate windows." -ForegroundColor Green
Write-Host "  Backend : http://localhost:8001" -ForegroundColor Yellow
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Yellow
