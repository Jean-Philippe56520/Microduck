# Kwipi F5 v2: one operator-approved image, one localhost Qwen3.5 9B call.
# This is a manual PC-only visual probe. Never connects to robotd or SQLite.
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 11435,
    [string]$Image = "",
    [ValidateSet("simple", "strict")][string]$Mode = "simple"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:USERPROFILE ".venv-qwen9b\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = Join-Path $repo ".venv-qwen9b\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Host "Python isole introuvable. Installer Python 3.12 et l'environnement .venv-qwen9b avant l'essai."
    exit 2
}

Write-Host "Kwipi - evaluation visuelle PC, sans mouvement ni memorisation"
Write-Host "Mode : $Mode | Modele : qwen3.5:9b | Ollama local : 127.0.0.1:$Port"
Write-Host "L'image est preparee localement puis envoyee uniquement a Ollama sur 127.0.0.1."
try {
    $tags = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/api/tags" -f $Port) -TimeoutSec 5
    $found = @($tags.models | Where-Object { $_.name -eq "qwen3.5:9b" })
    if ($found.Count -eq 0) {
        Write-Host "Le modele qwen3.5:9b n'est pas disponible sur ce serveur."
        Write-Host "Verifier ollama list avec OLLAMA_HOST=127.0.0.1:$Port."
        exit 2
    }
} catch {
    Write-Host "Serveur Ollama local inaccessible sur le port $Port."
    Write-Host "Verifier que le serveur GPU est actif sur 127.0.0.1:$Port."
    exit 2
}

if (-not $Image) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $picker = New-Object System.Windows.Forms.OpenFileDialog
        $picker.Title = "Choisir UNE image autorisee pour Kwipi"
        $picker.Filter = "Images|*.jpg;*.jpeg;*.png;*.webp;*.bmp|Tous les fichiers|*.*"
        $picker.Multiselect = $false
        if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            Write-Host "Essai annule : aucune image selectionnee."
            exit 1
        }
        $Image = $picker.FileName
    } catch {
        Write-Host "Selection graphique indisponible."
        $Image = Read-Host "Chemin complet de l'image (sans archive de photos privees)"
        $Image = $Image.Trim('"')
    }
}
if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) {
    Write-Host "Fichier image introuvable ou illisible."
    exit 2
}
if ((Get-Item -LiteralPath $Image).Length -gt 2000000) {
    Write-Host "Image trop volumineuse pour le pilote (maximum 2 Mo)."
    exit 2
}

Write-Host "Avant l'envoi local : verifier visuellement l'image et ses droits."
Write-Host "Aucun visage, ecran, texte prive, adresse, document ou contenu personnel."
Write-Host "Ne pas utiliser sans revue explicite les photos privees Cat-A2b."
$consent = Read-Host "Image autorisee et inspectee pour cette unique analyse ? Tapez OUI"
if ($consent -cne "OUI") {
    Write-Host "Aucun appel Qwen : consentement non confirme."
    exit 1
}

Push-Location $repo
try {
    & $python -m microduck_companion.qwen9b_advisor_v2 `
        --image $Image --ollama-port $Port --mode $Mode --timeout 180 `
        --authorize-image --reviewed-no-private-subjects
    $status = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($status -ne 0) {
    Write-Host "Resultat non accepte : aucun effet robot ou memoire."
    exit $status
}
Write-Host "Reponse structuree acceptee, mais connaissance NON verifiee."
exit 0