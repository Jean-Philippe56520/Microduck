# P16-W — examen des 32 avertissements du rootfs DEV WSL2 (31 octobre 2026)

**Suite P16-I (31/10/2026) :** le manifeste réel `microduck-image-dev-*.manifest` a été contrôlé sur WSL2 : **1 334 paquets, zéro nom finissant par `-dbg`**, `P16_I=PASS`. Les avertissements de GStreamer concernent donc des paquets de débogage **non installés dans ce rootfs DEV**. Cette preuve porte sur le manifeste audité, pas sur la shipping image ou l'absence totale de chemins debug dans d'autres fichiers. [P16-I/K](per-p16ik-manifest-and-kas-pin-diagnosis-2026-10-31.md).


## Provenance, objectif et décision

**Lot borné** : classifier sans compilation les 32 lignes d'avertissement communiquées par l'opérateur sur `bitbake -c rootfs microduck-image-dev`. Le journal local n'a pas été copié sur GitHub ; la synthèse ci-dessous contient huit types expurgés des chemins privés. La tâche d'origine s'est terminée par `P16_ROOTFS_EXIT_CODE=0` (4515 tâches toutes réussies, 2149 non relancées). Audit du rootfs réel déjà réussi : `P16_AUDIT_EXIT_CODE=0`, 19/19 modules P14B, 3/3 empreintes P15A et aucune activation par lien systemd dans le périmètre contrôlé ([reprise P16-A](reprise-v1-p16a-rootfs-verified-2026-10-31.md)).

**Critère positif du lot W** : identifier et relier chaque type d'avertissement à un mécanisme documenté, sans le masquer ni le transformer en preuve de sécurité. **Arrêt** : paquet incorrect, code erreur réel, paquet debug shipping, chemin privé sensible redistribué, recette modifiée ou pin KAS incohérent => interdiction de promotion de l'image. Aucun correctif Yocto avant preuve d'un défaut touchant le paquet runtime, la reproductibilité requise ou la sûreté.

## Classification exhaustive des 32 lignes

| Nombre | Texte du journal expurgé | Vérification OEM épinglée | Traitement |
|---:|---|---|---|
| 25 | `gstreamer1.0-plugins-rs-1.28.2-r0 do_package: buildpath in .../.debug/libgstrstracers.so` | Recette constructeur `meta-microduck/recipes-multimedia/gstreamer/gstreamer1.0-plugins-rs_1.28.2.bb`, blob `b1024c20634f607c86580c7d72952fd80bcb20e5` : le postfunc `microduck_report_buildpaths` imprime volontairement au maximum 25 lignes | **Connu, avertissement debug** : rémanence de `TMPDIR` ; ne pas supprimer le QA ni retoucher le paquet pour un artefact non livré |
| 1 | `gstreamer1.0-plugins-rs ... do_package: buildpath: 65 more not shown` | Même fonction : `if len(hits) > 25: bb.warn(...)` | **Connu** : 65 chaînes supplémentaires, non 65 nouvelles lignes WARNING ; pas un nouveau défaut |
| 2 | `gstreamer1.0-plugins-rs ... do_package_qa: ... -dbg contains reference to TMPDIR [buildpaths]` | Même recette : `ERROR_QA:remove = "buildpaths"` et `WARN_QA:append = " buildpaths"`, **uniquement** dans cette recette ; explique le downgrade volontaire par l'OEM | **Connu** : défaut de propreté/reproductibilité debug conservé en QA. Vérifier le manifeste réel : pas de `*-dbg` dans l'image DEV/shipping avant toute promotion. Ne pas affirmer que tout est reproductible |
| 1 | `udev-conf-rockchip-1.0-r0 do_unpack: ... S=${UNPACKDIR}/${BP} inexistant` | BSP épinglé `JeffyCN/meta-rockchip@f2fa9fd14571b855bb59a51da11616904a65f36d`, recette `recipes-core/udev/udev-conf-rockchip.bb` : seulement `file://99-rockchip-permissions.rules`, `do_install` lit explicitement `${UNPACKDIR}/99-rockchip-permissions.rules` | **Attendu pour cette forme de recette**, `S` par défaut inutilisé ; tâche réussie. Pas de correction OEM sans anomalie installée |
| 1 | `microduck-data-1.0-r0 do_unpack: ... S=${UNPACKDIR}/${BP} inexistant` | OEM Yocto épinglé `pollen-robotics/microduck_yocto@1ee58387810cebb67ae0d634c351d95024483bce`, `meta-microduck/recipes-core/microduck-data/microduck-data.bb`, blob `40ac4e7d7ca7c36505557b8ad4fc3c346e32ef75` : seulement `file://...` ; `do_install` copie depuis `${UNPACKDIR}` | **Même origine** ; P16 a confirmé la présence de `microduck-data` dans le manifeste mais pas chacune de ses unités OEM. Pas de modification |
| 1 | `Sstate directory is shared between several builds...` | `SSTATE_DIR` partagé sur l'hôte WSL2 conformément au réemploi des caches, environnements KAS multiples | **Avertissement de reproductibilité/provenance** : ne pas conclure que les caches n'ont aucun effet ; versions et manifests doivent rester épinglés et inspectés |
| 1 | `CONFIG_TASK_IO_ACCOUNTING is not set` | Concerne le noyau **hôte** Linux/WSL2 et la disponibilité des compteurs d'E/S du processus | **Limitation de mesure hôte**, pas une mesure robot ; ne pas extrapoler les métriques d'I/O |

