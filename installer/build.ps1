# Kurulum paketini üretir: PyInstaller (tek klasör + taşınabilir zip) ve Inno Setup (tek kurulum dosyası).
# Sürüm magaza_transfer\__init__.py içindeki __version__'dan okunur.
# Kullanım: powershell -ExecutionPolicy Bypass -File installer\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$python = Join-Path $root ".venv\Scripts\python.exe"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }

$version = (Select-String -Path "$root\magaza_transfer\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
if (-not $version) { throw "__version__ okunamadı." }

Push-Location $root
try {
    & $python -m PyInstaller main.py --name MagazaTransfer --windowed --noconfirm --clean `
        --icon "$root\assets\app.ico" `
        --add-data "$root\magaza_transfer\sql;magaza_transfer\sql" `
        --add-data "$root\assets\app.ico;assets" `
        --exclude-module tkinter `
        --distpath "$root\build\dist" --workpath "$root\build\work" --specpath "$root\build"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller başarısız." }
    Copy-Item "$root\KULLANIM.md" "$root\build\dist\MagazaTransfer\" -Force
    Copy-Item "$root\LICENSE" "$root\build\dist\MagazaTransfer\" -Force

    $zip = "$root\installer\Output\MagazaTransfer_Tasinabilir_$version.zip"
    New-Item -ItemType Directory -Force "$root\installer\Output" | Out-Null
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Compress-Archive -Path "$root\build\dist\MagazaTransfer" -DestinationPath $zip

    & $iscc "/DAppVersion=$version" "$root\installer\setup.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup başarısız." }
    & $python "$root\installer\paketle.py"
    if ($LASTEXITCODE -ne 0) { throw "Paketleme başarısız." }
    Write-Host "Hazır: $root\installer\Output\MagazaTransfer_Setup_$version.exe"
    Write-Host "Taşınabilir: $zip"
}
finally {
    Pop-Location
}
