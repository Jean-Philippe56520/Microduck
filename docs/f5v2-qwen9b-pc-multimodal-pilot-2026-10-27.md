# F5 v2 — pilote Qwen3.5 9B multimodal sur PC, images explicitement autorisées

**27 octobre 2026 — logiciel expérimental et tests de transport factice.** Aucun vrai Qwen 9B n'a été lancé dans la CI, aucune photo privée ou caméra embarquée utilisée, aucun robot testé. Le choix est **Qwen3.5 9B**, pas de comparaison 4B obligatoire. L'intégration à la cognition de Kwipi et à `ExperienceMemory` n'est **pas livrée** dans ce lot.

## Réutiliser / adapter / créer

- **OEM figé :** `robotd` garde les moteurs à 50 Hz, `mediad` capture la caméra, `tofd` les distances, `pet-detect` le son ; `ground_pick` au bec et kicks existent mais aucune préhension/autonomie physique n'est déduite ici. OEM #381/#414 restent des références non fusionnées au pin ; projets tiers du registre C3 non importés. Aucun sous-module ou policy modifié.
- **Companion réutilisé :** `OllamaEndpoint` validé par `ollama_local_client.py` F5-B. F5-A/B/C/D **v1 restent inchangés** ; ils refusent toute pseudo-reconnaissance sur des étiquettes sans pixels. `ExperienceMemory`/M1-B restent les seuls composants mémoire candidats, sans écriture par le v2.
- **Créé :** `microduck_companion/qwen9b_advisor_v2.py`, pilote **PC local, à déclenchement manuel** : préparation JPEG redimensionné et sans EXIF/XMP/ICC, protocole multimodal Ollama `/api/chat`, contrat de réponse v2 à énumérations strictes et tests nominatifs/négatifs. Ce pilote ne s'active PAS automatiquement à partir des observations, n'ouvre ni capteur ni SQLite, ne crée aucune intention motrice et ne réinjecte rien dans F2.

## Protocole du pilote

L'opérateur choisit une image **dont il détient les droits, qu'il a examinée et qui n'expose aucune personne, enfant, voix ou donnée privée**. Deux confirmations explicites sont obligatoires à chaque appel ; les booléens logiciels ne constituent pas une preuve de consentement physique. Le PC décode en RAM, recadre implicitement par `thumbnail()` (sans rognage du contenu) et réduit à 512 x 512 maximum ; recompression JPEG jusqu'à 100 000 octets, entrée source plafonnée à 2 Mo/16 mégapixels. Métadonnées EXIF/XMP/ICC supprimées. **Cela n'anonymise pas le contenu visuel : l'opérateur doit écarter manuellement les contenus privés.** Aucune photo n'est persistée par le pilote.

Le modèle reçoit un `system` de contraintes, un `user` avec une unique image base64 et la catégorie locale éventuellement `unknown`, sans coordonnées, paroles, individus, SQLite, empreintes, récompense ni capacité physique supposée. Sortie JSON v2 bornée à trois hypothèses, chacune avec catégorie, confiance seulement déclarée, propriétés possibles, usages possibles, relations, conséquences hypothétiques, suggestions d'**observation passive** et risques/incertitudes. Pas de texte libre, identité, script ni appel d'outil. Même `confidence=1` n'est pas une observation ou un fait. Les suggestions ne sont ni stockées ni exécutées.

Le pilote exige l'endpoint HTTP d'Ollama sur loopback `127.0.0.1` (ou tunnel authentifié terminant sur loopback), via la validation F5-B. Aucun accès direct au LAN. **La machine hôte peut appeler Ollama sur localhost sans TLS parce que le transport reste dans l'hôte**, mais la future liaison robot↔PC devra être chiffrée et authentifiée, et avec quota, consentement et travailleur hors boucle motrice. Le pilote PC est **synchrone** et NE DOIT PAS être appelé depuis le cerveau embarqué ni depuis `robotd`. Fenêtre maximale 180 secondes, délai de réponse locale horodaté, corps HTTP et JSON plafonnés ; **`num_ctx=4096` fixé sur chaque requête du pilote PC afin de ne pas hériter d’un immense contexte serveur** ; il ne constitue pas une garantie temps réel contre tous les serveurs malveillants.

### Exécution sur le PC Windows (hors CI)

Avec Ollama installé localement, depuis PowerShell sur le PC :

```powershell
ollama pull qwen3.5:9b
ollama list
ollama ps
```

Dans une copie locale **à jour** de Microduck Companion :

```powershell
py -3.12 -m venv .venv-qwen9b
.\.venv-qwen9b\Scripts\python.exe -m pip install Pillow==11.3.0
.\.venv-qwen9b\Scripts\python.exe -m microduck_companion.qwen9b_advisor_v2 --image "C:\chemin\vers\image-publique.jpg" --ollama-port 11435 --timeout 180 --authorize-image --reviewed-no-private-subjects
```

Le port `--ollama-port 11435` vise explicitement le serveur GPU dédié identifié localement. Par défaut le pilote garde `11434`; le port est validé sur 1–65535 et l’hôte reste exclusivement `127.0.0.1`. Ce choix ne modifie pas le système ni le serveur existant. Le pilote peut produire `unverified` (schéma accepté, hypothèses non vérifiées), `rejected` (format/refus), `stale` (retard) ou `unavailable` (service absent).

