# Deployment script for VAEP Football Analyzer to Hugging Face Spaces

$spaceName = "vaep-football-analyzer"
$hfUsername = "nirmitktripathii"

Write-Host "Preparing deployment for $spaceName..." -ForegroundColor Cyan

# Initialize git if not already
if (-not (Test-Path .git)) {
    git init
    git lfs install
}

# Track large .h5 files with LFS
git lfs track "spadl/*.h5"
git add .gitattributes

# Add files
git add .
git commit -m "Initial commit for VAEP Football Analyzer"

Write-Host "Deployment folder is ready." -ForegroundColor Green
Write-Host "To deploy to Hugging Face:" -ForegroundColor Yellow
Write-Host "1. Create a new Space on Hugging Face (Streamlit SDK) named: $spaceName"
Write-Host "2. Run the following commands in this directory:"
Write-Host "   git remote add hf https://huggingface.co/spaces/$hfUsername/$spaceName"
Write-Host "   git push -f hf main"