**Décompte** : 25 + 1 + 2 + 1 + 1 + 1 + 1 = **32** lignes, **8** messages distincts. **Aucun avertissement signalant directement une panne d'installation des 22 fichiers Kwipi audités**, et la tâche a été réussie. Ceci n'est pas une approbation générale de tous les paquets ou du système amorçable.

## Sources exactes et contraintes

- Recette GStreamer constructeur : https://github.com/pollen-robotics/microduck_yocto/blob/1ee58387810cebb67ae0d634c351d95024483bce/meta-microduck/recipes-multimedia/gstreamer/gstreamer1.0-plugins-rs_1.28.2.bb. Le code précise que les `-dbg` ne sont pas intégrés par les images OEM (absence de `dbg-pkgs` dans `IMAGE_FEATURES`), **mais le manifeste effectif devra être revérifié**.
- Recette microduck-data constructeur : https://github.com/pollen-robotics/microduck_yocto/blob/1ee58387810cebb67ae0d634c351d95024483bce/meta-microduck/recipes-core/microduck-data/microduck-data.bb
- Recette udev Rockchip : https://github.com/JeffyCN/meta-rockchip/blob/f2fa9fd14571b855bb59a51da11616904a65f36d/recipes-core/udev/udev-conf-rockchip.bb
- Aucun sous-module ni recette modifié. **Ne pas supprimer les avertissements ou désactiver QA**. Droits du paquet Python `LICENSE=CLOSED` / `source_license_checked=false`, privilèges du groupe `robot`, RAUC, P17 et robot restent des contrôles distincts.

## Porte suivante P16-K et P16-I (lecture seule)

1. **P16-K** : KAS 5.2 refuse maintenant l'ancêtre `meta-openembedded/wrynose` au SHA OEM épinglé `f28a144aa0a0ae05ca2ee91e1aef6aa05f6a12db`. Vérifier en **Git local** la présence du commit, les refs de branche et `git merge-base --is-ancestor`, sans `fetch`, `checkout`, `reset`, modification de `kas/microduck.yml` ou contournement. Si la branche est absente ou le pin non ancêtre, consigner **inconnu/STOP** pour les nouvelles constructions reproductibles. L'audit d'un rootfs déjà construit reste une preuve distincte.
2. **P16-I** : vérifier le manifeste réel DEV et les scripts/services OEM, en particulier l'absence des paquets `-dbg`, et contrôler le contenu de `microduck-data`. Ne pas lancer un nouveau build, image WIC, signature RAUC ou action robot à ce stade.
3. **P17** : qualification plus large seulement après levée de ces portes et revue des licences et procédures OEM de retour arrière.

**État** : P16-W classification complète pour les lignes partagées, pas d'anomalie nécessitant une recompilation prouvée ; P16-K et P16-I ouverts ; P16-A rootfs vérifié localement ; P17 et RAUC non validés.
