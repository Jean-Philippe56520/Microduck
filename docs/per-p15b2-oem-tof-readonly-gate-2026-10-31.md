# PER-P15-B2 — porte de provenance et observation ToF OEM ponctuelle (31 octobre 2026)

## Préenregistrement AVANT code et CI

**Objectif concret :** préparer, sans robot physique, la récupération *locale, hors ligne, ponctuelle et en lecture seule* d'un échantillon de profondeur OEM identifiable. P15-B1/#239 ne lit que `FixtureUnixReader` (`mock`), tandis que `sim_ipc.ReadOnlyUnixRpc` sait déjà ouvrir `tof.stream` et valider `tof.frame` mais **n'authentifie pas le pair et ne prouve pas la fraîcheur du capteur**. Aucun lien fiable vers une catégorie ni vers le cycle de cognition n'existe ; ce lot n'invente **pas** une catégorie à partir d'une distance.

**État des sources vérifié avant essai :** `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068`; base P15-B1/#239 `daa74a46899f1a13db9c3f3f3d56935bccecd6e7`; `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, gitlinks inchangés ; Qwen #97–99 fusionnées. #230/#231/#235/#238/#239 toujours en brouillon ; CI P15-B1 et P15A vertes, CI BitBake #230 échouée sur runner éphémère. WIC/ZST et métadonnées RAUC P16 déjà vérifiées sur WSL2 : **aucune reconstruction**.

## Audit exact des voies OEM épinglées

- `tof/src/main.rs`, `tof/src/status.rs`, `tof/systemd/tofd.service` : `tofd`, UID `tofd`, socket `/run/tofd/tof.sock`, mode `0660`, groupe `robot` ; `RuntimeDirectory=tofd`. `tof.stream` renvoie `accepted`, `sensor`, `unavailable`, `rows=8`, `cols=8`, `hz`; `tof.frame` pousse 64 distances en mm, 64 états, séquence et `t_ns` CLOCK_MONOTONIC ; `--fake` et `--sim` existent, ne prouvent jamais le capteur physique.
- `duck-ipc-proto/src/lib.rs` : `/run/tofd/identity.json` publié au démarrage (service, pid, revision compilée facultative). Un fichier présent n'atteste pas une caméra ou un capteur réellement monté ; sa revision peut être inconnue.
- `mediad/src/frame.rs` : socket local `/run/mediad/media.sock` = `media.frame` UYVY à la demande, **pas** la diffusion des notifications `media.detections`. Celles-ci sont WebRTC ; mono-classe Microduck par défaut et détecteur désactivé. N'effectuer aucune capture image.
- `robotd` : seul propriétaire des moteurs, ONNX et de la sûreté 50 Hz. Les droits `robot` donnent l'accès OS au socket RPC robotd entier ; une *allowlist Python* est une défense applicative, pas une ACL Unix de lecture seule.

## Réutiliser / adapter / créer

| Élément | Décision |
|---|---|
| `sim_ipc.ReadOnlyUnixRpc(role="tofd")`, `parse_depth` et ses tests | Réutiliser sans nouveau protocole ni service |
| `passive_fixture_runtime` P15-B1, `ExperienceMemory` unique | Laisser inchangés ; pas de provenance fictive promue en `sensor`, pas de SQLite pour les seules distances |
| `sim_ipc.py` | Adapter avec un **seul** lecteur ponctuel opt-in exigeant le chemin OEM fixe, identité OS du pair, révision attendue explicite, fraîcheur monotone et quota |
| `mediad`, `robotd`, `tofd`, Yocto et `upstream/` | Aucun changement, aucune unité auto-activée, aucun nouveau groupe ou droit |
| Tiers C3 | Aucun outil tiers nécessaire : contrat IPC disponible chez OEM |

## Hypothèse, risque, échec et repli

**Hypothèse technique :** le protocole ToF OEM peut être interrogé sans solliciter caméra ni moteur, et l'UID/PID du pair Unix peut être rapproché d'un `identity.json` propriétaire, du socket et d'une révision attendue indépendante. Cette preuve est **locale au système d'exploitation, non cryptographique**. Elle ne garantit ni matériel réel, ni absence de simulation OEM, ni obstacle évitable, ni autorisation motrice.

**Risques :** privilège `robot` trop large ; chemin/dossier/symlink remplacé, pair usurpé, identité périmée, `revision` absente ou inattendue, JSON mal formé, capteur absent, `fake`/`sim`, latence, trame périmée/future, redémarrage `tofd`, ressources RK3566 inconnues, SIGTERM pendant lecture. **STOP fail-closed** sans écriture/effet ni motricité. Timeout plafonné, une seule souscription et au plus une trame ; aucune boucle de service, pas de caméra, pas de nouveau pilote, pas de dépendance ni de paquet Yocto. Retour arrière : retirer l'adaptateur et ses tests, sans modifier OEM, SQLite ou images.

## Tests décidés avant implémentation

**Positifs sur PC-fixtures exclusivement :** transport réutilisé envoie exactement `tof.stream` et traite un seul `tof.frame` frais correctement formé ; valide 64 zones et le nombre de trames sans stocker de données brutes ; processus one-shot termine ; `robot.do`/`media.frame` ne sont jamais émis ; identité fictive cohérente passe le **validateur purement logiciel**, sans prétendre l'authentifier sur machine réelle.

**Négatifs :** chemin public non configurable, absence de socket/uid/groupes, symlink, mauvais propriétaire/mode ou dossier insûr, mauvaise révision, PID du fichier différent du `SO_PEERCRED`, absence de `SO_PEERCRED`, `identity.json` manquant, révision inconnue, données > quota/JSON invalide, horodatage `t_ns=0`/futur/vieux, trame manquante/timeout, `sensor=fake` ou `sim`, `unavailable`, double notification/séquence invalide, paramètre CLI absent ; tous refusés sans moteur/caméra/SQLite. Une fixture sur `/tmp` n'est **jamais** un pair OEM vérifié.

**Critère PASS :** tests P15-B2 et suite Python générale verts **au dernier commit de cette PR**, absence de nouvelle dépendance, sous-module, caméra, modèle, SQLite, service, méthode motrice et capture brute ; documentation README/plan/roadmap/audit matériel à jour. Toute CI rouge ou preuve Unix manquante = STOP sans fusion. La capacité d'authentifier un vrai pair et de mesurer la charge NPU/moteur sur un robot reste **en attente du matériel**.