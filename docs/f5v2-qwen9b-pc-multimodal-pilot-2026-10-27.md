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
- **Lanceur Windows** : apres un seul `git pull --ff-only` dans `C:\Users\Jp\Microduck-Qwen9B`, ouvrir `TESTER_KWIPI.cmd` par double clic ; le lanceur PowerShell (execution locale `RemoteSigned` sans changement persistant de politique) detecte `C:\Users\Jp\.venv-qwen9b\Scripts\python.exe` ou l'environnement venv du depot, controle `127.0.0.1:11435/api/tags` et la presence de `qwen3.5:9b`, propose une boite de selection, refuse les images >2 Mo et **demande de taper OUI** apres examen et autorisation de l'unique photo. Il n'installe pas Git/Ollama/modeles et ne demarre pas automatiquement de serveur GPU. L'image reste sur le PC ; Ollama la recoit exclusivement via loopback. Aucun media ni souvenir ni texte de Qwen n'est envoye a GitHub.
- **CLI reproductible** : `python -m microduck_companion.qwen9b_advisor_v2 --image <chemin> --ollama-port 11435 --mode simple --timeout 180 --authorize-image --reviewed-no-private-subjects` apres revue de la photo. Les deux indicateurs signifient une revue reellement faite, pas une option a automatiser pour des dossiers entiers.
- **Interpretation** : `status=unverified` et `visual_observation` = hypothese structuree acceptee, pas detection averee ; `status=rejected` et `diagnostic_reason` = aucun resultat valide. Un disque rouge dessine devrait permettre l'abstention ; seule une evaluation sur photos d'objets varies, independamment annotes, pourra etablir precision, confusions et generalisation. Ne pas deduire la qualite d'un seul exemple.

**Niveau de preuve :** pilote code et tests Python sur faux Ollama (25/25 en local) ; verifications Linux de la syntaxe Python ; fichiers PowerShell / CMD controles statiquement, mais **non executes en Windows CI**. Aucun nouveau test reel du mode `simple`, aucune mesure de GPU/RSS avec celui-ci, aucune validation de capteurs, de motorisation ou du robot non recu. CI GitHub du commit de ce lot a verifier. Prochaine etape : ouvrir le lanceur Windows avec l'image synthetique deja autorisee, consigner uniquement `status`, `visual_observation`, `latency_s` et diagnostics ; puis vrais objets photographies avec consentement, en conservant le jeu Cat-A2b prive hors GitHub.

## Environnement virtuel de test GitHub automatisé

Le workflow existant `.github/workflows/python-tests.yml` installe désormais un `venv` Python **temporaire** par GitHub Actions run (`$RUNNER_TEMP/microduck-companion-venv`), avec Python 3.11 / Pillow 11.3.0. Il vérifie l'isolation, exécute tous les tests et démos **sur fixtures/serveurs fictifs** puis GitHub détruit l'ordinateur temporaire. Les branches avec PR ne déclenchent plus à la fois `push` et `pull_request`, pour éviter la duplication de minutes ; `main` reste testé à chaque push. Le code n'ajoute ni fichier `.venv` dans Git, ni image de l'opérateur, ni poids de modèle. Aucun travail permanent ne tourne à l'arrière-plan.

Cet environnement ne peut **pas** joindre le `127.0.0.1:11435` du Windows de l'opérateur, ni utiliser sa Radeon 860M, ses images locales ou le robot absent. La validation sur vrai Qwen reste un essai local explicite via `TESTER_KWIPI.cmd`, après autorisation et choix d'une image. Pas de runner auto-heberge Windows public propose sans audit de sécurité : un runner de dépôt public permettrait une exécution de code non désirée avec accès aux fichiers de la machine.

Niveau de preuve : CI avec faux Ollama, pas d'inférence réelle ou de généralisation validée.