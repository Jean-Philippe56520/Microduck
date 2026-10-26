# R1 — Contrat passif de métadonnées OEM sur fixtures

**26 octobre 2026 · implémentation logicielle hors ligne uniquement · aucun robot.**
Suivant [l'audit de réutilisation R0](oem-reuse-audit-2026-10-26.md), ce sous-lot **n'ajoute pas un décodeur, un pilote, un classificateur, un contrôleur moteur, un modèle ou une base SQLite**. Il réutilise les modules déjà testés pour inspecter seulement des **formats fictifs ressemblant aux formats OEM**, avec une sortie commune strictement passive.

## 1. Pourquoi cette couche est utile

Les interfaces constructeur et leurs frontières ne sont pas interchangeables :

- **WebRTC `media.video` / `media.detections`** : notifications de contrôle de session côté client WebRTC. Elles **ne sont pas** diffusées par le socket Unix `/run/mediad/media.sock`. Le détecteur OEM ne voit que les **autres Microducks** ; son `score` brut n'est pas une probabilité calibrée.
- **Socket Unix `media.frame`** : réponse JSON-RPC d'en-tête puis pixels **UYVY** bruts. Notre prototype ne demande **aucune** image ; les tests n'utilisent que l'en-tête fictif, son horodatage déclaré et le nombre d'octets attendu. Le simple en-tête ne valide pas la provenance des images.
- **Socket ToF `tof.stream`** : notification `tof.frame` 8×8 déjà interprétable avec `sim_ipc.parse_depth` ; le signal frontal ne prouve ni sol praticable, ni escalier évité. Le nouveau module ne conserve **pas** les 64 distances, seulement `tof_zone_count=64` et l'état de contrôle.
- **Audio :** le worker constructeur `pet-detect` réunit sentinelle ambiante/voix et son de caresse. Nous réutilisons **uniquement** `MockAudioCueRouter` et ses **étiquettes synthétiques** ; ces étiquettes ne sont pas des événements OEM authentiques, des mots-clés reconnus ou des paroles transcrites.

Le problème R1 est de fournir un **reçu borné sans changer le niveau de confiance** : un message qui ressemble au constructeur reste une hypothèse de forme, jamais un capteur authentifié.

## 2. Reprise effective de code existant

| Flux de test | Validateur réutilisé, sans nouvelle implémentation de protocole | Sortie |
| --- | --- | --- |
| WebRTC factice | `passive_media_router.parse_oem_shape_notification` (F3-C) | Nombre de boîtes « canard candidat » ; statut `metadata_unverified` / `duck_candidates_unverified` |
| En-tête de trame caméra factice | `oem_frame_preflight.parse_mock_frame_header` (F3-E) | Octets UYVY **attendus**, ancienneté déclarée, sans pixels |
| Trame ToF factice | `sim_ipc.parse_depth` (simulateur officiel) | Nombre de zones, séquence et fraîcheur de **réception locale fictive** |
| Signal sonore factice | `passive_media_router.MockAudioCueRouter` (F3-C) | Métadonnée valide/invalide, jamais transcription |
| Cloison de décision / mémoire | `passive_sources.PassiveRead`, `perception.PerceptionSnapshot`, `AutonomyBrain.propose_passive`, `PassiveObservationJournal` (F1/F2) | Un reçu **non-ok**, sans événement ; aucune catégorie écrite en SQLite et intention `idle` uniquement |

La nouveauté est seulement `microduck_companion/oem_passive_fixture.py` : `OEMFixtureInspector` et `OEMFixtureMetadata`, **sans socket ni I/O**.

## 3. Contrat de sécurité

Le reçu exposé est limité à : type de voie, statut, instant de réception local, base de temps déclarée, âge éventuel, taille JSON, nombre de boîtes/éléments, numéro de séquence et latence annoncée du détecteur. Il n'expose **ni rectangles, ni identités, ni son, ni pixel, ni distance ToF brute, ni texte libre**. Ces contenus de test existent uniquement dans les arguments d'entrée et ne sont pas enregistrés.

Les invariants sont les suivants :

1. `source_authenticated=false`, `motion_authorized=false`, `motor_commands_issued=0`, `raw_media_stored_bytes=0`, `pc_requests_issued=0`, `category="unknown"` **pour tous les résultats**, y compris les résultats valides.
2. `to_passive_read()` réutilise les structures F1/F2 mais produit **toujours** une lecture `status != "ok"` et une `PerceptionSnapshot(environment="mock", events=())`. Même une trame de forme valide ne peut donc devenir `object_label`, `sound_label`, `safe_area`, `floor_clear` ou mouvement.
3. Données incorrectes, inconnues, trop volumineuses, trames trop vieilles/futures, séquences ToF répétées, horloge de réception régressant : refus, sortie sans catégorie.
4. `media.video` et `media.detections` n'ont ici **pas d'horodatage de capture authentifié** exploitable : le `now` reçu par le banc ne certifie pas leur fraîcheur.
5. L'en-tête caméra possède un temps mural **déclaré** : sans preuve de synchronisation et d'origine, il ne prouve pas que la caméra physique vient de prendre une photo. La tolérance de temps futur de F3-E est **refusée** par R1.
6. Les sons `keyword_stop` et `keyword_viens` sont **seulement des fixtures** ; jamais des commandes d'arrêt ni une permission de bouger.
7. Aucune ouverture de `/run/mediad/media.sock`, `robotd`, `tofd`, WebRTC ou réseau ; aucun modèle/PC, aucune base de souvenirs, aucune commande ou animation.

**Ces vérifications de schéma ne sont pas une authentification de capteur.** Une future lecture physique devra posséder une vraie preuve de provenance, gérer les autorisations des flux et la confidentialité. Ne pas contourner le refus de `to_passive_read()` pour aller plus vite.

## 4. Vérifications et exemples

Les tests `tests/test_oem_passive_fixture.py` exercent des fixtures positives et adversariales pour quatre voies : faux droit au mouvement, géométrie erronée, image trop grosse, source fausse, dépassement de durée, répétition de séquence et changement d'horloge, arrêt vocal fictif, refus de persistance SQLite et repli `idle` du cerveau existant.

Exécution :

```bash
python -m unittest discover -s tests -p 'test_oem_passive_fixture.py' -v
python -m unittest discover -s tests -v
```

**État de preuve :** R1 codé et tests hors ligne à consigner avec un lien de CI dans la PR ; aucun test physique, aucune donnée réelle et aucune interaction constructeur.

## 5. Suite en lots distincts

**R2** : corpus de plusieurs prises *indépendantes* d'un même objet ou événement sonore, négatifs difficiles, seuils validés et `unknown`, mesure RSS/CPU/SQLite sur PC. **R3** : compatibilité avec M9 si Pollen publie une véritable interface de cerveau autonome, sans arbitre moteur parallèle. **R4** : Qwen facultatif seulement sous opt-in et quota. **R5** : audit matériel et tests physiques conditionnels, sans supposer les ressources libres du RK3566.

La [règle de développement « réutiliser avant de créer »](reuse-first-protocol.md) s'applique à chaque lot.
