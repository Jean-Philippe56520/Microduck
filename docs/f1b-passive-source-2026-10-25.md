# F1-B — Adaptateur passif borné et vérification locale de mediad

**Date : 25 octobre 2026. État : fusionné dans `main` via [PR #25](https://github.com/Jean-Philippe56520/Microduck/pull/25), testé dans GitHub Actions sur service Unix entièrement fictif.** [315 tests Python réussis sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234054024) (295 existants + **20 nouveaux**). **Aucun Microduck physique ni mediad constructeur réellement lancé/testé. Aucun média brut, aucune image, aucun microphone, aucun modèle de vision ou audio. Aucune commande motrice.**

La [phase F1](plan-action.md) reste **en cours** : F1-A contrat de catégories est livré, F1-B livre seulement des **lectures fictives et un contrôle de disponibilité OEM**, F1-C devra mémoriser les découvertes en SQLite, puis F1-D fera la démonstration.

## Contrat et séparation de provenance

Deux voies **strictement séparées** sont exposées par `microduck_companion/passive_sources.py`.

### A. `FixtureUnixReader` — lecture du service fictif

- Connexion **Unix locale uniquement** à un socket fourni par le banc d'essai. La lecture d'une ligne JSON est bornée à **8192 octets**, le délai total à **3 s maximum**, l'âge d'une observation à **2 s maximum**, la fréquence d'appel à **2 lectures/s maximum** (intervalle minimal **0,5 s**), et le budget de `PerceptionEvent` à **64** entrées. Un dépassement échoue et **ne recycle aucune observation précédente**.
- Protocole par connexion : un objet `{"schema_version":1,"sequence":1,"sample_monotonic_s":...,"events":[...]}`. L'horloge monotone doit être celle du **même système**, les numéros de séquence doivent croître, la catégorie doit appartenir à la liste F1-A ; les identifiants de suivi sont éphémères et limités à la forme `track-...`. Une valeur `source`, `environment`, des `pixels`, `transcript`, `safe_area`, `floor_clear`, `robot.move`, etc. provoquent le refus.
- Le protocole est **fictif et propre à Companion**, pas une API officielle `mediad`. Même si un émetteur malveillant déclare « sensor » ou « robot », son message est rejeté ; toute observation acceptée est reconstruite explicitement avec `source="mock"` et `environment="mock"`. Elle ne peut pas valider une identité individuelle, une zone sûre ou une instruction de mouvement.
- `PassiveRead.status` distingue `ok`, `rate_limited`, `clock_reset`, `duplicate_or_out_of_order` et `unavailable_or_invalid`. **Seul `ok` peut fournir des événements.** Coupure, source absente, délai, séquence non croissante, événement ambigu et données invalides ne produisent pas de découverte fausse.

Exemple *fictif* accepté (horodatage monotone à remplacer par celui du processus local) :

```json
{"schema_version":1,"sequence":1,"sample_monotonic_s":100.0,"events":[{"kind":"object_label","category":"ball","track_id":"track-fixture-01","confidence":0.95,"ttl_s":1.0},{"kind":"sound_label","category":"knock","confidence":0.94,"ttl_s":1.0}]}
```

L'exemple n'est **pas** une observation réelle de caméra ou de microphone.

### B. `probe_official_mediad` — contrôle OEM « hello » seulement

À la révision constructeur épinglée `942e58e3aa6dbb28e7037203fff11866122c7567`, [`duck-ipc-proto/src/lib.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/duck-ipc-proto/src/lib.rs#L517-L538) définit le socket local `/run/mediad/media.sock`. [`mediad/src/frame.rs`](https://github.com/pollen-robotics/microduck/blob/942e58e3aa6dbb28e7037203fff11866122c7567/mediad/src/frame.rs#L122-L192) répond à `hello` sur ce socket, avant `media.frame`.

- Le probe **ne demande que `hello`** (JSON-RPC 2.0, ID 1). Aucune commande `media.frame`, aucun flux WebRTC, aucune capture, aucune lecture/écriture de média.
- Une identification `verified_for_pinned_oem=True` exigerait **ensemble** : chemin système officiel sans lien symbolique, propriétaire du socket et UID du processus pair Unix (`SO_PEERCRED` Linux) égal à l'utilisateur système `mediad`, API version 44 et révision exacte du code épinglé. Un socket temporaire de test **ne peut jamais** recevoir cette qualification, même avec un `hello` imitant le constructeur.
- Ce contrôle est **local et non cryptographique**, et ne démontre **ni présence d'une caméra réelle, ni fiabilité du détecteur, ni sécurité d'un port réseau WebRTC**. Une version OEM différente est volontairement refusée, à réexaminer manuellement et avec les sources correspondantes. `unverified_peer` et `unavailable_or_invalid` **ne fournissent aucune catégorie d'objet/son**.
- `media.detections` est une notification de boîtes sur un canal WebRTC ; les sources épinglées ne donnent pas de classes chien/chat/personne ou de flux Unix de catégories audio sur ce chemin. **Il n'existe pas à ce stade de connexion réelle de Companion à cette notification**. Ne jamais confondre cette sonde d'identité avec une détection.

## Tests exécutés en CI (données fictives exclusivement)

- 20 nouveaux tests `tests/test_passive_sources.py` : vraie connexion Unix vers un faux service, objet connu/inconnu, mot-clé `stop` sans action, imitation des sources `sensor`/`robot` refusée, `safe_area` et commandes rejetées, séquences en double ou régressives, limite de fréquence, panne puis reprise sans réutiliser de donnée, déconnexion, délai silencieux, trame surdimensionnée, socket remplacé par fichier/lien, faux `hello`, API/révision incorrecte, horloge, limites de confiance/TTL, JSON dupliqué et valeurs non finies.
- [Exécution Python complète sur `main`](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40234054024) : **315 tests réussis**, syntaxe Python vérifiée. Pas de commande moteur ni d'accès à une API payante.
- **Aucun test sur robot physique**, et les deux validations « vraie lecture de catégories depuis `mediad` » / « UID de service `mediad` sur système constructeur » restent **non réalisées**. Les fixtures de CI n'en constituent pas une preuve.

## Décision et prochain lot

**F1-B terminé uniquement comme adaptateur de fixtures + sonde read-only OEM.** Une véritable classification visuelle/audio demandera les modèles, les sources, les contrôles et les mesures **F3**, ainsi qu'un adaptateur OEM vérifié si possible. La faible mobilité P0/P1 reste un chantier suspendu.

**Prochaine PR, et une seule : F1-C**, journal SQLite léger des seules catégories passives et de leurs sources explicitement connues, avec reprise entre deux processus, conservation de `unknown`, bornes de rétention et séparation entre heure civile et horloge monotone. F1-C ne devra pas transformer une fixture `mock` en observation réelle, ni enregistrer de pixels ou de son brut.
