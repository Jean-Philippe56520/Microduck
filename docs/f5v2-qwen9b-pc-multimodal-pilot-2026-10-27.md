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