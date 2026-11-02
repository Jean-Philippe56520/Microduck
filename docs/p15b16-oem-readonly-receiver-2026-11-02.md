# P15-B16 — réception passive OEM B12 : qualification préalable (02/11/2026)

## Objectif et preuve du manque

Baseline `main@7371a2684abdaab7703eacaa4dfad1c4f8dbb26a`, PR #267/#268/#269 fusionnées. Le modèle B15 vérifie Linux ACL/UID/PID et B12 seulement dans `/tmp/kwipi-b15-*`. Le lecteur B6 installé dans le rootfs DEV B10 est délibérément limité aux fixtures et doit garder ses cinq empreintes historiques. Aucun lecteur de métadonnées sur le chemin `/run/mediad/kwipi/detections.sock` n'est livré. Cette PR apporte un **lecteur opt-in candidat**, réutilisant B12/B14/B15, sans remplacement B6.

## Réalité du producteur OEM

Gitlink `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, simulateur `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. Recette Yocto OEM épinglée `1ee58387810cebb67ae0d634c351d95024483bce`. Exécutable DEV B12 construit depuis `e2e9bfef7d7c4f46fe51924937e7939d78d00383`, non identique au gitlink OEM; ne pas confondre identité publiée et hash binaire. Les PR Qwen #97–99 sont fusionnées mais hors du trajet et aucun appel Qwen n'est ajouté.

- Dans le code OEM épinglé, `DuckDetectorParams::default()` fixe `enabled=false`, `hz=2.0`, `threshold=0.35`. Sans modèle actif, `mediad` poursuit son service sans détecteur.
- L'adaptation B4 ajoute `--kwipi-local-detections` **désactivé par défaut**. Le constructeur `mediad.service` épinglé démarre `/opt/robot/daemon/current/bin/mediad` sans cet argument ; le paquet B12 ne garantit donc pas l'activation du point de diffusion.
- L'unité OEM déclare `User=mediad`, `Group=mediad`, `SupplementaryGroups=video render robot` et `RuntimeDirectory=mediad`. Le compte `kwipi` est distinct et ne doit JAMAIS appartenir à `robot`; ses seules permissions proposées sont les ACL B8 sur le sous-répertoire et le socket metadata.
- `/run/mediad/identity.json` est une **auto-déclaration**, non une signature du code réellement chargé. Sa révision B12 est vérifiée par B14/B16 mais ne certifie pas l'exécutable en mémoire.
- Le rootfs DEV P16-B10 audité reste inchangé (24 modules Python, deux ELF, trois fichiers P15A). B13/B14/B15/B16 ne sont **pas** inclus dans cette composition, ni dans une image shipping.

## Code candidat et arrêts décidés avant essais

`microduck_companion/b16_oem_readonly_reader.py` expose un lecteur **désactivé par défaut**, chemin de production fixé à `/run/mediad/kwipi/detections.sock`. Il vérifie comptes Unix existants, UID/eUID/GID/groupes isolés, propriétaire/type/mode des répertoires, ACL B8 exactes, `SO_PEERCRED`, identité B12 stable, inode du socket stable, JSON B12 strict, horloge et séquence croissante. Au plus une tentative / 500 ms, timeout ≤500 ms, au plus 4096 octets. Aucune requête émise, ni lecture de `media.sock`, mémoire SQLite, image, catégorie reconnue, commande moteur ou modification du service.

**Critère positif de tests PC** : flux émis par un processus fixture Unix de bon UID et ACL, accepté en statut **`oem_identity_and_b12_claim_consistent_not_sensor`**, `category=unknown`, `verified_sensor=false`, `executable_verified=false`; appels trop proches refusés. **Critères négatifs** : lecteur non opt-in, UID/groupes, droits/ACL, lien symbolique, mauvais PID/révision, identité remplacée, stale/futur/replay, champs inattendus, route arbitraire, timeout ou signal. **STOP** si permissions élargies, chemin réel dans CI, rétro-modification B6, CI rouge, exécutable présenté comme prouvé, capteur ou autonomie revendiqués.

**Limites franchissement cible** : le code peut cibler `/run`, mais aucun vrai service Kwipi ne l'invoque. Aucun test kernel RK3566, séquence disponible en condition réelle, runtime `mediad` B12, ACL, présence du modèle ou ressources validé. Activer le détecteur/flag `mediad` ou intégrer au DEV exige une décision/version de distribution distincte et les portes P16/P17 complètes. Une CI verte ne suffit pas à livrer B16.

**Retour arrière** : revert de la branche B16 exclusivement ; aucune mise à jour du sous-module, du service OEM, des recettes, du rootfs B10, de ses rapports privés ou des caches de modèles.