Ne pas utiliser les 29 photos privées Cat-A2b sans revue explicite de leur confidentialité et de leurs droits. L'outil affiche seulement le résultat structuré et la latence locale, pas l'image ; il ne prouve pas que Qwen a répondu correctement. **Ne pas exposer le port 11434 directement sur le réseau**. Les mesures p50/p95/RSS d'un vrai 9B restent à effectuer sur le PC Ryzen AI / 64 Go, sans supposer un accélérateur actif.

### Validation technique

`python -m unittest tests.test_qwen9b_advisor_v2 -v` (sur un PC avec Pillow installée), puis CI Python complète. Tests : image autorisée, suppression EXIF, réduction, budget, JPEG corrompu, mauvais consentement, schéma strict, rejet de commande/identité/sûreté fabriquée/clé dupliquée, périmé, faux serveur local, absence d'Ollama et refus d'endpoint non local. **Une réussite CI signifie compatibilité de protocole et gardes logiciels seulement**, pas reconnaissance visuelle réelle, sécurité animal, mémoire causale ou performance sur RK3566.

### Suites distinctes

1. **Essai 9B réel** sur 5 à 10 images publiques/locales autorisées, avec vérité terrain indépendante, cas inconnus et scène contenant animal **uniquement si autorisation**, comparer erreurs/hallucinations, refus et p50/p95 sur PC. Revoir le vocabulaire sans ajuster les résultats a posteriori.
2. **F5 v2 liaison optionnelle** après fiabilisation des sources : quotas F5-C, `AutonomyBrain` local d'abord, rappel mémoire avant PC, worker non bloquant et rejet de scène périmée ; jamais d'autorisation moteur.
3. **Mémoire C** : contracter/projeter les hypothèses dans la SQLite existante, rétention/correction/consolidation, sans promotion en fait ni nouvelle table sans revue. Preuve physique EX4-C2 distincte.
4. **Portage robot seulement après** Cat-A2b indépendamment annoté, ressources `scripts/resource-audit.sh`, état OEM/board réel et sûreté auditée.
## Premier essai avec Ollama 9B sur PC Windows (rapport opérateur du 27/10/2026)

