# R1 — Perception passive OEM sur fixtures, sans nouveau pilote

**26 octobre 2026 — code et tests hors ligne ; aucun robot physique.** Ce rapport met en œuvre le [protocole permanent « réutiliser avant de créer »](development-reuse-protocol.md) et les recommandations de l'[audit de réutilisation R0](oem-reuse-audit-2026-10-26.md).

## Modules effectivement réutilisés

| Voie *fictive* | Composant existant réutilisé | Sortie limitée |
| --- | --- | --- |
| Notifications WebRTC `media.video` / `media.detections` | `passive_media_router.parse_oem_shape_notification` (F3-C) | nombre de boîtes de Microducks, jamais identité ni score calibré |
| En-tête Unix `media.frame` | `oem_frame_preflight.parse_mock_frame_header` (F3-E) | taille UYVY théorique et âge mural déclaré, **aucun pixel** |
| Notification `tof.frame` | `sim_ipc.parse_depth` | séquence, âge de réception fictif et 64 zones ; aucune distance conservée |
| Son synthétique de banc | `passive_media_router.MockAudioCueRouter` | statut et séquence, **jamais un vrai mot-clé entendu** |
| Décision et mémoire | `passive_sources.PassiveRead`, `perception.PerceptionSnapshot`, `AutonomyBrain`, `PassiveObservationJournal` | non-`ok`, événements vides, décision `idle`, zéro ligne SQLite |

La seule nouvelle fonction de liaison est [OEMFixtureInspector / OEMFixtureMetadata](../microduck_companion/oem_passive_fixture.py), qui appelle les validateurs existants sans refaire l'acquisition ou le décodage des médias. Aucun socket, flux WebRTC réel, enregistrement, inférence ou client Qwen n'est instancié.

## Sécurité, provenance et limites

- Le constructeur possède déjà les capteurs et les mouvements. `robotd` garde l'autorité exclusive des moteurs ; le cerveau Companion n'envoie aucune commande.
- Les notifications **WebRTC** ne proviennent **pas** du socket Unix local `/run/mediad/media.sock`. Leurs horodatages de capture ne sont pas certifiés dans ce prototype.
- Un en-tête `media.frame` contient une taille déclarée : il ne prouve ni l'origine du média, ni que ses octets ont été reçus. La petite tolérance d'horloge future du validateur historique est refusée par R1.
- La matrice ToF 8×8 ne certifie jamais `floor_clear`, le sol ou les escaliers. Les étiquettes audio sont **syntétiques** et n'implémentent pas la reconnaissance de mots-clés.
- Tous les reçus portent `category=unknown`, `source_authenticated=False`, `motion_authorized=False`, zéro moteur, zéro appel PC, zéro octet média conservé. Même une instanciation directe ne peut promouvoir ces attributs sans erreur de validation.
- Duplicatas, horloges régressantes, échantillons périmés/futurs, tailles invalides, prétendues permissions de mouvement, champs personnels ou identités injectées sont rejetés.
- Les résumés n'exposent ni image, ni matrice brute, ni forme des rectangles, ni transcription ou identité. `to_passive_read()` renvoie toujours une lecture sans événement **non-ok**, que F1-C/F2-A ne peut pas enregistrer comme vraie perception.

Ces tests **ne prouvent aucune connexion réelle** à `mediad`, `tofd`, `pet-detect` ou un robot Microduck. Ils ne mesurent aucune marge de RAM, chaleur, délai moteur, sécurité de navigation ni autonomie. Le constructeur prévoit encore son cerveau autonome M9 : aucune logique motrice doublonnée n'est ajoutée.

## Vérifications

- [Tests de contrat R1](../tests/test_oem_passive_fixture.py) : validation positive, erreurs, mémoire et propositions F1/F2.
- [Contrôle du protocole durable](../tests/test_reuse_protocol.py) : la checklist et les imports de parseurs existants sont toujours présents.
- Commandes : `python -m unittest discover -s tests -p 'test_oem_passive_fixture.py' -v` et `python -m unittest discover -s tests -v`.
- La suite GitHub Actions Python sur la branche a déjà réussi avec **956 tests**, [exécution #40313635916](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40313635916). Cette preuve concerne le commit de l'exécution ; la dernière CI sur la PR doit rester verte avant fusion.

## Suite, sans brûler d'étapes

**R2** : présenter sur PC les mêmes objets dans différentes prises de vue authentiquement indépendantes, et les mêmes événements sonores dans plusieurs enregistrements autorisés. Mesurer rappels, confusions, inconnus, CPU/RAM, et taille SQLite. **R3** : examiner un jour l'API M9 si elle est réellement publiée. **R4** : Qwen facultatif sous quotas. **R5** : validation physique après audit des ressources et des barrières constructeur.
