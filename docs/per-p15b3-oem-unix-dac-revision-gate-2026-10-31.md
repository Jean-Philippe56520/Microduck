# P15-B3 — Porte Linux d'accès capteur sans capacité motrice et identité de build (31 octobre 2026)

## Préenregistrement avant tout test et toute modification

**Objectif concret.** Permettre à un futur processus Kwipi non moteur de **lire le ToF OEM local** sans obtenir en même temps le droit Unix d'envoyer des RPC à `robotd`. P15-B2/#240 a validé la forme et la fraîcheur d'une trame sur PC, **pas** l'isolation du client. Deuxième question ciblée : la révision `tofd` déclarée lors de la compilation Yocto correspond-elle au SHA épinglé exigé par le lecteur P15-B2 ?

**Références vérifiées :** `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068`, branche dépendante de [#240](https://github.com/Jean-Philippe56520/Microduck/pull/240) au SHA `29939c64829370eb8b29058e8f0085a8baa4569d`. `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567` ; `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` inchangés. Yocto référencé `microduck_yocto@1ee58387810cebb67ae0d634c351d95024483bce`. P15-B2 15/15 cas nouveaux et suite 2 021 tests Python verts (22 ignorés) au SHA testé ; P14B CI BitBake #230 rouge, paquet WSL2 local attesté séparément, WIC P16 déjà vérifiée, RAUC DEV non signé. Ne pas reconstruire P16 ni fusionner hors séquence.

## Observation, hypothèses, preuve, risque

**État OEM exact** (sources épinglées) :
- `tof/src/main.rs` : `/run/tofd/tof.sock` mode `0660`, propriétaire du daemon `tofd` par défaut, **groupe `robot` via `give_to_group`** ; `tof/systemd/tofd.service` utilise `User=tofd Group=tofd SupplementaryGroups=i2c robot`, `RuntimeDirectory=tofd`. `/run/tofd/identity.json` est publié par le processus.
- `robotd/src/main.rs` : `/run/robotd.sock` mode `0660`, propriétaire root, groupe principal `robot` selon `robotd/systemd/robotd.service`. Le serveur accepte directement `robot.do`, `robot.move` etc. sans filtrage UID spécifique côté `robotd`; la sûreté motrice interne OEM reste en place mais ne crée **pas** un droit Unix « lecture seule ».
- `mediad` publie `/run/mediad/media.sock` mode `0660` groupe `robot`, utilisateur `mediad`. Aucun accès caméra/vidéo n'est visé dans ce lot.
- `duck-ipc-proto/src/lib.rs` : l'identité déclarée est `option_env!("DUCK_REVISION")`; sans variable **lors de la compilation**, `revision` vaut `null`. La couche P12 `scripts/per_p12_yocto_layer.py` installe source/versions du paquet `0.17.8+kwipi.p12.<companion SHA court>`, mais ne définit **pas** `DUCK_REVISION`. La recette constructeur `microduck-daemon.bb` épinglée ne la définit pas non plus. **Absence de preuve de révision effective** et risque de mismatch avec `_PINNED_OEM_TOF_REVISION = 942e58e3...` ; ne pas supposer la valeur du binaire construit, ni falsifier son SHA. Il faut inspecter le build réellement livré / son environnement avant d'autoriser le lecteur.

**Hypothèse de test non déployée :** une ACL POSIX sur **le socket ToF seulement** peut accorder à un UID dédié `kwipi` l'accès à ce socket, sans ajouter le groupe `robot`. Le binaire `tofd` devrait appliquer ce droit **après chaque bind/rebind**, avec une décision OEM explicite : `setfacl` manuel, une unité déclenchée en retard ou une ACL seulement sur le répertoire ne constituent **pas** une solution permanente sûre. L'ACL de fixture ne certifie pas sa disponibilité dans l'image Yocto.

**Alternative refusée provisoirement :** utiliser `User=tofd` sans groupe `robot` donne techniquement accès au socket ToF par les bits « owner » sans accéder à `robotd`, mais partage le même UID et donc la propriété des fichiers d'identité, l'intégrité des données et potentiellement le droit de signaler le processus capteur. Ce n'est **pas** une identité indépendante suffisamment isolée pour Kwipi. Ajouter `SupplementaryGroups=robot` donne accès au socket moteur et est expressément interdit.

**Risques et retour arrière :** erreur de chown/mode, ACL héritée ou perdue au redémarrage `tofd`, privilège `robot` ajouté, UID commun au capteur, parent non sûr, absence d'ACL ou de variables de compilation, version Yocto différente, lectures prises pour des faits physiques. STOP sans observation considérée authentifiée, et aucune installation / service moteur. Retour arrière : supprimer tests et documentation candidat ; **aucune ACL réelle, binaire, sous-module, unité ou image ne doit être modifié par ce lot**.

## Matrice de réutilisation

| Source/élément | Décision |
|---|---|
| `tofd`, `robotd`, `mediad` OEM épinglés, UID/groupe socket Unix, `SO_PEERCRED` | Réutiliser les contrats ; pas de copie ni second pilote |
| `oem_tof_readonly.py` #240 et `sim_ipc.py` P14A | Ne pas modifier : P15-B2 reste strict et fail-closed |
| Test Linux des permissions sur sockets temporaires fictifs | Un **seul** test noyau sous GitHub Actions dédié, pas de binaire, groupe ou service sur machine de l'utilisateur |
| ACL POSIX par UID dédiée | **Tester seulement** sur sockets de fixture ; adaptation OEM/Yocto envisagée **seulement sur accord, après preuve de faisabilité/ressources** |
| Source d'identité P11/P12/Yocto | Audit lecture seule ; ne pas fixer `DUCK_REVISION` arbitrairement au SHA OEM de base |
| Références C3 externes | Aucune dépendance ou licence tierce nécessaire |

## Tests préenregistrés, témoins et critères

**Témoin** : trois sockets Unix Linux **de fixture** mode `0660`, propriétaires `root`, `tofd`, `mediad` (UID numériques éphémères), groupe `robot`, sous répertoires temporaires, processus clients aux UID/GID fictifs distincts. Ne pas utiliser les sockets `/run` réels et ne pas essayer de RPC moteur.

**Cas positifs** : (P1) groupe robot peut *connecter* aux trois sockets (preuve de sa portée, pas un droit autorisé pour Kwipi) ; (P2) compte `tofd` sans groupe robot peut connecter à son socket ; (P3) UID `kwipi` sans groupe robot peut connecter à **tof.sock seulement après ACL ciblée**, et **reste refusé** par les sockets `robotd` et `mediad`; (P4) révoquer cette ACL révoque l'accès. Aucun `robot.do`, caméra, fichier mémoire ou fichier sous `/run` requis.

**Négatifs** : (N1) UID `kwipi` isolé sans ACL ne peut ouvrir aucun socket ; (N2) `kwipi` + groupe robot pourrait accéder au socket moteur — cette configuration doit être classée **unsafe** ; (N3) UID commun `tofd` peut altérer un fichier d'identité possédé par ce même UID, donc solution **non acceptée** ; (N4) une ACL accordée au précédent inode du socket ne survit **pas** à son remplacement (ne pas annoncer une permission persistante) ; (N5) tests échouent explicitement si ACL absente ou noyau non conforme, sans activer le service ; (N6) `DUCK_REVISION` absent ou incompatible signifie identité **inconnue/refusée**, non une raison de relâcher le contrôle.

**Critère PASS du lot logiciel :** essais DAC/ACL **réellement exécutés sur noyau Linux GitHub Actions**, neutres pour la machine de l'opérateur ; P15-B2/P14A et suite Python générale au HEAD de PR vertes, aucune nouvelle permission ou module de runtime, docs README/plan/roadmap/audit actualisées. Si ACL indisponible dans la CI ou échec d'isolation, **STOP** et rester sans accès ToF autorisé. **Critère pour P15 en production (distinct et non atteint)** : stratégie explicite intégrée dans l'OEM et reconstruite sur autorisation, identité de binaire réelle, vérification client Linux sans groupe moteur sous système cible, tests redémarrage/stop/ressources, robot physique supervisé. L'essai ACL en CI ne satisfait pas ce critère.

**Décision attendue après tests** : faisabilité Linux en fixture seulement, ou impossibilité prouvée ; dans tous les cas la version livrée et l'autorisation d'adapter OEM resteront **en attente**. P15-B4 pourra avancer séparément en exploitant uniquement des fixtures et source constructeur.