- Modèle réellement téléchargé : `qwen3.5:9b` ; accélération GPU Radeon 860M rapportée avec serveur local `127.0.0.1:11435` ; aucune mesure de RSS validée par le dépôt.
- Image de démonstration **synthétique** (disque rouge dessiné, 512 × 512, créée par l'opérateur localement), ni photographie d'objet réel, ni jeu de données privé transmis au dépôt.
- Premier appel réel au pilote : statut `unverified`, catégorie `unknown`, confiance déclarée 0,1, latence 25,312 s, zéro commande moteur / écriture mémoire. L'abstention est raisonnable : un disque plat dessiné ne certifie pas une balle réelle.
- Deuxième appel identique : `rejected`, latence 28,5 s, aucune hypothèse conservée, zéro commande moteur / écriture mémoire. **La cause du refus initial n'est pas observable** avec l'ancien statut agrégé ; ne pas inventer un dysfonctionnement Qwen ni attribuer une erreur de schéma sans preuve.
- **Correctif de diagnostic (ce lot)** : `diagnostic_stage` à valeurs strictement locales `none`, `http_protocol`, `ollama_envelope`, `generation_limit`, `model_output`, `transport` ou `deadline`. Aucun texte brut de Qwen, image, nom ni identifiant privé ne sort en log. Le validateur, l'abstention, les budgets et l'autorité motrice restent inchangés. Une génération `done_reason=length` est explicitement classée comme sortie tronquée et rejetée.
- **Mesure à poursuivre** après mise à jour de la branche sur Windows : répéter le même test 3 fois, consigner statut et `diagnostic_stage` (sans image ni sortie modèle brute), puis tester quelques photos d'objets autorisées avec référence indépendante ; surveiller latence et saturation. `keep_alive=0` décharge Qwen après chaque appel de ce pilote et peut allonger le temps total ; ne pas confondre cela avec un serveur arrêté.

**Niveau de preuve :** retour d'exécution réel sur PC utilisateur, non reproductible dans la CI sans son matériel ni ses images. Le correctif ne prétend pas résoudre la variabilité du modèle ; il permet de la qualifier. Pas d'entraînement ni de validation robot.

## F5 v2 - correction de diagnostic apres `model_output` (27/10/2026)

Deux essais reels sur le PC de l'operateur se terminent par `rejected` apres une premiere reponse `unknown` acceptee. Le diagnostic de premier niveau `model_output` localise le refus dans `parse_reply` : il ne prouve pas la nature de l'erreur. La prochaine execution fournit `diagnostic_reason`, code fixe parmi `none`, `json_invalid`, `duplicate_key`, `response_size`, `schema_invalid`, `request_id_mismatch`, `hypotheses_invalid`, `fields_invalid`, `category_invalid`, `confidence_invalid`, `enum_invalid`, `other`. Ni reponse brute, ni image, ni texte libre, ni valeur de champ ne sont conserves ou imprimes.

Le `format` JSON Schema demande maintenant `request_id: {type: string, enum: [UUID_de_la_requete]}` : cela peut diminuer les refus dus a la copie erronee de l'identifiant mais **la verification de correlation sur la reponse reste obligatoire**. Pas d'assouplissement du validateur, pas de correction silencieuse, pas de nouvelle requete automatique, pas de changements moteurs/SQLite, pas d'autre modele. **Hypothese de diagnostic, non cause prouvee ni correction validee sur le vrai Qwen**. Les tests locaux avec un faux `OllamaEndpoint` et serveur HTTP : 18/18 ; le depot et la CI Python reelle feront autorite pour le lot publie.

Apres `git pull --ff-only` dans le clone de la branche PR #98 sur Windows, faire **un seul** essai supplementaire avec l'image synthetique deja autorisee :

```powershell
& "$HOME\.venv-qwen9b\Scripts\python.exe" -m microduck_companion.qwen9b_advisor_v2 --image "$HOME\kwipi_balle_test.jpg" --ollama-port 11435 --timeout 180 --authorize-image --reviewed-no-private-subjects
```

Comparer `status`, `diagnostic_stage`, `diagnostic_reason` et `latency_s`. Les images et les reponses Ollama brutes ne doivent pas etre transmises. Si le modele renvoie `unverified`, la structure est acceptee mais **aucune reconnaissance d'objet reel n'est demontree** : `unknown` reste recevable devant un disque 2D.

## Mode `simple` et demarrage Windows reproductible (27 octobre 2026, PR #98)

**Pourquoi :** des essais reels avec Qwen3.5 9B sur Windows 11 et Radeon 860M ont abouti a une reponse `unknown/unverified` a 25,312 s puis des rejets `model_output/enum_invalid` (autour de 28–30 s) pour un disque rouge synthetique. Ce diagnostic pointe le vocabulaire trop complexe du pilote **strict**, pas une preuve d'incapacite visuelle du modele. Il n'y a pas de nouvelle comparaison 8B et aucun modele supplementaire a telecharger pour ce lot.

- **Profil minimal** `--mode simple` (nouveau defaut CLI) : exactement quatre champs obligatoires dans le JSON Ollama : `request_id` (UUID exact lie a la requete), `category` (categorie parmi les 11 valeurs existantes, dont `unknown`), `depiction` (`photograph/drawing/screen/unknown`), `visibility` (`clear/partial/uncertain`). Pas de generation de sept tableaux, pas de confiance numerique fabriquee, ni vocabulaire libre ou histoire d'objet. Le resultat est toujours **non verifie**, sans commande moteur, action, recompense, causalite ni memorisation.
- **Ancien profil** `--mode strict` conserve exactement le contrat F5 v2 d'hypotheses/proprietes/usages/risques. Pas de modification de F5 v1 ni de robotd. La sortie de l'Advisor simple ne remplace ni la reconnaissance locale par detecteur ni les traces d'effet reel.
- **Garde-fous identiques** : boucle locale uniquement via `OllamaEndpoint`, un unique JPEG approuve et retaille <=512 px / <=100 ko, source <=2 Mo / 16 MP, contexte 4 096 tokens, `think:false`, expiration 180 s maximum, enveloppe et JSON strictement bornes, UUID/categorie revalides. Tous les rejets sont sans hypothese exploitable. Les champs imprimes sont des enums et mesures locales, jamais les pixels ou reponses brutes de Qwen. `keep_alive=0` conserve la liberation du modele apres chaque essai.
- **Lanceur Windows** : apres un seul `git pull --ff-only` dans `C:\Users\Jp\Microduck-Qwen9B`, ouvrir `TESTER_KWIPI.cmd` par double clic ; le lanceur PowerShell (execution locale `RemoteSigned` sans changement persistant de politique) detecte `C:\Users\Jp\.venv-qwen9b\Scripts\python.exe` ou l'environnement venv du depot, controle `127.0.0.1:11435/api/tags` et la presence de `qwen3.5:9b`, propose une boite de selection, refuse les images >2 Mo et **demande de taper OUI** apres examen et autorisation de l'unique photo. Il n'installe pas Git/Ollama/modeles ; si le serveur 11435 est indisponible, il tente de lancer un processus `ollama.exe serve` local et temporaire après la confirmation de l'image, sans garantie de placement GPU et sans modifier le service 11434. L'image reste sur le PC ; Ollama la recoit exclusivement via loopback. Aucun media ni souvenir ni texte de Qwen n'est envoye a GitHub.
- **CLI reproductible** : `python -m microduck_companion.qwen9b_advisor_v2 --image <chemin> --ollama-port 11435 --mode simple --timeout 180 --authorize-image --reviewed-no-private-subjects` apres revue de la photo. Les deux indicateurs signifient une revue reellement faite, pas une option a automatiser pour des dossiers entiers.
- **Interpretation** : `status=unverified` et `visual_observation` = hypothese structuree acceptee, pas detection averee ; `status=rejected` et `diagnostic_reason` = aucun resultat valide. Un disque rouge dessine devrait permettre l'abstention ; seule une evaluation sur photos d'objets varies, independamment annotes, pourra etablir precision, confusions et generalisation. Ne pas deduire la qualite d'un seul exemple.

**Niveau de preuve :** pilote code et tests Python sur faux Ollama (25/25 en local) ; verifications Linux de la syntaxe Python ; fichiers PowerShell / CMD controles statiquement, mais **non executes en Windows CI**. Aucun nouveau test reel du mode `simple`, aucune mesure de GPU/RSS avec celui-ci, aucune validation de capteurs, de motorisation ou du robot non recu. CI GitHub du commit de ce lot a verifier. Prochaine etape : ouvrir le lanceur Windows avec l'image synthetique deja autorisee, consigner uniquement `status`, `visual_observation`, `latency_s` et diagnostics ; puis vrais objets photographies avec consentement, en conservant le jeu Cat-A2b prive hors GitHub.

## Environnement virtuel de test GitHub automatisé

Le workflow existant `.github/workflows/python-tests.yml` installe désormais un `venv` Python **temporaire** par GitHub Actions run (`$RUNNER_TEMP/microduck-companion-venv`), avec Python 3.11 / Pillow 11.3.0. Il vérifie l'isolation, exécute tous les tests et démos **sur fixtures/serveurs fictifs** puis GitHub détruit l'ordinateur temporaire. Les branches avec PR ne déclenchent plus à la fois `push` et `pull_request`, pour éviter la duplication de minutes ; `main` reste testé à chaque push. Le code n'ajoute ni fichier `.venv` dans Git, ni image de l'opérateur, ni poids de modèle. Aucun travail permanent ne tourne à l'arrière-plan.

Cet environnement ne peut **pas** joindre le `127.0.0.1:11435` du Windows de l'opérateur, ni utiliser sa Radeon 860M, ses images locales ou le robot absent. La validation sur vrai Qwen reste un essai local explicite via `TESTER_KWIPI.cmd`, après autorisation et choix d'une image. Pas de runner auto-heberge Windows public propose sans audit de sécurité : un runner de dépôt public permettrait une exécution de code non désirée avec accès aux fichiers de la machine.

Niveau de preuve : CI avec faux Ollama, pas d'inférence réelle ou de généralisation validée.
## Correctif Windows : serveur Ollama dédié non actif (retour opérateur 27/10/2026)

Le premier double-clic de `TESTER_KWIPI.cmd` a indiqué `Serveur Ollama local inaccessible sur le port 11435`, avant tout choix d'image. **Cet échec est un résultat réel de l'ancien lanceur, pas une preuve d'échec du 9B.** Le serveur secondaire n'était plus joignable ; il n'y a aucun motif de réinstaller Ollama, Python ou le modèle.

Le correctif réutilise l'exécutable `ollama.exe` **déjà installé**, sans service externe ni dépendance ajoutée :

1. Le lanceur fait choisir une image, la contrôle sous 2 Mo, exige une revue et le consentement `OUI` **avant tout démarrage** et tout traitement de pixels.
2. Il interroge exclusivement `127.0.0.1:11435/api/tags`. S'il est joignable, il réutilise le serveur existant et **ne l'arrête jamais**.
3. Sinon, il recherche `ollama.exe` dans le PATH Windows, définit seulement dans son propre processus les variables `OLLAMA_HOST=127.0.0.1:11435`, `OLLAMA_VULKAN=1`, `OLLAMA_IGPU_ENABLE=1`, puis lance `ollama serve` en fenêtre cachée. Il attend sa disponibilité sur un nombre fini de sondes, sans boucle infinie, ni téléchargement de modèle.
4. Si le serveur est disponible **et** contient `qwen3.5:9b`, il appelle **une seule fois** le pilote `simple` avec l'image autorisée. En fin d'exécution (succès, refus ou erreur), il tente d'arrêter **uniquement le processus Ollama qu'il a créé** ; aucune fermeture globale des services Ollama ni des autres processus.
5. En cas d'échec de démarrage, d'absence de modèle ou de problème de connexion, aucune commande Qwen/robot/mémoire n'est émise et le script indique le blocage. L'usage de Vulkan/iGPU n'est qu'une demande d'accélération : vérifier séparément si Ollama place effectivement le modèle sur GPU.

**Validation :** tests Python de contrat (26/26 en local), examen statique du script ; ajout d'une étape d'analyse syntaxique PowerShell sur GitHub Actions. Ce ne sont **pas** des tests d'exécution du lanceur sur Windows : le double-clic par l'opérateur est requis pour confirmer que `Start-Process`, la reprise de service et le nettoyage fonctionnent effectivement dans cette configuration. Aucun accès à la Radeon/aux photos de l'utilisateur par GitHub Actions. La PR #98 demeure non fusionnée tant qu'elle n'est pas validée et acceptée.

## Premier essai du lanceur auto-démarrant et du mode simple — rapport de l'opérateur du 27 octobre 2026

**Image réellement soumise, précisée par l'opérateur :** capture d'écran de l'Explorateur de fichiers Windows affichant des dossiers (et du texte à l'écran), **pas** le disque rouge synthétique évoqué dans les essais antérieurs. L'opérateur a transmis la capture dans la conversation pour expliquer ce choix ; les pixels, noms des dossiers, captures et chemins d'utilisateur **ne sont pas copiés dans GitHub**. L'opérateur a tapé `OUI` pour ce seul essai, mais la présence de texte et de chemin utilisateur rappelle qu'un consentement manuel n'est pas un contrôle automatique de confidentialité ; les prochains essais privilégieront des images d'objets sans texte ni données privées.

