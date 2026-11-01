# P11-C1 — intégration des overlays P15-B4/B8 dans l'archive de sources P11 (01/11/2026)

## Décision fixée avant modification du générateur

**Base :** `main@db2e138a81cf1126b9b1a1daecd9efef48136c27`. Gitlinks inchangés `upstream/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `upstream/microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`, Yocto OEM `1ee58387810cebb67ae0d634c351d95024483bce`. Qwen PR #97–99 fusionnées. OEM `main@b2b0d213` différent du pin pour `mediad/src/main.rs` : **aucune montée de version OEM**.

**Objectif vérifiable :** le seul générateur `scripts/per_p11_v1_source_release.py` doit produire un tar source déterministe contenant P10A/B/C **puis** P15-B4 (un unique consommateur des observations du détecteur `mediad`) et P15-B8 (garde Unix ACL / rebind), sans service, média brut ni moteur nouveau. La couche P12 existante doit exploiter ces octets exacts par `file://kwipi-v1-oem-source.tar.gz` sans nouvelle recette, gitlink ou double `mediad`.

**Écart prouvé :** dans la version de base, `build()` appelle uniquement `apply_a`, `apply_b`, `apply_c`, puis `drop_test_harness`. Les fichiers B4/B8 fusionnés existent avec leurs propres scripts et leurs CI (PR #242/#246), mais ne sont **pas appelés** dans la génération P11. Le binaire `mediad` historique P13B2 construit sur WSL2 et l'ancienne WIC P16 **ne prouvent pas** leur présence. `DUCK_REVISION` dans un binaire démarré, UID/ACL sur un vrai `/run` et provenance/capture des observations restent **inconnus**.

## Réemploi / adaptation minimale

- **Réutiliser :** `per_p10a/b/c` (source OEM épinglée, détecteur unique, `enabled=false`), `per_p15b4_apply_oem_local_detections.apply`, `per_p15b8_apply_oem_acl_binder.apply`, `per_p11_v1_source_release.verify_archive`, `per_p12_yocto_layer.checked_artifact`, CI P11/P12 et tests existants P15-B4/B8.
- **Adapter :** ordre des appels dans `build()` avant suppression du marqueur scratch ; manifeste de composition P11 ; contrôles d'archive, de module local et de refus P12 ; assertions d'archive compilée dans la CI P11. **Aucune nouvelle bibliothèque, entrée caméra, processus de supervision, RTC, modèle, poids, base ou recette OEM.**
- **Créer uniquement :** nouveaux tests négatifs de provenance/overlay dans la suite déjà présente et présente fiche. Le code OEM Apache-2.0 épinglé reste avec sa licence ; Yocto `LICENSE=CLOSED` et droit commercial des ressources sont à auditer séparément.

## Expérience prédéfinie, témoin et critères STOP

**Témoin :** sur `main@db2e138`, P11 a le manifeste P10A/B/C, sans `mediad/src/local_detections.rs` ni `mediad/src/local_detections_acl.rs`, et P12 ne peut pas les empaqueter. Les tests P15-B4/B8 seuls prouvent une **copie scratch**.

**Passage positif (tests réels à exécuter par CI, pas déclarés ici) :**

1. Deux exports P11 successifs de la **même** révision Companion/OEM génèrent des tar.gz identiques SHA-256, en réutilisant les deux fonctions B4/B8 sans patch manuel.
2. L'archive contient exactement un `mediad/src/local_detections.rs`, un `mediad/src/local_detections_acl.rs`, une seule déclaration de module, un seul branchement du détecteur OEM, et un opt-in **`false`** ; garde `observer_uid` et ACL socket-avant-répertoire/rebind vérifiées. Le marqueur P10 et le `p10c-harness` n'y figurent pas ; aucun nouveau modèle.
3. `verify_archive` contrôle un manifeste **P10A/B/C+B4/B8** et les invariants de contenu ; P12 vérifie le même contrat avant de remplacer la seule `SRC_URI`, toujours avec Yocto épinglé et `Cargo.lock` cohérent.
4. La CI compile le **vrai `mediad` exporté** avec `cargo --locked` sur hôte (aucune construction BitBake/ARM64 nouvelle) ; suites Python P11/P12 et générales, ainsi que les négatifs existants, vertes **au HEAD de cette PR**.

**Cas négatifs prévus :** nom ou contenu du module B4 absent/altéré, helper B8 manquant, identité/ACL/bind remplacés, `enabled` changé, faux manifeste « B4/B8 présents », archive modifiée après manifest, branche/empreinte constructeur différente, lien symbolique ou doublon, poids non autorisé, couche P12 avec archive obsolète P10 seulement. **L'échec de l'un de ces tests, une CI rouge, une évolution des dépendances, un second pilote/capture/moteur ou l'impossibilité de compiler le vrai export = STOP, PR brouillon non fusionnée.**

**Limites et retour arrière :** source P11/P12 **candidate** uniquement. Aucun `do_rootfs`, `do_package`, nouvelle WIC, RAUC, flash, socket `/run` réel, service actif ou test robot. Une nouvelle archive P11 rend les anciennes empreintes WSL2 **historiques** ; elle n'atteste pas un nouveau binaire embarqué ou une licence prête à la diffusion. Repli : retirer les seuls appels et validations P11/P12 de cette branche, sans toucher `upstream/`, Yocto, artefacts WSL2 ni équipement.

## Résultat

**En attente des CI du HEAD.** Codé ≠ testé hôte ≠ packagé Yocto ≠ validé robot.
