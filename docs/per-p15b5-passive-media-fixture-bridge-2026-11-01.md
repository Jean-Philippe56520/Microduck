# P15-B5 — Raccord passif de métadonnées `mediad` au cycle PC existant (1er novembre 2026)

## Porte préalable — décision fixée avant tout test ou code

**Fonction utile à démontrer.** Le **même processus** Kwipi P15-B1 doit pouvoir recevoir, à côté de son unique source cognitive MOCK F1-B, une notification locale **au format exact `media.detections` de P15-B4**, l'afficher uniquement en compteurs anonymes de diagnostic et continuer son cycle de repos/arrêt. **Aucune détection unilatérale ne devient une catégorie, une preuve physique, une intention d'action, un événement SQLite ou un résultat causal.** Un événement manquant/erroné ne bloque pas la mémoire fictive déjà autorisée.

**Écart attesté** : `P15-B4/#242@d1dad594a390006878d89d790989070fb43edb9b` expose un **producteur OEM opt-in candidat** sur Unix `/run/mediad/kwipi/detections.sock`, 9/9 tests Rust natifs, binaire `mediad` construit et 10/10 tests d'overlay, [CI B4 #41251142202](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41251142202) verte. `microduck_companion/passive_media_router.py` sait déjà analyser ce JSON et rejette les scores illégitimes, mais ne lit pas de socket. `passive_fixture_runtime.py` P15-B1 lance un processus fini et `PassiveCycleSupervisor` impose strictement `FixtureUnixReader` et **une seule** `ExperienceMemory` ; l'interface de détections OEM n'est donc pas consommable par le processus. L'ancien `/run/mediad/media.sock` sert `hello/media.frame`, **jamais** `media.detections`.

**État vérifié avant essai** : main `eab73e9435dbd217c0e50b9e9ecfd59730a6e068` ; #230, #231, #235, #238, #239, #240, #241 et #242 **ouvertes en brouillon, non fusionnées**. #97–99 fusionnées. Les cinq CI #242 du dernier SHA fonctionnel sont vertes. Gitlinks inchangés `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Yocto constructeur `microduck_yocto@1ee58387810cebb67ae0d634c351d95024483bce`, P16 WIC/ZST déjà produits et vérifiés ; RAUC DEV non signé, **ne pas reconstruire**. PR B5 doit être empilée sur #242, non fusionnée sans ses dépendances.

### Comparateur réutiliser / adapter / créer

| Élément réel | Choix | Limite et raison |
|---|---|---|
| `mediad::Detector.sightings` et `detect::notification` P15-B4 | **Réutiliser sans toucher** ; source OEM scratch inchangée | Un seul détecteur OEM, pas de timestamp/seq de capture ; mono-classe uniquement |
| `parse_oem_shape_notification` F3-C et `_connect_unix/_recv_line` F1-B | **Réutiliser octet pour octet** | Le parseur accepte aussi `media.video`, que le lecteur B5 devra refuser |
| `PassiveCycleSupervisor`, `AutonomyBrain`, `PassiveObservationJournal`, `ExperienceMemory`, `PassiveLearning` | **Réutiliser sans modifier** | Autorisent seulement les snapshots `mock`, ne pas y injecter de notification OEM |
| `passive_fixture_runtime.py` P15-B1 | **Adapter au minimum** : deuxième lecture **facultative**, non cognitive, dans sa boucle déjà bornée et sa gestion d'arrêt existante | Mode `--mock-only` toujours obligatoire ; source média explicite **fixture seulement** |
| Lecteur local de la notification mono-classe sur socket Unix de fixture | **Créer un seul module borné** utilisant le transport et parseur existants | Ne jamais accepter d'adresses OEM `/run`, de données caméra, de RPC, de catégories ni de permissions moteur |
| Nouveau service/daemon/bus/SQLite/ONNX/moteur/OEM/Yocto | **Refuser** | Aucun gain de P15-B5, ni accès OEM sûr prouvé |

### Risques, faits et blocages

- `/run/mediad/kwipi/` est **`0700` pour UID `mediad`** et le socket B4 `0600`. **L'ACL du seul socket ne suffirait pas : l'utilisateur `kwipi` doit aussi avoir le droit de traverser le répertoire privé.** Le groupe `robot` ouvrirait `robotd.sock` ; interdiction de l'ajouter. Aucun changement d'ACL/UID sur le constructeur, cible, WIC ou la machine opérateur sans revue OEM distincte ; une ACL après rebind ne persiste pas naturellement.
- `Sighting` / `media.detections` ne transportent **ni horodatage de capture ni séquence**. Réception locale ≠ fraîcheur réelle ; ne pas prétendre gérer duplicats physiques ou déduire `faux`/absence d'objet d'un silence. `took_ms` est le temps d'inférence, **pas** l'âge de l'image. Les boîtes représentent des **hypothèses Microduck** sans classification multi-objets ; scores non calibrés (peuvent dépasser 1).
- La sortie locale de P15-B4 n'est pas installée, l'identité `DUCK_REVISION` compilée en Yocto reste **inconnue**, l'accès UID indépendant n'est pas résolu. Aucun mode `--oem` de lecture n'est ajouté dans ce lot. Toute route `/run`, `/dev`, `/proc`, `/sys` ou via un lien à partir du CLI **reste bloquée avant l'ouverture de SQLite**.
- Les lectures fixture peuvent être bloquantes **au plus 0,4 s** pour la réception d'une ligne de **4096 octets maximum** ; `MIN_INTERVAL=0,5 s` et **1 connexion par cycle**, arrêt coopératif dans les mêmes limites de P15-B1. Ne jamais envoyer de requête (le serveur B4 la fermerait). Ne conserver que des **compteurs de statut** éphémères ; pas de rectangle, image, identité, trace texte, persistance ou seconde base.