**Sortie du vrai Qwen3.5 9B, rapportée par l'opérateur :**

```json
{
  "diagnostic_reason": "none",
  "diagnostic_stage": "none",
  "hypotheses": [],
  "latency_s": 10.078,
  "memory_writes": 0,
  "mode": "simple",
  "motor_commands_issued": 0,
  "status": "unverified",
  "visual_observation": {
    "category": "unknown",
    "depiction": "unknown",
    "verified": false,
    "visibility": "clear"
  }
}
```

**Faits observables :** le lanceur Windows a signalé le démarrage automatique d'Ollama local `127.0.0.1:11435`, le résultat accepté par le protocole, puis la fermeture du seul serveur qu'il venait de lancer. Ces faits sont rapportés par l'opérateur, non reproduits dans la CI Linux. La **sortie JSON est acceptée par la validation de contrat, mais la perception n'est pas validée** : `category=unknown` est une abstention défendable puisqu'il ne s'agit pas d'un objet physique unique ; `depiction=unknown` manque pourtant la valeur `screen` attendue d'une capture d'écran. La visibilité `clear` ne compense pas cette incertitude. Un seul essai ne permet pas de conclure sur la qualité de vision du Qwen 9B.

La latence de 10,078 s est un chiffre du logiciel PC pour cet essai, pas une mesure fiable de débit ou d'utilisation GPU (options Vulkan/iGPU demandées, placement GPU et RSS non mesurés). Ne pas comparer directement les essais antérieurs sur disque rouge et le schéma strict aux conditions actuelles ; pas de robot disponible, aucun capteur ou effet autonome testé. Les compteurs zéro moteur et zéro mémoire sont des compteurs du pilote PC passif, pas une preuve instrumentée sur robot.

