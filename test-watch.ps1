# Install pytest-watch dynamically inside docker on the fly
Write-Host "Installing pytest-watch inside the Docker container..." -ForegroundColor Cyan
docker exec TheKnowledgeOrbits_backend pip install pytest-watch

Write-Host "Starting watch mode for Backend tests..." -ForegroundColor Green
Write-Host "It will re-run automatically every time you hit Save in a Python file!" -ForegroundColor Yellow
docker exec -it TheKnowledgeOrbits_backend ptw engines/
