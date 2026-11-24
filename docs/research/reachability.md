# Accessibilite des coffres et points de collecte (tools/reachability.py -> reachability.json)

Estimation statique, sans lancer le jeu, des capacites de mouvement necessaires pour atteindre chaque coffre
(265) et point de collecte (1090) de `world_positions.json`. Relancer :

```
python tools/reachability.py extract   # une fois (~25 min) : COL2 + Layout.lay des 255 cellules wd*/g*.dat en cache
python tools/reachability.py run       # ~15 min -> docs/research/reachability.json
python tools/reachability.py run --jump1 2.5 --jump2 5 ...   # autres seuils (voir --help)
```

Un seul .dat decompresse a la fois ; le cache (`%TEMP%/nier_research_cache/reachability`) garde les triangles
(.npz) et les points de sol rasterises (.npy). RAM < 200 Mo.

## Donnees
- Collisions : fichiers `.col` (COL2) des cellules `wd1` (monde ouvert, 125 cellules avec col), `wd3` (18 variantes
  de la ville apres l'effondrement) et `wd5` (17 cartes : Tour, Ville copiee, sous-sol de l'usine, foret, parc,
  ville inondee...). wd2, wd4 et wda n'ont pas de .col. Format : voir data_formats.md "Collisions COL2".
- Les cellules wd1/wd3 sont en coordonnees LOCALES : grille hexagonale de rayon 100 m, decalage retrouve par
  recalage (data_formats.md). **Validation** : les 233 positions de 2B relevees en jeu (`tools/path_log.tsv`)
  ont toutes un sol praticable 0 a 0,5 m sous elles (mediane 0,02 m).
- Ancres (endroits ou le joueur se tient a coup sur) : releves en jeu (path_log.tsv), positions de depart des
  sous-phases (routes_full.json `start_pos`), terminaux ba1000/ba1100, PNJ (objId pl*/um*) des quetes et
  magasins (world_positions.json).

## Methode
1. Sol praticable = triangle dont |normale y| >= 0,6 (pente <= ~53 deg). Tous les triangles sont pris, quel que
   soit leur champ `flags` (semantique non verifiee). Rasterisation sur une grille de 1 m : pour chaque case,
   les hauteurs des triangles couvrant son centre ; hauteurs a moins de 0,4 m fusionnees = couches.
2. Carte de l'objet : parmi les cartes dont l'emprise couvre (x, z), celle dont un sol est le plus proche sous
   l'objet (dans [y-6, y+0,6]) ; bonus a la carte du fichier de l'entite (wd5/...), malus aux cartes "test"
   (g5a001/g5a002). Les autres candidates et leur ecart sont dans `map_candidates`.
3. Fenetre locale de 80 x 80 m autour de l'objet. Noeud de depart = couche sous l'objet. Cibles = couches sous
   une ancre + toutes les couches du bord de la fenetre (on suppose l'exterieur relie au reste de la carte).
4. `min_climb` : recherche minimax entre cases voisines = plus petite "plus grande montee" d'une cible jusqu'a
   l'objet (descendre est gratuit). 0 = accessible en marchant (marches <= 1 m entre cases).
5. Niveaux testes dans l'ordre (le premier qui relie une cible a l'objet donne `needs`) :

   | niveau | montee max | vide franchissable |
   |---|---|---|
   | `[]` (saut simple, vol plane du Pod) | 2,0 m | 4 m |
   | `["Double Jump"]` | 4,0 m | 6 m |
   | `["Double Jump", "Air Dash"]` | 4,0 m | 10 m |

   Aretes : cases voisines si montee <= max(1 m, montee max) ; saut au-dessus du vide depuis une case de bord
   (voisine sans sol au meme niveau) vers toute couche a distance <= vide + 2 x chute (vol plane) et montee <=
   montee max. "Ground Evade" n'est pas exige (rien ne le distingue en statique) ; "Pod Program" n'intervient
   pas : le vol plane (maintenir saut) n'en depend pas.
6. Rien ne relie l'objet -> `unknown`.