**Suite prioritaire :** faire quelques essais unitaires du lanceur sur **photographies d'objets inanimés** explicitement autorisées, avec catégorie attendue déterminée indépendamment, scènes simples puis masquées/inconnues. Noter `status`, `visual_observation.category`, `visual_observation.depiction` (souvent `photograph` attendu), `visibility`, refus et latence ; aucune capture contenant identifiants, documents, personnes ou informations privées. Ne pas publier les fichiers sources ni fusionner les résultats avec l'ExperienceMemory tant que l'évaluation visuelle n'est pas concluante.

## F5 v2 — échec de catégorie sur photo réelle et autotest d'entrée image (27 octobre 2026)

### Rapport de l'opérateur sur une photographie autorisée

L'opérateur a soumis une photographie de couchage pour animal, à faible hauteur avec meubles en arrière-plan (aucune image/copie ajoutée au dépôt). Annotation indépendante **avant** lecture de la réponse : catégorie attendue `dog_bed` dans les 11 classes disponibles, `depiction=photograph`, visibilité `clear` ou `partial` en fonction du cadrage. Le vrai Qwen3.5 9B sur Ollama localhost GPU demandé a retourné :

```json
{"diagnostic_reason":"none","diagnostic_stage":"none","hypotheses":[],"latency_s":9.703,"memory_writes":0,"mode":"simple","motor_commands_issued":0,"status":"unverified","visual_observation":{"category":"unknown","depiction":"unknown","verified":false,"visibility":"partial"}}
```

**Conclusion :** le transport et le **schéma** sont fonctionnels, mais la reconnaissance visuelle de la catégorie et du type photographique échoue pour ce cas. L'abstention peut être légitime lorsque l'information est insuffisante, mais elle ne prouve pas à elle seule que le modèle a exploité les pixels. Ne pas stocker l'objet en mémoire et ne pas interpréter `unverified` comme une prédiction correcte. Latence GPU réelle et RSS non mesurés ; temps rapporté de 9,703 s non extrapolable au robot absent.

### Nouvelle commande : `VERIFIER_VISION_KWIPI.cmd`

Après `git pull --ff-only` dans le clone Windows `Microduck-Qwen9B`, double-cliquer `VERIFIER_VISION_KWIPI.cmd`. Ce lanceur appelle le même script PowerShell, réutilise `ollama.exe` local (port dédié `11435`), et exécute deux demandes **explicites et limitées** sans demander une photo : un carré rouge uni puis un carré bleu uni (256×256), générés en mémoire et recompressés en JPEG sans métadonnées. Aucun fichier utilisateur n'est ouvert, aucune image n'est écrite sur le disque, aucune photo personnelle/identité n'est transmise à GitHub ou au réseau externe. Le modèle reste Qwen3.5 9B sur PC ; le script n'installe ni poids ni pilote. Le serveur local n'est fermé que s'il a été démarré par ce lanceur.

L'autotest réutilise le transport borné, le contrôle de frais/expiration (120 s maximum par appel), un seul JPEG par requête, `num_ctx=4096`, `think=false`, validation `request_id` exact, contenu JSON limité à `{request_id,color}` et `color in {red,blue,unknown}`. Toute réponse malformée est rejetée sans effet sur robot/SQLite ; si la première requête échoue, la seconde n'est pas lancée. La console n'affiche que `expected`, `observed`, `status`, `diagnostic_stage`, `diagnostic_reason` et latence, jamais les textes bruts du modèle. Le code n'exécute pas de commandes moteurs et n'écrit aucun souvenir.

**Interprétation** : `result=two_colors_distinguished` indique que le vrai Qwen a correctement différencié ces deux entrées simples sur ce PC dans ce test, **pas une validation générale de la vision**, de `dog_bed`, d'une identité ou de l'autonomie. `result=not_demonstrated` ne permet pas d'attribuer la panne au modèle ou au transfert d'image : examiner ensuite API/chargement multimodal, contexte et prompt séparément. Le constructeur Ollama documente `images` comme tableau de JPEG encodés base64 sur `/api/chat`, mais seuls des essais réels trancheront : https://docs.ollama.com/capabilities/vision.