### Tests positifs fixés AVANT implémentation

1. Sur **vrai socket Unix de fixture Linux**, émettre **une notification OEM-shaped `media.detections`** avec score brut >1 : le lecteur en reçoit une seule, la qualifie `shape_only_untrusted`, et conserve `category=unknown`, `physical_verified=False`, sans écriture et sans envoyer d'octets. Cas **zéro boîte** distinct de « flux absent ».
2. Avec P15-B1 : processus **unique** lisant d'abord la fixture cognitive MOCK habituelle, puis la fixture média, **une seule SQLite ExperienceMemory**, mémoire ne contient **que** la catégorie MOCK autorisée. Compteurs média séparés, aucun effet sur `source_events_accepted`, `stored_observations` ou le choix du cerveau. Une fixture média valide, sans source cognitive, **0 catégorie et 0 écriture**.
3. Exécuter la CLI avec `--mock-only` et chemin média fixture explicitement fourni : fin après 1..16 cycles, rapports anonymes, sans octets image/voix/rectangle persistés ; `SIGTERM`/stop avant lecture => aucun accès supplémentaire ; relance n'invente pas d'événement historique.
4. Vérifier dans la CI Python générale P15A/B3/N1 et P15-B4 inchangés ; gitlinks inchangés. Pas de workflow GitHub nouveau si les existants suffisent.

### Tests négatifs fixés AVANT implémentation

- `media.video`, `media.frame`, `robot.do/move`, `media.region_candidates`, JSON dupliqué/NaN, boîtes invalides, longueur excessive, plusieurs lignes dans un seul tampon, silence/déconnexion/lenteur, chemin lien/répertoire noyau, mauvais mode CLI, paramètre non borné ⇒ **aucune détection vérifiée, aucune catégorie, aucune écriture** ; si source indisponible : retour `unavailable_or_invalid` et poursuite du cycle existant.
- Détecteur désactivé / zéro notification ou socket inaccessible ⇒ inaction sans supposer « environnement vide ». Redémarrage de la CLI => pas de reprise des dernières boîtes.
- Pas de déverrouillage des moteurs, pas de `robotctl`, `media.frame`, `mediad` réel, `uid=mediad`, `robot`, ACL ni Qwen. Pas de capture, ni nouvelle base.

### Critère de passage et arrêt (préfixés)

**PASS `test_logiciel_seul`** uniquement si tests de lecture Unix, invalides, quotas, cycle unique, séparation SQLite, CLI/arrêt + suite Python, P15A/B3/N1 et P15-B4 existants sont verts sur le SHA final, sans modifier les fichiers protégés P14A/P15A. **STOP** si un événement OEM-shaped devient `source=sensor` ou une catégorie mémorisée, si UID `robot` est nécessaire, si dupliquer un processus/capture/mémoire est requis, ou si la CI échoue. Repli : retirer uniquement l'adaptateur fixture, son option et tests ; conserver B4 et tous gitlinks inchangés. **Accès OEM matériel et intégration réellement déployable : EN ATTENTE** de revue explicite des ACL dossier + socket après chaque bind, identité compilée, horodatage/seq capteur et mesures RK3566/robotd 50 Hz. Aucune mise à niveau constructeur ou service autonome dans ce lot.


## Résultats CI réellement observés — 1er novembre 2026

**Décision : `test_logiciel_seul` (PASS PC, STOP accès OEM réel).** PR [#243](https://github.com/Jean-Philippe56520/Microduck/pull/243) empilée en brouillon sur #242. Le SHA de code/documentation `8de528b7f1971c5d636529e4d5a2b7e989eb8a22` a exécuté [Python companion tests #41252539832](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41252539832) : **2 054 tests exécutés, dont 30 ignorés (2 024 réussis)**, soit **15 nouveaux tests spécifiques B5** en plus des 2 039 déjà validés sur B4 ; négatifs `/run`, RPC, media.video/region, JSON invalide/large, inaction, SIGTERM, processus + SQLite uniques et aucune écriture de données média. [P15A #41252539697](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41252539697), [P15-B3 #41252539649](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41252539649) et [N1 #41252539687](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41252539687) sont verts sur ce SHA. P15-B4 natif reste [vert au SHA #242](https://github.com/Jean-Philippe56520/Microduck/actions/runs/41251142202), **pas recompilé ni déployé ici**. Aucun sous-module, caméra, `robotd`, portage Yocto/WIC, ACL, service, modèle ou seconde SQLite n'a été modifié.

**Limite de résultat :** la CI vérifie de vrais sockets Unix de **fixtures**, pas le `mediad` réel ni une source de catégorie fiable. Le lecteur B5 refuse explicitement le chemin OEM ; les boîtes sont des hypothèses mono-classe et ne déclenchent ni catégorisation, ni apprentissage, ni mouvement. Une ACL de traversée du parent `0700` ainsi qu'un accès au socket `0600` à chaque bind, une identité binaire vérifiée, une horodatation de capture, des mesures NPU/CPU/RSS/température et une revue OEM restent nécessaires avant tout déploiement. La CI verte ne lève pas ces portes.
