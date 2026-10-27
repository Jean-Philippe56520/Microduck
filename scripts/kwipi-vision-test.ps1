# Kwipi F5 v2: operator-approved image to local Qwen3.5 9B only.
# Windows PC only. No camera, cloud, SQLite or robot motor access.
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$Port = 11435,
    [string]$Image = "",
    [ValidateSet("simple", "strict", "balanced")][string]$Mode = "simple",
    [switch]$VisionCheck,
    [switch]$ComparePrompts,
    [switch]$RolePreview
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $env:USERPROFILE ".venv-qwen9b\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $python = Join-Path $repo ".venv-qwen9b\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    Write-Host "Python isole introuvable. Reutiliser l'environnement .venv-qwen9b deja installe."
    exit 2
}

function Get-LocalOllamaTags {
    param([int]$LocalPort)
    try {
        return Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/api/tags" -f $LocalPort) -TimeoutSec 3 -ErrorAction Stop
    } catch {
        return $null
    }
}

function Stop-OnlyStartedOllama {
    param([System.Diagnostics.Process]$ServerProcess)
    if ($null -ne $ServerProcess) {
        try {
            if (-not $ServerProcess.HasExited) {
                Stop-Process -Id $ServerProcess.Id -Force -ErrorAction Stop
                Write-Host "Serveur Ollama temporaire arrete apres cet essai."
            }
        } catch {
            Write-Host "Fermeture automatique du serveur temporaire impossible (verifier les processus Ollama)."
        }
    }
}

Write-Host "Kwipi - evaluation visuelle PC, sans mouvement ni memorisation"
Write-Host "Mode : $Mode | Modele : qwen3.5:9b | Ollama local : 127.0.0.1:$Port"
Write-Host "L'image est preparee localement puis envoyee uniquement a Ollama sur 127.0.0.1."

if ($VisionCheck -and $Image) {
    Write-Host "Autotest synthetique : ne pas fournir d'image privee."
    exit 2
}
if (($VisionCheck -and $ComparePrompts) -or ($VisionCheck -and $RolePreview) -or ($ComparePrompts -and $RolePreview)) {
    Write-Host "Choisir un seul mode d'essai a la fois."
    exit 2
}
if ($VisionCheck) {
    Write-Host "Autotest visuel : deux carres rouge/bleu generes en memoire, aucune photo personnelle."
    Write-Host "Le double-clic sur VERIFIER_VISION_KWIPI.cmd autorise uniquement ces deux images synthetiques."
} else {
    if ($RolePreview) {
        Write-Host "Simulation du role reel de conseil de Kwipi, aucun robot connecte."
        Write-Host "Une image approuvee, une reponse courte NON verifiee, pas de memoire."
    }
    if ($ComparePrompts) {
        Write-Host "Comparaison : deux analyses locales de la MEME photo, consignes simple puis equilibree."
        Write-Host "Aucune photo ni reponse brute ne sera envoyee a GitHub ou sauvegardee."
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
    if ($ComparePrompts) {
        Write-Host "Votre approbation couvre EXACTEMENT deux appels successifs au meme Ollama local."
    }
    $consent = Read-Host "Image autorisee et inspectee pour cet essai ? Tapez OUI"
    if ($consent -cne "OUI") {
        Write-Host "Aucun appel Qwen : consentement non confirme."
        exit 1
    }
 }

# Start Ollama only AFTER photo approval OR explicit synthetic vision test.
# Never kill an existing server. This process is temporary and uses localhost only.
$serverWeStarted = $null
try {
    $tags = Get-LocalOllamaTags -LocalPort $Port
    if ($null -eq $tags) {
        $ollama = Get-Command -Name ollama.exe -CommandType Application -ErrorAction SilentlyContinue
        if ($null -eq $ollama) {
            Write-Host "Ollama introuvable dans le PATH Windows. Verifier son installation."
            exit 2
        }
        # Child process inherits these LOCAL process variables only; no setx, registry or service changes.
        $env:OLLAMA_HOST = "127.0.0.1:$Port"
        $env:OLLAMA_VULKAN = "1"
        $env:OLLAMA_IGPU_ENABLE = "1"
        Write-Host "Serveur Ollama arrete : lancement local automatique sur le port $Port."
        Write-Host "Acceleration Vulkan demandee, mais utilisation GPU a verifier separement."
        try {
            $serverWeStarted = Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden -PassThru -ErrorAction Stop
        } catch {
            Write-Host "Impossible de demarrer Ollama localement. Aucun fichier image envoye."
            exit 2
        }
        # Bounded retry for a cold Windows startup, never a background monitor.
        for ($i = 0; $i -lt 24; $i++) {
            Start-Sleep -Milliseconds 500
            $tags = Get-LocalOllamaTags -LocalPort $Port
            if ($null -ne $tags) { break }
            if ($serverWeStarted.HasExited) { break }
        }
    }
    if ($null -eq $tags) {
        Write-Host "Serveur Ollama local inaccessible sur le port $Port, meme apres tentative de lancement."
        Write-Host "Aucun modele telecharge ou donnees privees transferees par le lanceur."
        exit 2
    }
    $found = @($tags.models | Where-Object { $_.name -eq "qwen3.5:9b" })
    if ($found.Count -eq 0) {
        Write-Host "Le modele qwen3.5:9b est absent de l'inventaire du serveur local."
        Write-Host "Le lanceur ne telecharge aucun modele automatiquement."
        exit 2
    }

    Push-Location $repo
    try {
        if ($VisionCheck) {
            & $python -m microduck_companion.qwen9b_vision_check `
                --ollama-port $Port --timeout 120
        } elseif ($RolePreview) {
            & $python -m microduck_companion.qwen9b_role_preview `
                --image $Image --ollama-port $Port --timeout 120 `
                --authorize-image --reviewed-no-private-subjects
        } elseif ($ComparePrompts) {
            & $python -m microduck_companion.qwen9b_prompt_comparison `
                --image $Image --ollama-port $Port --timeout 120 `
                --authorize-image --reviewed-no-private-subjects
        } else {
            & $python -m microduck_companion.qwen9b_advisor_v2 `
                --image $Image --ollama-port $Port --mode $Mode --timeout 180 `
                --authorize-image --reviewed-no-private-subjects
        }
        $status = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($status -ne 0) {
        Write-Host "Test non concluant / resultat refuse : aucun effet robot ou memoire."
        exit $status
    }
    if ($VisionCheck) {
        Write-Host "Deux couleurs simples distinguees, vision d'objets reels NON verifiee."
    } elseif ($RolePreview) {
        Write-Host "Conseil Qwen de role candidat teste sur PC, AUCUNE connaissance verifiee ni action."
    } elseif ($ComparePrompts) {
        Write-Host "Deux consignes comparees, categories NON verifiees; aucun apprentissage."
    } else {
        Write-Host "Reponse structuree acceptee, mais connaissance NON verifiee."
    }
    exit 0
} finally {
    Stop-OnlyStartedOllama -ServerProcess $serverWeStarted
}