**Validation :** 34 tests ciblés réussis localement, dont 8 nouveaux sur la génération synthétique, JSON, HTTP loopback factice, erreurs invalides, arrêt après échec et lanceur; **aucun Qwen réel ni Windows dans ces tests**. La CI GitHub vérifie l'analyse syntaxique PowerShell et les fixtures Python ; passage de la CI du commit à consigner. La PR #98 reste ouverte et non fusionnée. Le protocole d'essai est ciblé et ne constitue ni apprentissage neuronal ni entraînement de Kwipi.

## Retour PC rouge/bleu et comparaison A/B de consignes — 27 octobre 2026

### Fait réel : le modèle distingue les couleurs transmises

L'opérateur a exécuté `VERIFIER_VISION_KWIPI.cmd` avec le vrai `qwen3.5:9b` sur son PC Windows et son Ollama local dédié sur `127.0.0.1:11435`. Les images ont été construites en RAM, à 256×256, sans photo utilisateur. Les couleurs attendues `red` et `blue` sont présentes **seulement** dans le générateur/evaluateur local, **jamais** dans le prompt, le schéma ou le contenu transmis à Qwen (hors pixels JPEG). Résultats observés : `red -> red` en **9,047 s**, `blue -> blue` en **9,813 s** ; deux statuts `unverified` sans diagnostic d'erreur, aucun média privé lu, zéro écriture mémoire et zéro commande moteur (compteurs du pilote PC). Cela démontre une différenciation simple compatible avec un chemin multimodal opérationnel, **pas une compréhension visuelle générale ni une exactitude mesurée sur objets**.

Sur une photographie d'un couchage pour animal fournie et autorisée séparément, la sortie réelle était `category=unknown, depiction=unknown, visibility=partial` en 9,703 s ; les étiquettes indépendantes de comparaison sont `dog_bed`, `photograph`, visibilité `clear` ou `partial` selon cadrage. La cause de cette abstention n'est pas identifiée : prompt prudent, cadrage, classe ou limite du modèle restent possibles.

### Nouveau test de contraste, sans changement de modèle

La branche de la PR #98 introduit :

- `balanced` (mode de laboratoire uniquement) : **même** image JPEG, JSON Schema `request_id/category/depiction/visibility`, options Ollama, limites, validateur et Qwen 9B ; seule l'instruction SYSTEM change. Elle sollicite la **catégorie la plus plausible** si les indices sont suffisants, autorise `other_object` et conserve `unknown` en cas de manque réel d'indices, sans identité, propriété garantie, permission ou ordre moteur. Elle ne contient **pas** l'étiquette attendue `dog_bed` ni description d'une scène particulière ; cela évite de communiquer la réponse au modèle.
- `COMPARER_VISION_KWIPI.cmd` : lance le script PowerShell déjà existant avec `-ComparePrompts`, propose **une seule photo** révisée, explicite que l'autorisation `OUI` couvre **exactement deux appels** à Ollama localhost (d'abord `simple`, puis `balanced`). Le fichier est lu une fois, redimensionné une fois en JPEG 512 px / 100 ko max sans métadonnées, puis les deux appels utilisent **exactement les mêmes pixels** et des UUID frais. Si la première requête est rejetée/indisponible, la seconde n'est pas lancée. Les seules sorties sont des codes JSON bornés (`category`, `depiction`, `visibility`, statut, diagnostic, latence) ; aucune réponse libre, image, texte privé, SQLite ni média n'est enregistré ou transféré à GitHub. Le même processus Ollama local temporaire est fermé après l'essai, s'il a été lancé par ce script.
- **Aucune inférence de correction automatique :** `result=comparison_completed` signifie seulement que les deux réponses ont été reçues et acceptées syntaxiquement. Ce n'est pas une victoire du prompt `balanced`, ni une preuve de reconnaissance. Une seule photo et deux générations ne suffisent pas à évaluer les taux de fausses catégories. L'annotation indépendante doit précéder l'analyse ; répéter sur scènes diverses (objets familiers, objets hors vocabulaire, angles bas et occultations) après ce diagnostic.

**Validation du code :** 40 tests ciblés locaux réussis sur faux Ollama, dont nouveaux tests pour les deux requêtes avec JPEG identique, UUID distincts, sortie refusée, consentement, limites et lanceur ; CI GitHub de ce commit à vérifier. Le vrai modèle 9B n'a pas encore exécuté le **mode balanced**, et la photo domestique n'est pas incluse dans le dépôt. Aucun robot physique, modèle neuronal réentraîné, contrôle moteur ou intégration mémoire n'a été introduit.

## A/B réel sur photographie de couchage pour animal — rapport opérateur du 27 octobre 2026

