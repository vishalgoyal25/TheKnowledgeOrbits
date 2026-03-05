Write-Host "Running Backend Checks (via Docker)..." -ForegroundColor Cyan
docker exec TheKnowledgeOrbits_backend mypy engines/
docker exec TheKnowledgeOrbits_backend pytest engines/ -q

Write-Host "Running Frontend Checks..." -ForegroundColor Cyan
Set-Location frontend
npm run type-check
npm test
Set-Location ..

Write-Host "Deep Check Complete!" -ForegroundColor Green
