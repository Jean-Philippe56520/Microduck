# MEM-2A — Rappel consolidé, borné, en lecture seule (fixtures PC)

**Date :** 28 octobre 2026. **Statut :** [PR #147](https://github.com/Jean-Philippe56520/Microduck/pull/147) fusionnée (`67d6db4b`) ; [CI Python #40780346663](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40780346663) et [N1/N5/N6 #40780346693](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40780346693) réussies ; aucun robot, image, Qwen 9B, moteur ou mesure RK3566. **Autorité :** [plan-action.md](plan-action.md). Base de travail `main@bad05cdfcc72c84fea74988a9950e225f864ebf8`; fusion après contrôles verts ; revalider le `main` et les gitlinks avant tout prochain chantier.

## Porte OEM-first, hypothèse et limites de preuve

**Constats vérifiés :** `ExperienceMemory.observe(identifier)` incrémente `objects.sightings` avec UPSERT. Cent appels portant le même identifiant synthétique restent une seule ligne, mais **ne prouvent ni 100 rencontres indépendantes ni l'identité physique d'un objet**. C1 `memory_consolidation.recall_category` agrège les seules catégories fictives F1-C/F2-C/F4-A actives et corrigibles, avec sessions déclarées non indépendantes. MEM-1 conserve les objectifs fictifs et références EX1 sans seconde SQLite. DET-1 est déjà fusionné (#143) mais **n'autorise pas la reprise automatique d'un objectif tenté**. F5 v2 Qwen3.5 9B est encore un pilote **manuel sur PC**, sans mémoire multimodale connectée.

**Source OEM épinglée relue :** `pollen-robotics/microduck@942e58e3aa6dbb28e7037203fff11866122c7567`, `robotd/src/intents.rs` (intents horodatés et deadman), `docs/design/robotd-design.md` (robotd seul maître de la boucle 50 Hz), `mediad/src/sensor.rs` (IMX219 Zero3/GC2093 Beta), `microduck_rl@b02fdea4902c2b93b7d34a83a6f05da4ececb7d3` (politiques ONNX/RL). Sans robot physique, version, caméra effective, modèle ONNX chargé, policy, `robotctl health/monitor`, scènes et mémoire flash **inconnus**. Aucun appel OEM n'est nécessaire pour ce lecteur.

**Hypothèse MEM-2A :** une **projection en lecture seule** de F0 + C1/C2 + MEM-1 peut rappeler comptage, catégories, hypothèses, conflits et objectifs fictifs sans dupliquer les preuves ni confondre catégorie, identifiant F0 et individu réel.

**Critères de refus :** nouvelle DB/table/writer, inférence d'identité à partir de M1-B, promotion des textes Qwen en vérités, ancien marqueur de rétraction réactivé, sortie de données personnelles, lecture d'une autre SQLite, nouvelle autorisation motrice, exercice réseau ou résultat physique inventé. **Retour arrière :** ne pas importer `memory_recall` ; zéro migration, zéro modification des anciennes lignes, OEM inchangé.

## Réutiliser / adapter / créer

| Source | Décision | Motif |
| --- | --- | --- |
| `ExperienceMemory` F0 | Réutiliser SELECT `objects` | Fiche/compteur **déclarés**, jamais identité |
| C1 `memory_consolidation.recall_category` + C2 | Réutiliser sans recopier | Corrections, TTL, provenance et contradictions déjà traitées |
| MEM-1 / EX1 | Réutiliser lectures facultatives | Au plus huit objectifs résumés ; liens consultés, pas réinscrits |
| M1-B/R2-C | Ne pas raccorder | Signature 64 octets et seuil de ressemblance **ne prouvent pas même objet** ; R2-C suspend l'identification des instances |
| F5-C / Qwen9B | Ne pas appeler | QW-1 et QW-2 sont des lots autonomes sous opt-in/quotas |
| OEM robotd / mediad / tofd | Ne pas toucher | Pas de moteur, capture ou télémétrie directe |
| `memory_recall.py` | Créer une seule projection bornée | Pas d'autre SQLite, table, boucle ni service |
| QuackNav, microduck-brain/twin, Quacksat et autres tiers | Registre C3, pas de copie | Aucune dépendance externe justifiée pour ce SELECT |

## API MEM-2A

`recall_memory(memory, semantics, category, now_wall_epoch_s, object_key=None, goals=None)` :

- Exige les **instances déjà créées** `ExperienceMemory` et `CategorySemantics` reliées à **la même connexion** ; un MEM-1 optionnel doit aussi partager cette connexion. Aucune ouverture ni initialisation de schéma par le lecteur.
- Utilise `recall_category()` C1 pour les observations **fictives historiques**, les sessions *déclarées*, les hypothèses non vérifiées, leurs conflits et la prise en compte des rétractions. Aucun échantillon audio/vidéo conservé.
- Accepte un identifiant F0 opaque `o-` suivi de 16 chiffres hexadécimaux **uniquement dans ce lecteur** ; sa fiche est rapportée séparément des catégories C1. Le champ `sightings` compte des **appels** et non des rencontres physiques. Les étiquettes hors vocabulaire fermé deviennent `unknown`.
- Lit éventuellement les objectifs MEM-1 récents (au plus 14 jours fictifs), `candidate/active/suspended`, en **résumant au plus huit** objectifs. Le booléen `goals_truncated` signale une troncature. Les références EX1 disponibles sont comptées sans valeur causale.
- Ne calcule **ni un score de nouveauté fiable, ni une preuve de nouvelle vue, ni un signal d'appel Qwen**. Les champs `same_physical_object_verified`, `physical_effects_verified`, `motor_commands_issued`, `qwen_requests`, `memory_writes` restent à zéro ou `False`.
- L'API peut renvoyer une erreur sur données corrompues, autre mémoire, horloge invalide ou clé interdite : ne pas appliquer de réparation automatique ni traiter le rappel comme une perception fraîche.

### Exemple attendu, uniquement fixture

Cent `observe("o-00000000000000a1", "unknown", source="mock")` donnent une seule ligne F0 et un compteur 100. Le rappel rapporte `sightings=100` et `independent_encounters_verified=0`. Si un autre objet fictif utilise `o-00000000000000b2`, les fiches **ne sont pas fusionnées**. Cette différence de clés ne prouve pas deux objets physiques.

Une hypothèse F4-A retirée n'apparaît plus dans le prochain rappel, y compris après réouverture du fichier SQLite. Une question restée ouverte ne déclenche **pas** Qwen dans ce lot.

## Essais prévus / exécutables

```bash
python -m unittest discover -s tests -p test_mem2_memory_recall.py -v
python -m unittest discover -s tests -v
python -m scripts.n3_sqlite_audit --output /tmp/n3-mem2.json
```

Couverture : 100 appels identiques, deux clés distinctes, compteur/identité séparés, catégorie C1 et rétraction F2-C, hypothèse C2 rétractée et réouverture SQLite, objectifs MEM-1 corrigés et plafonnés, absence d'écriture pendant le rappel, clé SQL malicieuse refusée, vocabulaire et horloge invalides, DB divergente, zéro requête Qwen ou ordre moteur. Les 11 tests ciblés MEM-2A ont été inclus dans la [suite Python #40780346663](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40780346663) **réussie** ; [inventaire N1/N5/N6 #40780346693](https://github.com/Jean-Philippe56520/Microduck/actions/runs/40780346693) **réussi**. N3 et N4 ont également réussi en CI. Tests PC/fixtures uniquement.

**Ressources :** nombre borné de lignes F4-A (256), MEM-1 (32) et F0 un objet par clé ; lecture F1/F2 jointe par C1. Temps CPU, RSS, croissance WAL sur le RK3566 **non mesurés**. Ne pas changer les quotas OEM ni ajouter un accès par tick 50 Hz.

## Suite et séparation des lots

- **MEM-2B / Cat-B/C3-B :** définir et mesurer une *rencontre* multi-vue avec continuité et abstention, sans déclarer l'identité sur un simple fingerprint. Les vrais objets inconnus, plantes incluses, demandent une perception fiable avant regroupement.
- **DET-2 :** permettre une reprise seulement si contexte/stratégie/provenance apportent une nouvelle information indépendante, sans répétition compulsive.
- **QW-1 :** assembler un contexte public expurgé pour le vrai Qwen3.5 9B sur PC, avec consentement F5-C, JSON strict et sorties hypothétiques ; ne jamais exporter la SQLite entière.
- **QW-2/E2E-1 :** test de seconde consultation vraiment utile après nouvelle observation, et ablations sans/avec mémoire/PC sur scènes indépendantes.
- **PHY-1 :** mesures RK3566 et preuve des interfaces OEM en lecture seule sur robot, puis essais physiques graduels seulement après validation distincte.

**Statuts explicites :** MEM-2A = **codé/testé CI PC-fixtures, PR #147 fusionnée** ; MEM-2B/DET-2/QW-1/QW-2 = **prévus**, aucune autonomie perceptive, Qwen intégré ou robot validé.
