# R2-B+1 — Préparateur audio initial, puis test sur prises réelles

**26 octobre 2026 — lot indépendant de R2-B+2, non lancé.**
**État historique de la PR #59 (préparation) :** code et tests WAV synthétiques, **aucun corpus réel exécuté à cette date de clôture du lot**. **Depuis la PR #60 :** [l'évaluation de 34 extraits réels sur six machines](r2b1-real-audio-results-2026-10-26.md) a été exécutée ; **M1-B échoue sur le test (0/10 connues correctement reconnues, 1 fausse fusion)**. Le présent fichier décrit surtout la préparation et ses garde-fous, pas le résultat final.

## Sources internes, décisions et absence de doublon

Inspectés : [plan principal](plan-action.md), [suite R2](r2-follow-up-execution-plan-2026-10-26.md), [évaluateur existant](../microduck_companion/r2b_independent_capture_eval.py), [empreintes M1-B2](../microduck_companion/m1b2_host_embeddings.py), [mémoire M1-B](../microduck_companion/multiview_pattern_memory.py), [protocole de réutilisation](development-reuse-protocol.md) et [registre communautaire](community-reference-registry-2026-10-26.md).

- **Réutiliser :** validateur de manifeste et SHA-256, lecteur WAV PCM16 16 kHz mono 1 seconde, extracteurs M1-B et option YAMNet, scores et seuils figés sur validation, calcul du rejet inconnu, fonction de benchmark R2-B.
- **Adapter :** ajouter au rapport un décompte par source **anonyme** (pas de labels personnels).
- **Créer seulement la pièce manquante :** [préparateur local ToyADMOS](../microduck_companion/r2b1_toyadmos_local.py), qui produit des clips privés et manifeste compatible à partir de vrais fichiers originaux déjà obtenus et examinés.
- **Ne pas créer :** second lecteur micro, nouvelle SQLite, modèle, transport Qwen, pilote, commande moteur, import de Quacksat ou microduck-twin. Ceux-ci ne règlent pas l'identité d'une source sonore familière.

## Corpus sélectionné pour le prochain essai réel

[Zenodo : DCASE 2020 Task 2 Development, DOI 10.5281/zenodo.3678171](https://zenodo.org/records/3678171), assemblage officiel de ToyADMOS et MIMII.

- Chaque **Machine ID** désigne une machine individuelle d'un type donné. Les clips **ToyADMOS IND** couvrent chacun une opération complète démarrage → arrêt, enregistrée réellement ; il ne s'agit pas de décalages temporels artificiels d'un seul fichier.
- **Licence vérifiée sur la fiche officielle DCASE : CC BY-NC-SA 4.0**, avec obligations d'attribution, d'utilisation non commerciale et de partage dans les mêmes conditions pour d'éventuelles adaptations redistribuées. **Aucun enregistrement, extrait, nom privé ou poids n'est committé.**
- Pilotage minimal : deux archives **ToyCar (1,8 Go)** et **ToyConveyor (1,9 Go)**. Le préparateur choisit deux machines inscrites et une inconnue *du même type* pour la validation, puis deux inscrites et une inconnue du second type pour le test. Total : six machines différentes, dix clips.
- La provenance officielle autorise à parler d'**opérations et fichiers distincts**, **pas** de prises réalisées à des dates/sessions différentes ni de robustesse domestique. Le champ session_id du manifeste représente ici un **identifiant de fichier enregistré**, pas une vraie session datée. L'outil marque cette limite.
- Les types changent entre validation et test : cela interdit de conclure à une bonne généralisation de la reconnaissance sonore domestique avec un pilote aussi réduit.

Pour vérification des archives officielles, Zenodo publie les MD5 suivants : **ToyCar** 4dec75ca8d9f666aa9e4c1894a740501 ; **ToyConveyor** 03b6aa1bfd09a39d53af0ba39f71fa91. Le MD5 publié sert à contrôler l'intégrité du téléchargement, pas à certifier les enregistrements indépendants.

**Autres pistes non retenues pour ce pilote :** un fichier MIMII peut être un segment d'une même session continue ; RWCP est réservé à la recherche/développement ; des sons ESC-50/Freesound ne démontrent pas automatiquement la répétition d'une même machine physique.

## Reproduction sur un PC qui dispose des médias autorisés

Télécharger et extraire **manuellement** les deux ZIP Zenodo **hors du dépôt Git**, de sorte que le chemin privé contienne les répertoires dev_data/ToyCar/train, dev_data/ToyCar/test, dev_data/ToyConveyor/train et dev_data/ToyConveyor/test.

Les dossiers de destination doivent être nouveaux, privés et eux aussi **hors du dépôt**. Après revue effective des droits et de l'origine, exécuter :

~~~sh
python -m microduck_companion.r2b1_toyadmos_local \
  --dataset-root /chemin/prive/dcase \
  --audio-root /chemin/prive/r2b1-clips \
  --audio-manifest /chemin/prive/r2b1-manifest.json \
  --noncommercial-license-reviewed \
  --independent-operations-reviewed

python -m microduck_companion.r2b_independent_capture_eval \
  --locally-approved-research \
  --audio-manifest /chemin/prive/r2b1-manifest.json \
  --audio-root /chemin/prive/r2b1-clips
~~~

Le préparateur refuse les droits/prises non examinés, liens symboliques, médias sous Git, doublons, formats incorrects, cohortes insuffisantes et sorties déjà présentes. Il découpe **une seconde centrale fixe** par fichier original (pas d'optimisation a posteriori), garde les SHA-256 d'origine dans un dossier local avec provenance et génère le manifeste R2-B. Le benchmark existant compare la signature M1-B et, si demandé avec poids/licence contrôlés, le descripteur YAMNet sur CPU. Pas de nouvelle mémoire ou modèle.

## Tests et décision d'arrêt

[Tests R2-B+1](../tests/test_r2b1_toyadmos_local.py) : WAV **purement synthétiques** (sans signification acoustique réelle) pour prouver validateur, cohortes source séparées, SHA, faux doublons, formats rejetés, confidentialité de chemins, absence de mouvement et réutilisation de l'évaluateur. Ils n'établissent aucune performance de reconnaissance réelle.

**Blocage initial, PR #59 uniquement :** le runtime de préparation n'avait pas les fichiers Zenodo. **Ce blocage a été levé en PR #60** par lecture HTTP Range dans GitHub Actions ; voir le [rapport de résultats réels](r2b1-real-audio-results-2026-10-26.md). Il reste interdit de promouvoir un modèle audio sur cette base.

**Décision révisée :** outillage préparatoire testé et essai réel exécuté dans la PR #60 ; **M1-B ne satisfait pas le rappel des sons familiers et commet une fausse fusion**. Aucun modèle n'est retenu. R2-B+2 reste strictement **non démarré** sans nouveau Go.
