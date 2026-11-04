# VIS-FOCUS-A1 — baseline existante F1/F2, sans suivi physique

Date : 04/11/2026. **Base : `main@432c2e7e3628b2defdabd7fa9024f7f18af8b44a` après fusion QUAL-R0 #305 (10/10 CI).** Autorité : [plan d'action](plan-action.md). Décisions et critères préenregistrés dans [issue #78](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6639783194) puis [mise à jour après fusion](https://github.com/Jean-Philippe56520/Microduck/issues/78#issuecomment-6640377031).

## Question bornée et résultat attendu

Avant tout tracker, adaptation F2 ou extension OEM : quels comportements **exécutables aujourd'hui en PC/fixtures** couvrent le choix d'un seul intérêt parmi plusieurs observations, et quelles preuves manquent pour la continuité de **la même cible physique** ? Comparateur : les classes et objets de `perception.py`, `passive_observations.py`, `autonomy.py`, `passive_rhythm.py`, `passive_memory.py` et `episodic_memory.py` **inchangés**. Aucun modèle réel, image, média privé, Qwen, SQLite supplémentaire, moteur ni sous-module.

`tests/test_vis_focus_a1_baseline.py` constitue un **nouveau banc d'observation sur le comportement actuel**, pas une adaptation ni une promesse de performance. Les huit refus incluent des **tests de limites de contrat** : par exemple N6/N7 démontrent que les sorties F2 ne contiennent pas de preuve d'identité physique ou de réalité-vs-écran ; **une catégorie reconnue n'est PAS une détection sûre d'être un être vivant présent**. Ne pas compter ces tests comme un vrai classement TV/photographie ni un test de suivi visuel.

## Préenregistrement des 4 positifs / 8 négatifs (avant leur CI)

| Cas | Entrée de fixture / critère |
| --- | --- |
| P1 | 3 catégories présentes : une seule catégorie prioritaire liée au jeu/motivations, sans track dans l'intention |
| P2 | même track déclaré et cycle suivant dans le cooldown : absence de répétition |
| P3 | nouvelle catégorie fraîche : changement de catégorie admissible |
| P4 | absence de frame puis nouvelle observation `unknown` : incertitude `inspect`, sans vieille position |
| N1 | source indisponible : `idle` |
| N2 | observation expirée : `idle` |
| N3 | observation future : `idle` |
| N4 | désaccord des labels sur une piste déclarée : `inspect unknown` |
| N5 | confiance trop faible : `idle` |
| N6 | deux pistes `ball` différentes : **sortie catégorie seulement, identité non distinguée** |
| N7 | étiquette `person` pouvant représenter écran ou réalité : **pas de certificat physique ni action** |
| N8 | sûreté absente : chemin moteur `halt` et aucune action F2 |

**Succès strict du lot baseline :** les **12 tests hôte** + CI générale tous verts sur le SHA final, pas d'écriture `objects`/expériences à chaque cycle, 0 commande moteur / Qwen, 0 modification des modules de production ou gitlinks. **STOP :** test cassé ou suite rouge ⇒ ne pas fusionner ; divergence des hypothèses ⇒ documenter l'écart sans ajuster silencieusement la porte ; pas de nouvelle adaptation avant analyse. Retour arrière : retirer uniquement le test et ce rapport / workflow / en-têtes documentaires.

**Limites même si PASS :** chaque `track_id` est **fictif et déclaré** ; ces tests ne mesurent ni échange physique de cible, ni IoU/GT de localisation, ni distance, ni angle, ni modèle multicatégorie NPU, ni latence, ni réacquisition réelle, ni température et impact sur `robotd` 50 Hz. Le benchmark ne prétend pas mettre en œuvre la continuité. Toute future proposition de continuité A2 exigera une **preuve indépendante supplémentaire** et un gain mesuré contre ce témoin, avec test des détections ratées, confusion d'objets identiques et abstentions.

## Fréquence et données

Le 2 Hz OEM reste le point de référence de reconnaissance ; **1,5 Hz et 1 Hz n'ont pas été testés dans ce lot** et seront comparés sur les mêmes séquences horodatées seulement si cela permet une décision mesurable. Sans vérité terrain indépendante : taille, distance et angle physiques sont inconnus. `STOP_PROMOTION` des détecteurs multicatégories demeure ; 1 316 IDs COCO consommés, aucun rejeu.