## Seuils = HYPOTHESES
Les hauteurs/distances de saut de 2B ne sont pas dans les donnees : aucun parametre de saut dans `pl0000.dat`
(seulement des .csv d'experience/combo) ni de constante flottante evidente dans les fonctions de saut de l'exe
(0x47e0b0, 0x4e0f06 qui incremente le compteur de sauts `[2B+0x14A8]` : seulement 0.1/0.2/0.3/pi...), la hauteur
vient vraisemblablement des motions (root motion). Valeurs par defaut = estimations a mesurer en jeu (2B :
saut simple ~2 m, double saut ~4 m). `min_climb` est fourni pour re-seuiller sans relancer : nombre de
lieux (hors unknown) avec `min_climb` > 1,5 / 2 / 2,5 / 3 / 4 / 6 m = 41 / 37 / 35 / 31 / 25 / 13 (la plupart
restent atteignables par un saut au-dessus du vide depuis plus haut).

## Resultats (v1.04, seuils par defaut)
| classe | coffres | points de collecte | total |
|---|---|---|---|
| aucune capacite (`[]`) | 246 (230 high, 16 medium) | 1053 (1036 high, 17 medium) | 1299 |
| Double Jump | 3 (1 medium, 2 low) | 6 (3 medium, 3 low) | 9 |
| Double Jump + Air Dash | 0 | 0 | 0 |
| unknown | 16 | 31 | 47 |

Double Jump (`borderline` = le niveau precedent passe avec +0,5 m) :
- core_hap coffre 0xd05ab856 et point 0x4d60fdc4 (-4, 18, 291), ville effondree (wd3) : montee 4,1 m (medium).
- st1/r170 2 points (492, -71, 864) : montee 5,9 m, atteints par saut depuis plus haut (medium).
- st1/r140 2 coffres + 2 points (470-487, 20-28, -23..-55) et st1/r100 point 0x7265a73 (5, 17, 377) :
  montee 2,4-3,9 m, cas limites (low).

`unknown` :
- 38 sans sol praticable sous l'objet : Bunker (quest/qb40, 17 : pas de collision dans wd*, interieur charge
  ailleurs), sous-sol de l'usine (st5/r520, 9), st1/r170 (3), r120 (2), r500 (2), p100 (2), core_hap, r200,
  p300 (1 chacun) : sol porte par
  un objet (ba/bg avec .col propre, ascenseur) ou zone sans .col de cellule.
- 9 non relies meme avec Double Jump + Air Dash : toits de la ville (core_hap coffres 0x3e6b1ee (128, 30, 530) et
  0x5d7855c4 (208, 22, 104), point 0xd7de3ede (198, 22, 107) ; r200 points 0x65a16844 (30, 21, 450, wd3) et
  0x7cb0ba06 (-78, 20, 228) ; r140 point 0x120c7f2e (445, 27, 92)) et sous-sol de l'usine r520 (2 coffres + 1
  point vers (-347, -149..-162, 317..324)). Probablement echelle, ascenseur, decor bg/ba ou acces hors fenetre.

## Champs de reachability.json
`locations.<kind>:<fichier>:<membre>:<entity_id>` -> `needs` ([] / ["Double Jump"] / ["Double Jump","Air Dash"] /
"unknown"), `confidence`, `evidence`, `map`, `map_candidates` (carte -> y objet - y sol), `floor_height`,
`nearest_floor_delta` (y objet - sol dessous), `ground_height` / `height_above_ground` (couche la plus basse a
3-8 m, <= 40 m sous le sol de l'objet), `min_climb`, `anchors_in_window`, `borderline`, plus objId, position,
fichier, hap. `thresholds_assumed` et `summary` en tete.

## Limites
- Collisions des objets places (bg/ba : `Layout.lay` et entites hap ; ~40 % des ba/bg echantillonnes ont un
  .col) NON ajoutees : caisses, ascenseurs, echelles, portes. Ils peuvent creer un acces (unknown -> []) ou en
  bloquer un (murs/portes fermes ignores : chemins a travers des portes possibles).
- Les murs ne bloquent pas la marche entre cases (seuls les sols comptent) ; pas de test de hauteur sous plafond.
- Le bord de fenetre est suppose relie : un toit de plus de 40 m de large touchant le bord est juge accessible.
- Grille 1 m : passerelles de moins de 1 m de large ou poutres peuvent manquer.
- wd1 et wd3 se superposent (avant/apres effondrement de la ville) : la carte la mieux ajustee est prise, pas
  celle de la route en cours.
- Confiance : high = chemin a pied seulement ; medium = sauts necessaires ; low = cas limite ou unknown. Aucun
  resultat n'a ete verifie en jeu.
