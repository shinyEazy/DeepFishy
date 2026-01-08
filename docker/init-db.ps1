# Initialize database with Alembic migrations (PowerShell version)

Write-Host "Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow

# Wait for PostgreSQL
$ready = $false
$attempts = 0
$maxAttempts = 30

while (-not $ready -and $attempts -lt $maxAttempts) {
    $attempts++
    try {
        docker exec postgres pg_isready -U postgres -d deepfishy 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
        } else {
            Write-Host "Waiting for database... (attempt $attempts/$maxAttempts)" -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    } catch {
        Write-Host "Waiting for database... (attempt $attempts/$maxAttempts)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "ERROR: PostgreSQL failed to start after $maxAttempts attempts" -ForegroundColor Red
    exit 1
}

Write-Host "PostgreSQL is ready!" -ForegroundColor Green
Write-Host "Running Alembic migrations..." -ForegroundColor Yellow

# Run migrations
docker exec server alembic upgrade head

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database initialized successfully!" -ForegroundColor Green
} else {
    Write-Host "ERROR: Migration failed!" -ForegroundColor Red
    exit 1
}