Après réussite de l'autotest rouge/bleu, l'opérateur a exécuté `COMPARER_VISION_KWIPI.cmd` sur une **photographie réelle déjà autorisée**. Le résultat a été communiqué uniquement sous forme de JSON de catégories et de mesures : aucune photographie ni réponse brute du modèle n'a été copiée dans GitHub. La catégorie de référence, fixée lors de l'inspection préalable de cette photo, est **`dog_bed`** pour le couchage/rembourrage destiné à un animal (hypothèse visuelle plausible, non preuve du propriétaire ou de l'usage exact) ; le type de support attendu est `photograph`.

| Mesure | `simple` | `balanced` |
|---|---|---|
| `status` | `unverified` | `unverified` |
| `diagnostic_stage/reason` | `none/none` | `none/none` |
| `category` | `unknown` | `other_object` |
| `depiction` | `unknown` | `photograph` |
| `visibility` | `clear` | `clear` |
| `latency_s` | `11.172` | `11.953` |

`result=comparison_completed`, `verified_recognition=false`, `photos_saved_by_companion=0`, `motor_commands_issued=0` et `memory_writes=0` dans la sortie du **pilote PC passif**. Le code confirme que l'image JPEG retraitée, les énumérations admises et le schéma JSON sont identiques entre les deux appels ; seules les consignes système, l'UUID de corrélation et l'heure de requête diffèrent. L'étiquette `dog_bed` attendue n'est injectée dans aucun prompt.

**Interprétation :** `balanced` montre une amélioration locale du type d'image et passe d'une abstention totale à un objet générique. **La catégorie souhaitée n'est correctement reconnue par aucun des deux modes.** L'expérience sur une seule photo ne suffit pas pour choisir définitivement un prompt, affirmer une compétence de perception fiable ou comparer les vitesses. Il est prématuré d'ajouter ces sorties à `ExperienceMemory`, d'exécuter des gestes OEM ou d'imputer l'erreur uniquement aux poids du modèle. Le test couleur établit une discrimination élémentaire, pas la reconnaissance sémantique d'objets.

**Porte de validation suivante (sans changer les prompts en fonction de ce résultat) :** utiliser un petit jeu de photographies **inédites, consenties et indépendamment annotées**, incluant des classes présentes (`ball`, `chair`, `sock`, `cat`, `dog`, `dog_bed` seulement si autorisé), ainsi que des objets hors taxonomie (par exemple `shoe` qui n'est pas dans les 11 classes et doit être compté `other_object`, et `unknown` pour les ambiguïtés véritables). Préférer les objets inanimés pour commencer, avec scènes simples, basses et partiellement visibles. Garder le même 9B, le même JPEG/contrat sur les deux modes ; compter les bonnes catégories, mauvaises classifications, abstentions, types d'image et latences, sans exporter de médias. Les séries très petites sont exploratoires, non une mesure robuste de généralisation. Aucun test réel du robot ni des ressources RK3566.

## A/B réel n°2 — chaise à faible hauteur devant une table (27 octobre 2026)

**Source et vérité visuelle avant résultat :** l'opérateur a fourni dans la conversation une photo de chaise grise rembourrée avec une table occupant une large partie de l'arrière-plan/du haut de la scène. La **cible visée** est la chaise ; `category=chair` (catégorie déjà disponible), `depiction=photograph`, et `visibility=clear` ou `partial` selon l'importance donnée au dossier recadré. La photo personnelle n'est **pas** ajoutée à GitHub et le pilote n'a enregistré ni pixels ni réponse brute. Les deux analyses ont été approuvées par l'opérateur sur son Ollama local `127.0.0.1:11435`.

| Champ | Attendu pour la chaise visée | Simple | Balanced |
| --- | --- | --- | --- |
| `status` | réponse non vérifiée | `unverified` | `unverified` |
| `category` | `chair` | `unknown` | `other_object` |
| `depiction` | `photograph` | `unknown` | `photograph` |
| `visibility` | `clear` ou `partial` | `clear` | `clear` |
| `latency_s` | n/a | **11.250** | **13.016** |
| diagnostics | aucun échec de schéma | `none/none` | `none/none` |

Le comparateur a renvoyé `result=comparison_completed`, `verified_recognition=false`, `photos_saved_by_companion=0`, `memory_writes=0`, `motor_commands_issued=0` ; ce sont des **compteurs du pilote PC**, non du robot. Ces résultats reproduisent le motif de la précédente photo de couchage : le mode équilibré choisit le type de support correctement mais pas la catégorie d'intérêt.

**Audit du prétraitement, réalisé hors GitHub sur une copie de l'image partagée dans la conversation :** entrée JPEG **1 152 × 1 536**, 545 381 octets, sortie selon `prepare_jpeg` (Pillow, auto-orientation EXIF, RGB, `thumbnail((512,512))`, JPEG qualité 75 sans métadonnées) = **384 × 512**, **28 855 octets**. En inspection humaine, la silhouette rembourrée de la chaise, ses pieds et son assise sont toujours discernables. L'image réduite n'est pas sauvegardée dans le dépôt ; cette vérification ne prouve pas les octets exacts transmis par le PC de l'opérateur. Le simple redimensionnement n'explique pas manifestement l'erreur, mais son impact quantitatif n'a pas été évalué.

**Point de prudence :** `other_object` pourrait désigner la table (ou d'autres objets) plutôt que la chaise : la taxonomie F5 v2 comprend `chair`, mais pas `table`, et l'actuel schéma ne renvoie ni localisation ni objet de référence. Ne pas présenter cet essai comme preuve que le modèle est incapable de reconnaître une chaise ; il a **échoué à classer la cible choisie par l'humain dans cette scène**. Tester des photos d'objets uniques à composition simple puis de la même catégorie en scène multi-objets, avec référence établie avant inférence, pour isoler l'erreur de focus, de prompt, de redimensionnement ou de capacité multimodale. Éviter de retoucher l'invite sur ces deux exemples et de connecter les hypothèses à `ExperienceMemory` ou au robot.

## Baseline de compréhension native hors Advisor et latence — rapport opérateur du 27 octobre 2026

**Résultat réel important :** l'opérateur a interrogé le vrai `qwen3.5:9b` via PowerShell sur son Ollama local `127.0.0.1:11435`, **sans notre Advisor**, avec `ollama run qwen3.5:9b --think=false` et la photographie originale d'une chaise dans une pièce. La CLI a signalé `Added image` ; la réponse française décrit précisément un **fauteuil/chaise gris texturé avec pieds métalliques**, une **table** et une **deuxième chaise**, ainsi qu'un **radiateur**, des plantes, des câbles et le sol. Ce sont des reconnaissances visuelles pertinentes sur cette scène, qui contredisent l'idée que les poids du 9B seraient incapables de reconnaître une chaise. D'autres détails générés (matière exacte du bois, moment de la journée, interprétation de petits objets) restent des **hypothèses non vérifiées**. Aucune image privée ni sortie brute longue n'est ajoutée au dépôt.

L'opérateur a confirmé par `GET /api/tags` que le serveur répond sur `11435`, et par `ollama show qwen3.5:9b` : modèle `qwen35`, **9,0B** de paramètres, Q4_K_M, contexte maximal déclaré `262144` (pas la taille nécessairement utilisée), capacités `completion/vision/tools/thinking` et projecteur visuel de **456,01 millions** de paramètres. `ollama ps` était **vide avant** l'appel CLI, c'est-à-dire qu'aucun modèle n'était chargé à cet instant ; le placement réel GPU pendant la description native n'a pas été mesuré. Le modèle est confirmé vision, **pas d'accélération GPU prouvée pour ce run particulier**.

La génération d'une **longue description** a pris « environ une minute » selon l'opérateur, durée **approximative, non chronométrée par phase** ; les essais JSON courts `simple`/`balanced` prenaient environ **10–13 secondes** mais donnaient `unknown`/`other_object` sur ce même sujet. **Ces chiffres ne démontrent pas que JSON est plus rapide à compétence égale** : la CLI reçoit la **photo originale** avec une demande libre et produit de nombreux tokens ; l'Advisor reçoit un **JPEG redimensionné (384×512 pour cette photo)**, un prompt restrictif, un schéma JSON à 4 champs et un budget `num_predict=180`. Le résultat ne permet pas d'isoler l'impact de la compression, du cadrage, du prompt, du schéma, de la longueur de sortie ou du chargement à froid. Le précédent autotest rouge/bleu démontre seulement la discrimination de deux images simples.

### Décision et prochain diagnostic PC (prévu, non livré par cet addendum)

- **Conserver le Qwen3.5 9B existant**, sans téléchargement 8B imposé ni réentraînement.
- Concevoir un test avec **même image JPEG consentie, mêmes paramètres, même cible d'attention, même serveur** et une sortie **très courte**, puis comparer description naturelle, description contrainte et vocabulaire de catégorie en évitant d'injecter la réponse attendue. Sur les **scènes inédites préannotées**, mesurer justesse, abstentions, erreurs, faux positifs et latence, sans ne sélectionner que les exemples déjà vus. Ne pas exporter de média privé ou de texte généré qui pourrait révéler des informations personnelles.
- Pour la latence, lire les champs Ollama `total_duration`, `load_duration`, `prompt_eval_duration`, `eval_duration`, `eval_count` (nanosecondes sauf comptages) plutôt qu'un seul temps global. Faire des demandes courtes, limiter `num_predict` et le contexte, puis seulement comparer avec un `keep_alive` limité **sur PC**, si mémoire/RSS/GPU mesurés le permettent. Le pilote actuel utilise `think=false`, `num_ctx=4096` et `keep_alive=0` (déchargement après chaque réponse), ce qui peut accroître le coût des appels répétés. Aucune accélération garantie sans mesures.

### Comportement de Kwipi pendant une consultation facultative (PLAN, **pas codé sur robot**)

Un futur Advisor Qwen PC doit fonctionner **hors de la boucle motrice** : envoi rare et autorisé après rappel local, **sans attendre synchroniquement** dans `robotd` ni interrompre ses gardes 50 Hz. La boucle légère du robot continue à percevoir, à suivre les règles de sûreté OEM, à faire une **inaction sûre**, à se reposer ou, seulement si déjà autorisé et sûr, à exécuter des routines OEM locales non liées à l'hypothèse attendue. Aucun geste « je réfléchis » n'est obligatoire ; des indices discrets et non répétitifs peuvent être envisagés après inventaire OEM, jamais une animation motrice concurrente. `stop` et les limites sol, obstacle, chaleur, batterie, fraîcheur et priorité à la sécurité priment sur toute requête Qwen. À la réponse, **vérifier identifiant, consentement, fraîcheur de scène, délai et schéma** ; ignorer les réponses tardives, les scènes déplacées, l'absence de PC et toute proposition motrice. Les sorties acceptées sont des **hypothèses**, non des observations ou souvenirs causaux. Mesurer hors robot délai, abandons, interruption, continuité des routines et consommation avant un éventuel portage.

**Statut :** résultats natifs rapportés par l'opérateur ; ce lot ne contient que de la documentation et des critères d'essai. Aucun nouveau modèle, comportement moteur, état d'attente déployé, consultation asynchrone sur robot ou test RK3566 livré.
