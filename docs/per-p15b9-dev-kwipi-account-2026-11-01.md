# P15-B9 - contrat avant code (2026-11-01)

## Objectif et preuve du manque
Prouver qu'une image `microduck-image-dev` peut contenir un utilisateur de service systeme nomme `kwipi`, isole du groupe moteur `robot`, sans connexion interactive ni service active. L'operateur a lu en lecture seule la partition GPT `rootfs_a` de la WIC DEV deja verifiee (12 968 805 376 octets, SHA-256 `c1140e7508559ebc9467c3f97d3c9891452228f05b3baf999ccaa3c0a5f11bc8`) : `WIC_ROOTFS_A_GPT: PASS`, `OEM_MICRODUCK_ACCOUNT: PRESENT`, `KWIPI_ACCOUNT: ABSENT_IN_ROOTFS_A`, `LOOP_DETACHED: PASS`. Sortie utilisateur seulement, aucun fichier WSL2 disponible sur GitHub. L'absence est attestee pour **cette partition / cette WIC**, pas pour tout futur build.

## Source et comparaison
Projet parent PR #246 au SHA `fa783ff162ad356d5298e2f3e1157cd0a7d696b0` (brouillon, base #245). `main@eab73e9435dbd217c0e50b9e9ecfd59730a6e068`; `microduck_yocto@1ee58387810cebb67ae0d634c351d95024483bce`, constructeur `microduck@942e58e3aa6dbb28e7037203fff11866122c7567` et simulation `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3`. OEM `microduck-image.bb` utilise `inherit ... extrausers` et `EXTRA_USERS_PARAMS` pour creer `microduck` avec groupe `robot`. `microduck-image-dev.bb` le reutilise. Les couches P14C et P15A installent seulement des paquets, avec controles d'octets historiques intouchables. P15A `DynamicUser=yes` et `SupplementaryGroups=robot` **ne constituent pas** le compte isole recherche. PR Qwen #97-99 fusionnees, sans incidence.

## Reutiliser / adapter / creer
- **Reutiliser** la classe `extrausers` deja heritee dans la recette OEM et la syntaxe `EXTRA_USERS_PARAMS`, sans modifier OEM ou `upstream/`.
- **Adapter** seulement la selection DEV par une couche optionnelle `meta-kwipi-p15-account` a bbappend nomme exactement `microduck-image-dev.bbappend`; ne pas modifier les couches P14C/P15A (empreintes strictes) ni la recette shipping.
- **Nouveau minimum** : declaration d'un groupe prive `kwipi` et utilisateur systeme `kwipi` sans home ni shell interactif, mot de passe verrouille; tests Python de source et negatif de selection, plus preuve BitBake effective requise avant rootfs.

## Seuils positifs, negatifs, STOP
1. Couche limitee aux 2 fichiers `conf/layer.conf` et `recipes-core/images/microduck-image-dev.bbappend`; `LAYERSERIES_COMPAT=wrynose`, pas d'installation de paquet/service ou modele.
2. La declaration doit utiliser `EXTRA_USERS_PARAMS:append`, conserver la creation OEM de `microduck` et exclure `robot`, `sudo`, `video`, `audio` et tout privilege supplementaire. Groupe primaire explicite `kwipi`, `useradd -r -M`, shell `/sbin/nologin`, mot de passe `!` verrouille ; zero UID chiffre fige, zero activation systemd.
3. Les tests rejettent l'absence du verrouillage du compte, le shell de connexion, `-G robot`, un mot de passe utilisable, une inclusion shipping, une recette differente, ou des fichiers de couche inconnus.
4. Porte apres code : tests source positifs/negatifs, puis **vrai BitBake `-e` DEV/shipping sur Yocto epingle**, comparaison `EXTRA_USERS_PARAMS` : un compte operateur OEM `microduck` conserve, un `kwipi` DEV et zero `kwipi` shipping. Les controles source seuls **ne sont pas une preuve d'expansion BitBake**. `do_rootfs` uniquement avec nouvel accord et build explicite : dans un nouveau rootfs, verifier `/etc/passwd`, `/etc/group`, `/etc/shadow`, groupe primaire, UID non root/non partage, absence `robot` et refus du socket moteur. En cas d'erreur : STOP, ne pas reexecuter WIC ni contourner les protections.
5. Ne pas activer de service, changer moteur, socket, ACL effective, RAUC, WIC ou sous-modules; maintien des STOP P15-B8 : montage `/run` reel, provenance timestamp, revision `DUCK_REVISION`, droits capteurs et validation RK3566.

Retour arriere : retirer simplement cette couche des `BBLAYERS` optionnels; aucune WIC ou image existante n'est modifiee. Ce dossier ne constitue ni un compte livre, ni un logiciel embarque valide.
