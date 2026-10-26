# M1-A — Souvenirs visuels et sonores compacts, prototype sur données synthétiques

**26 octobre 2026 — nouveau chantier M (mémoire multimodale), [PR #49](https://github.com/Jean-Philippe56520/Microduck/pull/49) en revue, indépendant de F7 validation physique.** Ce lot code une première chaîne **pixels/audio bruts de fixtures → empreintes courtes → comparaison prudente → observation regroupée dans la même SQLite → indication facultative de nouveauté**, sans modèle externe, API, microphone, caméra, motricité ni son émis.

## Besoin auquel répond le lot

L'objectif est de ne pas enregistrer dix photos de la même peluche, ni dix fichiers audio d'un bruit familier. Chaque nouvelle observation est temporairement convertie en **caractéristiques de signal** ; les fichiers médias ne sont **jamais** persistés par ce module. La base conserve l'empreinte, la modalité, un éventuel **libellé général déclaré dans la fixture**, une date de première/dernière rencontre et un compteur. La rencontre suivante actualise le compteur **si et seulement si** une similitude suffisante est trouvée, sans générer une nouvelle photo ni un nouvel enregistrement.

**État réel de M1-A :** la formule fonctionne sur pixels et PCM **synthétiques fabriqués par le test**. Elle ne reconnaît **ni une vraie peluche, ni un chat, ni un chien, ni une personne**, ni une porte ou un aboiement en environnement domestique. Un « même motif » n'est pas la preuve du même objet physique ou de la même source sonore. Aucune identification individuelle (Kitty, Nessquick, Malo) n'est entreprise.

## Algorithmes légers réellement codés

| Chemin | Format d'entrée strict, en RAM | Caractéristiques sauvegardables | Portée et limites |
| --- | --- | --- | --- |
| Visuel `image_fingerprint` | **32 × 32** pixels en niveaux de gris, 1 024 octets | **64 octets** : moyenne de 8 × 8 blocs, normalisée par contraste pour supporter un décalage global simple de luminosité | Des changements d'angle, d'échelle, d'objet, d'occlusion et des reflets peuvent changer l'empreinte ou créer des collisions |
| Son `audio_fingerprint` | Mono **PCM 16 bits little-endian, 8 kHz**, de 512 à 4 096 échantillons, multiple de 128 | **16 octets** : 12 bandes grossières d'énergie fréquentielle sur blocs + 4 caractéristiques temporelles normalisées | C'est de l'analyse de signal. **Aucune** classification « miaulement », « aboiement » ou reconnaissance vocale n'est exécutée |

Les octets bruts sont abandonnés à la sortie de l'appel ; pas de table contenant des pixels, formes d'onde ou transcriptions. Les empreintes sont de simples **mesures d'apparence/son**, pas des représentations apprises par un réseau neuronal.

La comparaison est une similarité moyenne sur les composantes quantifiées, **pas une probabilité de confiance** ; seuil initial visuel **0,94** et audio **0,93** à **évaluer**. Si deux empreintes enregistrées sont trop proches (écart inférieur à **0,025**), le système retourne `ambiguous_unverified` et **n'agrège pas** de souvenir. Une contradiction de catégories déclarées, comme `dog` et `cat` sur la même empreinte, est également marquée ambiguë.

## Politique SQLite et stockage

`CompactPatternMemory` réutilise exactement la **connexion SQLite `ExperienceMemory.conn` existante**. Il ajoute `m1a_compact_patterns` (un index de récence), et n'altère pas les autres tables F1 à F6.

- **256 empreintes actives maximum au total**, visuel + audio, et **180 jours sans rencontre** avant expiration. Lorsqu'il n'y a plus de place, l'entrée la moins récemment observée est supprimée pour une nouvelle signature.
- Les rencontres répétées **augmentent un compteur** plafonné à **2 147 483 647** et actualisent la dernière date ; pas de copie de l'ancien son ni de la photo.
- Deux motifs fictifs (une image et un son) occupent **80 octets de champs `fingerprint`**, hors index, colonnes, pages SQLite, journal, autres tables et espace disque libre. **256 empreintes ne constituent PAS un plafond du fichier SQLite en octets** : il faudra ensuite mesurer/limiter les fichiers `db`, WAL et le comportement de réallocation sur le véritable système persistant.
- `ExperienceMemory` utilise `:memory:` par défaut ; la démonstration CI avec deux processus autorise **un chemin temporaire explicite** dans `RUNNER_TEMP`. Ce n'est **pas** une procédure d'installation sur `/var/lib/robot`, dont le montage reste à vérifier au titre de F6-A/F6-D.
- Les métadonnées sont marquées `synthetic_fixture_claim`. Une étiquette `cat` ou `dog` fournie par un test ne devient pas une observation authentifiée. Une sortie contient toujours `category_verified=False`, `same_individual_verified=False` et `physical_robot_validated=False`.
- **Confidentialité :** M1-A refuse d'enregistrer une empreinte visuelle étiquetée `person` ou une empreinte sonore étiquetée `speech`. Cela **ne remplace pas une vraie détection de personne/parole** sur un média inconnu : tant qu'une chaîne de filtrage privée, fiable et consentie n'est pas validée, **ne brancher aucune caméra ou microphone réel**. Une empreinte n'est pas intrinsèquement anonyme et doit rester hors GitHub.

## Curiosité et PC facultatif

Sur un événement nouveau/ambigu, le résultat peut porter `pc_review_suggested=True` **seulement** si l'exemple déclare explicitement `pc_opt_in=True`, si la curiosité d'entrée est au moins **0,7**, et si la catégorie générique est `unknown` / `object` / `ambient`. Pour un motif familier, l'indication est `False`.

Cette indication **n'envoie aucune requête** et n'autorise aucun transfert de photo ou de son ; `network_requests=0` est permanent dans M1-A. Le client F5-B/C existant ne reçoit toujours pas de vrais médias. Une connexion ultérieure devra obtenir l'autorisation de partage du média courant, appliquer les quotas F5-C, protéger les personnes et voix, refuser les réponses périmées et traiter Qwen comme hypothèse **non vérifiée**. Le PC reste facultatif et n'autorise jamais de mouvement.

## Tests reproductibles et démonstration observable

```bash
python -m unittest discover -s tests -v
python -m compileall -q microduck_companion tests

# En créant un chemin de test LOCAL privé et temporaire :
python -m microduck_companion.m1a_multimodal_demo --database /tmp/m1a-fixture.sqlite3 --session first
python -m microduck_companion.m1a_multimodal_demo --database /tmp/m1a-fixture.sqlite3 --session second
```

Dans la première session, le logiciel reçoit **un objet fictif** et **une tonalité pure de 440 Hz**, tous deux nouveaux. Dans la seconde, il les revoit/reçoit **neuf fois chacun** (luminosité et amplitude modifiées). Résultat de succès attendu : **2 lignes**, **10 rencontres par ligne**, **80 octets d'empreintes**, **aucun média stocké**, **0 consultation PC**, **0 commande moteur**. Les deux sessions sont deux **processus Python indépendants** partageant seulement un fichier SQLite de test.

Les tests couvrent la déduplication, différences d'apparence et de fréquence, conflits et ambiguïtés, lumière/volume, silence, audio tronqué, refus de personnes/parole, étiquettes et horodatages invalides, limite 256, expiration et réouverture SQLite. La réussite sur des fixtures **n'établit aucune précision** sur des animaux, objets ou bruits réels.

### Résultat effectivement obtenu en CI hôte

La [CI #40297726482](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40297726482) a réussi : **898 tests Python**, **4 tests Rust** et les deux lancements indépendants de `m1a_multimodal_demo`. Premier processus : `pattern_count=2`, compteur 1, `fingerprint_blob_bytes_total=80`, deux **suggestions de revue sans requête**. Second processus : `pattern_count=2`, compteur **10 par motif**, `fingerprint_blob_bytes_total=80`, **0 suggestion supplémentaire**, aucune photo ni son enregistré et zéro moteur/réseau. Ce résultat porte sur des données de synthèse, pas sur la précision réelle de reconnaissance ni sur la taille du fichier SQLite complet.

## Suite : M1-B, puis M1-C

**M1-B — Évaluation scientifique sur médias autorisés :** images et sons réels publics ou consentis, séparation stricte entraînement/test, variété d'angles/distances/bruits, faux positifs de « même objet/son », taux de rejet et consommation de CPU/RSS hôte. Comparer ce prototype artisanal avec de **petits embeddings** de modèle publiquement licencié, en conservant « inconnu » si la marge de décision est insuffisante. Le modèle final doit être évalué sur le vrai matériel et optimisé pour ses ressources, **sans supposer une accélération NPU**.

**M1-C — Déclenchement PC parcimonieux :** seulement après un vrai filtre de sécurité des médias, autorisation explicite, quota et mesure des modèles Qwen effectivement disponibles. Éviter l'envoi automatique d'images de personnes, de voix et de conversations.

**Cette nouvelle phase n'est pas F7 :** aucune phase F7 de validation physique n'a été commencée.
