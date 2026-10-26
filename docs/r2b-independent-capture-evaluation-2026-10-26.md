# R2-B — reconnaissance sur prises indépendantes : banc ouvert et prudent

**26 octobre 2026 — implémentation de protocole sur hôte, non une reconnaissance d'objet livrée.** Ce lot suit [R1.5](r15-retrospective-reuse-audit-2026-10-26.md), [R2-A](r2a-single-memory-selection-2026-10-26.md) et le [protocole « réutiliser avant de créer »](development-reuse-protocol.md). Aucun pilote constructeur, schéma SQLite ou modèle embarqué n'est créé.

## 1. Sources, droits et niveau de preuve

La source scientifique de référence pour les vraies orientations est [COIL-20 — Columbia Object Image Library](https://www.cs.columbia.edu/CAVE/software/softlib/coil-20.php), 20 objets physiques, 72 vues de plateau tournant par objet, recadrées sur fond uniformisé. Les prises correspondent au **même objet matériel** sous plusieurs angles, mais proviennent d'une séance contrôlée. Elles **ne prouvent pas** la reconnaissance dans une pièce, en éclairage changeant, ou avec des mouvements de caméra. Ce corpus est destiné à la **recherche non commerciale** selon les catalogues le distribuant ; la page historique officielle ne fournit pas de SHA-256 vérifié publiquement. Le programme refuse donc tout lancement COIL sans **autorisation d'étude non commerciale vérifiée localement** et SHA-256 attendu explicitement fourni. La correspondance de ce SHA avec l'origine universitaire est à vérifier indépendamment, et non simplement à recalculer depuis le même fichier téléchargé. Aucun téléchargement automatique, extraction permanente ou média COIL committé.

Option préférable en présence de conditions d'usage plus larges : des vues prises ou réunies avec les droits nécessaires, ou un **sous-ensemble licencié explicitement**. Par exemple, le [jeu Amazon Berkeley Objects (ABO)](https://registry.opendata.aws/amazon-berkeley-objects/) annonce des séquences réelles multi-vues et la licence **CC BY 4.0** depuis 2023 ; les photos précises, groupes d'objets, empreintes et attributions ne sont **pas sélectionnés ni vérifiés dans ce lot**. L'outil accepte un dossier local de PNG et un manifeste anonymisé ; aucune conversion ou collecte depuis un compte cloud n'est fournie.

La partie sonore utilise des **prises WAV indépendantes** de la même source de bruit sous contrôle local, et des sources différentes pour les négatifs. Les identités, sessions et droits sont **déclarés par le manifeste**, non authentifiés par un certificat physique. Aucun nouveau corpus audio public satisfaisant l'indépendance et les droits n'a été exécuté ici : **aucun résultat audio réel n'est annoncé**.

## 1 bis. Sous-ensemble public ABO en CI (véritables images multi-vues)

Le dataset [Amazon Berkeley Objects](https://amazon-berkeley-objects.s3.amazonaws.com/index.html) fournit des **séquences de produits réellement photographiés** en rotation. Son éditeur affiche la licence **CC BY 4.0** (anciennement CC BY-NC, mise à jour 2023), et demande de citer **Amazon.com** ainsi que **Guillaumin et al.**. Des catalogues secondaires reproduisent encore l'ancienne licence : **l'attribution et la licence officielle actuelle font foi pour ce banc**, sans garantir les droits d'éventuelles images externes hors dataset.

La fonction optionnelle `run_public_abo` réutilise le scoreur et les extraits M1-A/B2, et introduit uniquement un lecteur borné du fichier CSV compressé **officiel** `spins/metadata/spins.csv.gz` et des JPEG sur `amazon-berkeley-objects.s3.us-east-1.amazonaws.com`. L'URL est constante, les redirections vers d'autres hôtes sont refusées, chaque image possède un SHA-256 calculé en mémoire et aucune image n'est déposée comme artefact GitHub. Le manifeste public a **12 séquences d'objets**, choisies selon les **12 premières séquences complètes** dans le CSV, avec 6 vues distinctes par séquence (72 images réelles). L'empreinte combinée des contenus et l'empreinte de la sélection sont fournies dans le résultat pour vérifier la reproductibilité ; aucune liste de noms de produits n'est nécessaire à la comparaison.

- En validation : **5 séquences inscrites** + **1 séquence inconnue**.
- En test final : **4 séquences inscrites** + **2 séquences inconnues**.
- Références angulaires 0 et 36 ; requêtes 9, 18, 45 et 54. Cela mesure **un rappel inter-vues de la même séquence**, pas une capacité à identifier un produit à partir de **sessions indépendantes**, ni à distinguer avec certitude deux exemplaires physiques du même produit.
- Le seuil est calculé seulement avec les négatifs validation, en refusant les scores égaux à la plus forte similarité négative. Il peut donner zéro rappel pour certains modèles. Le test conserve ce seuil sans l'ajuster.
- Modèles : baseline 64 octets vs distribution de 1 000 classes ImageNet MobileNetV2, poids **SHA-256 contrôlé**. Les sorties de classification ImageNet ne constituent **pas** un embedding d'instance. Aucune des représentations n'est sélectionnée pour le robot par ce banc.

Commandes (recherche autorisée sur images publiques, accès réseau **opt-in**) :

```bash
python -m microduck_companion.r2b_independent_capture_eval \
  --locally-approved-research --public-abo-ccby \
  --image-model /chemin/prive/mobilenetv2-12.onnx
```

Le workflow [`r2b-abo-multiview.yml`](../.github/workflows/r2b-abo-multiview.yml) exécute ce banc sur runner temporaire pour les PR pertinentes, et est déclenchable manuellement. Les mesures publiques ne doivent être mentionnées **qu'après réussite d'une exécution identifiée** et ne valent pas validation physique Microduck. Aucun accès via le robot et aucun transfert vers un LLM.

## 2. Réutilisation et périmètre exact

| Besoin | Réutilisation | Ce qui est nouveau |
| --- | --- | --- |
| Empreintes 64 octets image / 16 octets audio | `image_fingerprint`, `audio_fingerprint` M1-A et `_image_baseline`, `_audio_baseline` M1-B2 | Aucun extracteur supplémentaire |
| Modèles comparatifs facultatifs CPU | `_image_learned` MobileNetV2, `_audio_learned` YAMNet, contrôles SHA des poids M1-B2 | Aucun modèle entraîné ou nouveau téléchargement |
| Décisions et rejet « inconnu » | `_score`, `similarity`, `conservative_threshold`, `AMBIGUITY_GAP` M1-A/B2 | Comparaison **entre objets** en open-set sur prises séparées |
| Mémoire durable | `MultiviewPatternMemory` / `ExperienceMemory` de R2-A | **Aucune nouvelle table et aucune écriture SQLite** ; la vérité terrain physique n'est pas encore un format de preuve reconnu par le schéma M1-B |
| Métadonnées et refus | `_parse_json` F3-A, politique de provenance et droit | Manifeste local de captures contrôlées et scores regroupés |

Le module ajouté est **`microduck_companion/r2b_independent_capture_eval.py`**, qui est un *évaluateur expérimental*, pas une troisième mémoire ni une API de robot.

## 3. Protocole des évaluations

### Images : COIL-20, seulement après autorisation et contrôle d'intégrité

- 20 objets, 8 angles réels distincts par objet dans la version limitée : références aux poses 0 et 36, requêtes aux poses 9, 18, 27, 45, 54 et 63. **160 PNG** sans doublons exacts.
- Validation : objets **1–8 inscrits**, objets **9–10 inconnus**. Test final : **11–16 inscrits**, **17–20 inconnus**. Aucun objet physique ne traverse les ensembles de validation et de test.
- Seuil fixé au **maximum des similarités négatives validation**, avec comparaison strictement supérieure ; ce choix prudent peut rejeter la totalité des positifs. Les mêmes seuils sont ensuite figés sur le test. Les scores sont des similarités, pas des probabilités.
- Mesures : rappels d'objets inscrits, rejets inconnus, confusions entre objets, acceptations indues d'inconnus, indécisions, taux par pose, coûts CPU utilisateur/système, pic RSS processus Linux, temps total hors transfert et temps d'inférence ONNX hors décodage. Aucun chiffre RK3566.

### Images/audio locaux : manifeste autorisé et ouvert aux vraies prises séparées

La structure anonymisée est identique pour les fichiers `.png` et `.wav`, avec des répertoires et extensions spécifiques. Chaque ligne porte exactement : `file`, `source_id` opaque, `session_id`, `take_id`, `split`, `role` et `sha256` des **octets locaux**. Les quatre partitions sont `validation`, `validation_unknown`, `test_known`, `test_unknown`. Les objets/sources sont exclusifs à une partition ; une source connue a des prises **reference** et **query** de sessions déclarées différentes ; les sources inconnues n'ont que des requêtes. Le manifeste impose au minimum **2 sources de validation connues, 1 inconnue validation, 2 sources test connues et 1 inconnue test**, au moins dix prises au total, SHA différents et noms locaux bornés.

Entête de manifeste, exemple de format **sans média** :

```json
{
  "schema_version": 1,
  "rights_basis": "locally_reviewed_license",
  "source_evidence": "independent_takes_reviewed_locally",
  "recordings": [
    {
      "file": "objetalpha-0.png",
      "source_id": "s-objetalpha",
      "session_id": "t-objetalphasession0",
      "take_id": "t-objetalphatake0",
      "split": "validation",
      "role": "reference",
      "sha256": "REMPLACER_PAR_LE_SHA256_HEXADECIMAL_DES_OCTETS"
    }
  ]
}
```

Ce fragment seul **n'est pas un manifeste complet** ; il faut au moins dix entrées réelles conformément aux règles. Les `rights_basis` possibles sont `locally_reviewed_license` et `documented_consent`. Ce sont des attestations **humaines non vérifiées automatiquement**, pas des preuves de licence ou consentement. Le rapport n'exporte ni nom de fichier, ni source ID, ni données brutes. Des fichiers privés ou personnels ne doivent pas être transmis à GitHub.

- PNG locaux : 32 à 1 024 pixels par côté, maximum 1 Mo chacun, empreinte SHA exigée, décodage Pillow à la volée et conversion vers les extracteurs *existants*. Cette contrainte technique n'est pas une garantie de confidentialité ou d'absence de personne.
- WAV locaux : exactement **1 seconde PCM16 mono 16 kHz**, maximum 48 Ko et SHA exigé. La normalisation vers M1-B 8 kHz réemploie le banc M1-B2 ; aucune transcription ni identification vocale.
- Toutes les comparaisons utilisent des **sources distinctes entre validation et test**, et une référence prise dans une session distincte des requêtes. Si les métadonnées ne sont pas fiables, la conclusion physique n'est pas fiable.

## 4. Commandes, uniquement dans l'environnement de recherche approuvé

**COIL-20 non commercial et contrôlé localement :**

```bash
python -m microduck_companion.r2b_independent_capture_eval \
  --locally-approved-research \
  --noncommercial-coil20-permission-reviewed \
  --coil20-zip /chemin/local/coil-20-proc.zip \
  --coil20-reviewed-sha256 SHA256_EXTERNE_VERIFIE
```

**Images autorisées**, sans téléchargement ni poids externe :

```bash
python -m microduck_companion.r2b_independent_capture_eval \
  --locally-approved-research \
  --image-manifest /chemin/prive/manifest.json \
  --image-root /chemin/prive/captures
```

**Sons autorisés**, sans sortie audio sauvegardée par l'outil :

```bash
python -m microduck_companion.r2b_independent_capture_eval \
  --locally-approved-research \
  --audio-manifest /chemin/prive/manifest.json \
  --audio-root /chemin/prive/enregistrements
```

Les options `--image-model` et `--audio-model` acceptent les fichiers ONNX **déjà existants** dont les hashes correspondent à M1-B2, uniquement pour une comparaison CPU hôte. Aucun accès réseau, moteur, capteur OEM, PC Qwen ni résultat d'identité certifié. Les dépendances Pillow / NumPy / ONNX Runtime restent facultatives et uniquement pour les évaluations réelles correspondant aux formats.

## 5. Validation et blocages avant R2-C

Les **tests unitaires CI sont sur données inventées** : manifestes artificiels, matrices de descripteurs fictives, sons sinusoïdaux générés, altération de SHA, source réutilisée entre splits, trames/sessions dupliquées, CLI sans consentement, refus des chemins symlinks. **Ils ne constituent pas une mesure de reconnaissance de captures réellement indépendantes**.

État à compléter depuis la CI de la PR : nombre de tests et SHA de commit. **Aucun score COIL-20 ni audio de source physique réelle n'a été mesuré** par ce lot, tant que le contenu n'est pas acquis avec des droits/étiquettes vérifiables. La mesure RSS hôte ne remplace pas l'audit de RAM réellement disponible, thermique ou latence moteur du RK3566.

**Porte de sortie scientifique R2-B :** obtenir un sous-ensemble documenté avec des captures physiques distinctes, consentement ou licence vérifié, et exécuter le benchmark une fois, puis consigner sans sélectionner un modèle sur le jeu de test. **R2-C ne doit pas conclure** sur la précision ou l'intégration embarquée avant cette preuve. La partie R2-B infrastructure peut être fusionnée indépendamment comme banc passif, sans autoriser la mémorisation réelle de média dans les tables limitées aux fixtures M1-B.
