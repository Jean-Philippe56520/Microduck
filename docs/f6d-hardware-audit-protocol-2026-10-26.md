# F6-D — Préparer l'audit de ressources du Microduck physique sans mouvement

**26 octobre 2026 — [PR #48](https://github.com/Jean-Philippe56520/Microduck/pull/48) fusionnée après revue et tests, protocole et protections logiciels, sans robot physique.** Ce lot améliore l'outil de collecte en lecture seule `scripts/resource-audit.sh` et ajoute une politique documentaire testable ; **aucune donnée réelle RK3566, NPU, batterie, caméra ou moteur n'a été obtenue**.

## 1. Décisions de sécurité : ne pas confondre « testable » et « validé »

- `robotd` constructeur reste l'unique autorité moteur à **50 Hz**. Ni cet audit, ni le Companion n'ouvrent un accès moteur alternatif.
- L'ancienne locomotion MuJoCo P0 n'a **pas démontré** de translation stable : **aucun audit en déplacement n'est permis par le script F6-D**. L'argument `--phase movement` est systématiquement refusé, même si un opérateur déclare toutes les vérifications réalisées. L'étude indépendante de locomotion/sûreté et sa validation supervisée devront être reprises explicitement avant une autre procédure.
- Un audit en **vision** reste stationnaire et **strictement sous contrôle opérateur des services OEM**. Le script ne démarre, n'arrête, ne configure ni la caméra, ni les détecteurs, ni les services. Le drapeau `--vision-already-enabled` est une déclaration manuelle, **pas une vérification système**. `--idle-reviewed` est également une déclaration manuelle et n'authentifie ni le capteur ni l'état thermique.
- Le champ `energy` du cerveau cognitif est fictif, et ne prouve aucun niveau de batterie. Aucune limite de RAM libre, de courant ou de température sûre du RK3566 ne peut être **déduite** du banc GitHub Actions.
- La présence d'un dossier `/var/lib/robot` ne prouve pas le montage de la partition persistante `data`. `df` peut retourner la partition système A/B. Il faut recouper l'entrée **exacte** `/proc/self/mountinfo`, le type et les options, le `PARTLABEL=data` et les permissions réelles, sans écrire de donnée personnelle dans le dépôt.

## 2. Mode hors ligne réalisable maintenant (aucun robot requis)

```sh
# N'effectue aucune lecture /proc, /sys, aucun réseau ni mouvement.
sh scripts/resource-audit.sh --plan

# Vérifie uniquement la syntaxe POSIX.
sh -n scripts/resource-audit.sh

# Tests unitaires de déclaration / refus (unittest).
python -m unittest discover -s tests -v
python -m microduck_companion.f6d_audit_plan_demo
```

Le module `microduck_companion/hardware_audit_policy.py` reçoit **des déclarations de fixtures**, pas des mesures, et expose `AuditClaims` / `review_audit_claims`. Il code les **conditions manuelles préalables** (opérateur autorisé, carte identifiée, services OEM évalués, état stationnaire, revue du repos, RAM/RSS, fréquence/thermie, partition `data`, télémétrie de cadence moteur indépendante). Les menaces listées restent dangereuses même si toutes les autres déclarations sont `True`.

**Important :** `declared_snapshot_checklist_only_not_hardware_clearance` est un état de checklist, **jamais un certificat de montage, une autorisation d'enregistrement, de vision ou de locomotion**. Tous les résultats contiennent `physical_robot_validated=False`, `motor_commands_issued=0` et `movement_authorized=False`.

## 3. Quand une unité physique de développement sera disponible

**Précondition indispensable :** accès shell constructeur/dev expressément autorisé, état stable sans enfants/animaux à proximité, surveillance humaine, arrêt d'urgence OEM accessible et modèle matériel identifié. Le script refuse les systèmes non ARM64 et l'absence de déclaration RK3566 dans le *device tree*. **Cette vérification de plateforme est une simple plausibilité, pas une authentification de Microduck** : une carte RK3566 non Microduck peut y satisfaire.

### Étape A — état stationnaire au repos, avec contrôle constructeur actif

```sh
# Seulement sur un appareil de développement RK3566 réellement possédé
# et contrôlé par un opérateur autorisé. Lecture ponctuelle, pas un démon.
sh scripts/resource-audit.sh --phase idle --operator-confirmed
```

Relever les valeurs **brutes**, l'heure UTC, révision carte/OS constructeur et firmware (cette dernière hors du script), `MemTotal`/`MemAvailable`, CMA/Swap, `df -k` et la preuve du montage `data`, RSS/%CPU de `robotd`/`mediad`/`tofd` et éventuel Companion, état systemd et `MemoryCurrent`, température en **milli-degrés Celsius**, fréquences CPU courantes/maximales en **kHz**. Vérifier les services constructeur et **la cadence/les délais de la boucle motrice via un outil OEM non intrusif indépendant**.

Le script affiche intentionnellement `MOTOR_50HZ_DEADLINE_MISSES=NOT_MEASURED` : un état `ActiveState=active` ne suffit pas à confirmer que `robotd` tient réellement ses délais à 50 Hz. Les mesures de batterie, autonomie et temps capteur sont également signalées **non mesurées**. `/usr/bin/time`, `ps` et `MemoryCurrent` ne donnent pas la mémoire libre physiquement exploitable par tous les services ni l'énergie de la batterie.

**Critère avant étape B :** examen des relevés au repos, services en état normal, intégrité des interfaces et des montages confirmées, baseline RAM/RSS/CPU/thermie enregistrée **en privé**, méthode de mesure des délais moteurs disponible ; inconnue critique ⇒ **ne pas engager la vision**. Une observation ponctuelle est insuffisante pour conclure à la stabilité : choisir une répétition minimale et documenter précisément les conditions, sans activer de nouveau service par cet outil.

### Étape B — vision constructeur stationnaire et supervisée

```sh
# L'OPÉRATEUR doit avoir relu l'étape A puis activé la vision
# par les outils constructeur, sous supervision, sans déplacement.
sh scripts/resource-audit.sh --phase vision --operator-confirmed   --idle-reviewed --vision-already-enabled
```

Comparer au **même robot et à la baseline A** : dégradation `MemAvailable`, pics RSS et consommation CPU des services, évolution de la fréquence CPU sous charge, thermie et éventuel bridage, cadence/délais `robotd`, défauts du flux `mediad`, des capteurs et de la vision. Ces mesures doivent être collectées indépendamment quand le script ne les expose pas. **Aucun temps capteur, FPS, erreur de vision ou deadline moteur n'est fabriqué par F6-D.** L'opérateur doit pouvoir interrompre la vision avec les contrôles OEM ; le script ne la pilote pas.

### Étape C — mouvement : **non autorisé par F6-D**

**Il n'existe aucune commande de collecte en déplacement dans cet outil.** Une procédure ultérieure distincte devra d'abord réunir une locomotion reproductible prouvée en simulation, un contrôle des dangers de sol/obstacles, un protocole de vitesse et de zone, un arrêt constructeur et une surveillance adéquate. Le ToF 8×8 ne suffit pas à garantir une détection d'escalier ou l'évitement d'animaux mobiles. **L'absence de preuve impose de rester immobile**.

## 4. Critères d'interruption et de non-déploiement

| Signal observé ou manquant | Réponse prudente | Pourquoi cela bloque |
| --- | --- | --- |
| Un seul **délai moteur OEM manqué**, reset de `robotd` ou cadence non vérifiable | Arrêter les activités Companion/vision non essentielles par la voie **OEM**, ne pas faire bouger le robot ; suspendre le déploiement | Pas de preuve de maintien de 50 Hz |
| Échauffement anormal, **throttling thermique**, baisse de fréquence inattendue sous charge, sonde thermique absente | Revenir à l'état OEM stationnaire, examiner température/fréquence, arrêter le test | Pas de seuil thermique propre au matériel confirmé |
| `MemAvailable` critique ou en chute, RSS en hausse, OOM ou allocation de mémoire refusée | Arrêter l'activité non essentielle, revoir le nombre de modèles/buffers ; aucune marge supposée | Charge globale Linux/ISP/NPU/buffers non profilée |
| Partition `data` non montée, lecture seule, chemin `/var/lib/robot` sur partition système, permissions indéfinies | **Ne pas activer la SQLite persistante du Companion** ; conserver `:memory:` et/ou arrêter le test | Risque de fausse persistance et d'écriture sur A/B |
| Perte de `mediad`, `tofd`, capteur incertain ou sol non fiable | Ne pas interagir physiquement ; `idle` ou repos local après accord OEM | Les données courantes de sécurité ne sont pas garanties |
| Surveillance/arrêt d'urgence insuffisant, enfant ou animal dans la zone de test | Annuler le test, pas de mouvement | Sûreté matérielle non établie |
| Absence de mesure vérifiée ou révision de carte/firmware inconnue | **Indéterminé = non validé**, pas de passage de phase automatique | Les nombres hôte GitHub ne prouvent rien sur RK3566 |

**Aucun seuil numérique universel** de `MemAvailable`, température, énergie ou FPS n'est inscrit : les limites devront être déterminées selon le matériel exact, les protections officielles et la dégradation mesurée en conditions contrôlées. Un unique échantillon ne peut pas arrêter activement un service : l'humain et les protections OEM prennent la décision d'interruption. Le modèle de checklist n'appelle aucune méthode motrice.

## 5. Confidentialité et traçabilité

Le script ne lit ni identifiants Wi-Fi, adresse IP, mots de passe, image, audio, données de l'enfant ou journal système complet. Il n'envoie rien sur Internet, n'ouvre aucun socket, ne crée pas de fichier, n'enregistre pas de trace et **n'exécute aucun changement sur le système**. Toutefois les noms de carte, chemins de montage, processus et état des services peuvent être sensibles : **garder les sorties brutes en privé**, expurger les données identifiantes avant tout partage, ne jamais commiter de capture de télémétrie personnelle.

Le script affiche `F6D_SURVEY_ONLY=YES`, `ROBOT_HARDWARE_VALIDATED=NO` et `F6D_RESULT=SNAPSHOT_ONLY_MANUAL_REVIEW_REQUIRED`. Un **faux script exécuté dans GitHub Actions n'est pas un audit physique** : CI uniquement `--plan`, syntaxe, vérification des refus et checklist fictive. À vérifier lors du premier accès : disponibilité de `ps`, `systemctl`, `awk` et chemins sysfs dans l'image Yocto réellement livrée, sans supposer que la variante commerciale utilise exactement le snapshot beta documenté.

## 6. Tests et suite

`tests/test_hardware_audit_policy.py` couvre les préconditions statiques, tous les drapeaux de danger, le rejet des étapes mouvement, l'interdiction de promouvoir des déclarations fictives en preuve matérielle, les mauvais types, les arguments shell invalides, le mode sans collecte et le rejet d'une machine Linux x86-64. La démonstration `f6d_audit_plan_demo.py` ne lit **aucune** donnée système. Les tests CI ne réalisent pas l'étape A ou B sur une carte physique.

**Suite après F6-D :** aucun déploiement F7 tant que le robot n'est pas disponible et que les mesures A/B ainsi que les délais moteurs ne sont pas vérifiés. Une activité indépendante reste possible : **validation volontaire sur le PC local** d'Ollama + Qwen 4B puis 9B avec mesures réelles de latence/RSS/consommation, hors du robot. La locomotion MuJoCo demeure un chantier séparé suspendu jusqu'à une hypothèse falsifiable.
