# Difficulte : niveaux d'ennemis, courbe recommandee, armes, EXP (v1.04)

Genere par `python tools/difficulty.py` -> `difficulty.json`. Lecture seule du jeu. Traduction non officielle.

## Regles (exe)

- EmBase init 0x65f730 : niveau = setInfo+0x74 (copie en [em+0x594] par 0x853b60) ; parametre de placement 'Lv' le remplace ; puis 'Lv_B' si SceneState Route/B, 'Lv_C' si Route/C, 'Lv_D' si Route/D (0x65ff6c..0x660158) ; resultat [em+0x28030].
- Generateur 'EnemyGenerator' (0x346990 lit levelRange +0x9c, relativeLevel +0x3d0 ; objets 0x352b60 : levelRange par objet +0x24) ; niveau 0x3504a0 : relativeLevel -> (plage objet si non nulle, sinon niveau du joueur [Pl0000+0x14bc] via vfunc 0x2b0) + tirage plage generateur ; sinon plage objet si non nulle, sinon plage generateur. Tirage LCG uniforme min..max.
- Layouts hap (0x3e96c0) : pas de champ niveau ; setInfo+0x74 = 0 par defaut -> sans 'Lv' le niveau vaut 0 et la ligne de stats est celle du niveau 1 (0x4034d0 : indice = min(niv, nb)-1, borne a 0).
- Exception : bit 0x1000 de [0x1029b00] (pose par 0x515460 selon l'etat du joueur, probablement unite de vol) et objId em0030 : niveau = niveau du joueur, PV / 5 (0x661b2c, 0x661d03).
- Parametre 'MaxLv' (0x6619bd) : niveau tire d'une table d'execution (0x1495640) ; aucun placement ne l'utilise.
- SetLevel (vtable EmBase slot 104 = 0x631700) borne le niveau a 1..99.
- Aucune mise a l'echelle par difficulte trouvee dans ce chemin ; les layouts 'hard'/'extream' des haps sont separes (comptes dans placement_counts, exclus des statistiques).

### Tables ExpInfo

- Chargeur 0x40fdc0 : '%sexpinfo%02d.csv' (indice 4 pour em1100 setType 4..6) sinon '%sexpinfo.csv' dans le .dat de l'objet ; analyseur 0x40a6d0 (99 lignes x 0x1c o, une ligne par niveau).
- Joueur (objId 0x1xxxx, mode 2) : col0 -> +0 = EXP cumulee du niveau, col1 -> +4 = PV max (0x436640 -> +0x85c), col2 -> +8 (utilise dans les calculs de degats : attaque, deduit), col3 -> +0xc ; col4+ ignorees.
- Ennemi (0x2xxxx, mode 1) : col0 -> +4 = PV (SetLevel), col1 -> +8, col2 -> +0xc, col3 -> +0x14 = EXP donnee a la mort (0x574140 : x (1 + bonus de puce 0x10), min 1, vers 0x7c9ef0), col4 -> +0x18 ([em+0x27d54/58], sens non trace).
- Le fichier est celui de l'objId de base [em+0x2819c] (variantes sans .dat propre : table de la base).

- StateBind : core_hap.pak StateBind : champ 'Level' par sous-phase (ex. '[Route/A] 7', '[Route/B] 33'), lu par 0x35b780 comme element de type 7 ; l'applicateur 0x31dcf0 ne traite que les types 0..6 : consommateur non trouve. Interprete comme niveau prevu du joueur (confiance moyenne).
- Armes : core/core.dat:WeaponParam.csv (charge par 0x821fd0) : objId, serie, puis 4 niveaux x 8 champs (attaque min, attaque max, p2..p7). Attaque min/max : deduit (progression x1.8/x2.8/x3.8 coherente) ; p2..p7 non traces (p2/p3 ressemblent a des longueurs de combo, p7 = valeur d'aptitude). WeaponInfoTable.bxm 'Attack' 100..400 = valeurs factices identiques pour toutes.

## Notes

- Confiance : regle de niveau = haute (exe) ; persistance de Route/B en C/D = moyenne (StateOn sans StateOff) ; zone/route des placements du monde = moyenne ; 'Level' StateBind comme niveau joueur prevu = moyenne.
- Statistiques : placements de variante normale (ou sans variante) ; niveau 'unset' et 'player_offset' exclus des min/moy/max (comptes a part). Un generateur compte une fois (milieu de sa plage).
- Routes : A (p100+p200 A), B (p100+p200 B), C/D (p300). La simulation d'EXP enchaine A -> B -> C/D et ne compte que les ennemis poses (layout) des sous-phases : borne basse (sans generateurs, monde, quetes, puces).
- Non lus : ennemis apparus par scripts mruby, ennemis de piratage, STG (em0030 en vol = niveau du joueur).
- relativeLevel=1 : 34 objets de generateur. Animaux r100 (ema000/ema010) = joueur +3..5 ; r170 'ファストトラベル解除敵' = 1 + 1 (plage objet 1..1) ; p300 '敵発生機_汚染ヨルハ' (em1060, 11-xx C/D) = joueur +47..48 selon la regle lue (donc ~99 apres borne) : a verifier en jeu (confiance faible sur ce cas).
- Zones du monde : tous les placements sans sous-phase d'une zone, quels que soient les etats de scene qui les activent (arenes, apres la Tour...) : enveloppe large ; la mediane est plus representative que le max.

Placements lus : generator/none 1209, layout/normal 5669, layout/none 12

## Route A : par chapitre

| Chapitre | Nom | Zones | Niv. prevu (StateBind) | Ennemis min/moy/med/max (n) | Sans niv. | Boss |
|---|---|---|---|---|---|---|
| 01-01 | 2B's Aerial Battle | Abandoned Factory | 1 | 1/1.0/1.0/1 (1) | 368 | - |
| 01-02 | 2B's Defense Machine Battle | Abandoned Factory | 1-3 | 1/1.4/1.0/5 (69) | 16 | Marx 3, ema020 unset, Marx 2, Marx 1 |
| 01-03 | 2B's Battle on Land | Abandoned Factory | 3 | 3/3.9/3.0/6 (14) | 1 | Engels 6, Engels 5 |
| 01-04 | 2B Awakens | Bunker | 3 | - | 0 | - |
| 01-05 | The Mission | Bunker | 3 | - | 69 | - |
| 02-01 | Landing at the City Ruins | City Ruins, Resistance Camp | 3-4 | 40/40.0/40.0/40 (1) | 0 | - |
| 02-02 | Traveling to the Desert | Desert Zone | 7 | - | 0 | - |
| 03-01 | At the Desert | Desert Zone | 7 | 5/6.5/6.0/13 (60) | 0 | - |
| 03-02 | Desert Residential District | Desert Zone | 7 | 7/9.8/10.0/33 (56) | 0 | - |
| 03-03 | Battle with Adam | Desert Zone | 7 | 1/9.5/10.0/33 (40) | 0 | Adam (First Encounter) 1 |
| 03-04 | YoRHa Recon | Desert Zone -> Amusement Park | 10 | - | 0 | - |
| 04-01 | Amusement Park | Amusement Park | 10 | - | 0 | - |
| 04-02 | Tank Boss | Amusement Park | 10 | - | 2 | em3004 unset |
| 04-03 | Advent of the Songstress | Amusement Park | 10 | 15/15.0/15.0/15 (3) | 93 | Simone 15, em3004 unset |
| 04-04 | The Messenger Arrives | Amusement Park -> Pascal's Village, Pascal's Village | 10 | - | 1 | - |
| 05-01 | Pascal's Village | Pascal's Village | 10 | - | 1 | - |
| 05-02 | Goliath Attack | City Ruins | 12 | 3/4.2/5.0/5 (5) | 0 | - |
| 05-03 | Alien Ship | Alien Ship, City Ruins | 15 | 13/13.3/13.0/14 (3) | 0 | - |
| 05-04 | Battle with Adam and Eve | Alien Ship, City Ruins | 15 | 16/16.0/16.0/16 (2) | 0 | Eve (Battle in the Alien Ship) 16 |
| 06-01 | Reporting to the Commander | Bunker, Pascal's Village | 15 | - | 0 | - |
| 06-02 | To the Commercial Facility | Commercial Facility (Shopping Center) | 19 | 19/19.0/19.0/19 (4) | 0 | - |
| 06-03 | Searching the Forest | Commercial Facility (Shopping Center), Forest Castle / Forest Zone | 19 | 17/20.1/20.0/26 (41) | 1 | ema020 unset |
| 06-04 | Forest Castle | Forest Castle / Forest Zone | 19 | 18/22.2/23.0/25 (4) | 1 | ema020 unset |
| 06-05 | A2's Revenge | Forest Castle / Forest Zone | 19 | 1/17.0/17.0/22 (11) | 0 | Immanuel 1, A2 22 |
| 07-01 | Reporting to Pascal | Pascal's Village, Pascal's Village -> Resistance Camp | 22 | - | 0 | - |
| 07-02 | The Aircraft Carrier | Flooded City, Resistance Camp -> Flooded City | 22 | 20/20.0/20.0/20 (9) | 0 | - |
| 07-03 | Battle Over the Ocean | Flooded City | 22 | 25/25.0/25.0/25 (1) | 118 | Goliath Flyer 25 |
| 07-04 | Monster | Flooded City | 22 | 10/10.0/10.0/10 (2) | 2 | - |
| 08-01 | 2B Searches for 9S | Copied City, Flooded City | 24 | 25/25.0/25.0/25 (3) | 133 | Adam (Final Battle) 25 |
| 09-01 | Trends Among the Machines | Abandoned Factory, Resistance Camp | 25 | 18/22.5/22.0/25 (140) | 1 | Kierkegaard 20, Kierkegaard 18, Kierkegaard [20, 24], Kierkegaard 25 |
| 09-02 | 2B Escapes the Factory | Abandoned Factory | 25 | 15/23.1/20.0/40 (57) | 1 | So-Shi 30, Kierkegaard 18, Kierkegaard 20, Kierkegaard 29, Kierkegaard 26, Kierkegaard 25 |
| 09-03 | Multi-leg Goliath Destroyed | Abandoned Factory, City Ruins | 25-28 | 6/19.4/20.0/40 (73) | 24 | Kierkegaard 18, Kierkegaard 20, Kierkegaard 29, Kierkegaard 26, Kierkegaard 25, Kierkegaard 35 |
| 10-01 | 2B Requests Backup | City Ruins, Resistance Camp | 28 | 25/26.6/27.0/28 (14) | 1 | Boku-Shi 28 |
| 10-02 | Spherical Machine Battle | City Ruins | 28 | 25/27.0/28.0/29 (5) | 3 | Boku-Shi 28, em9000 unset, em9011 unset, em9000 29, em9010 28 |
| 10-03 | Attack on Pascal's Village | Pascal's Village | 28 | 28/28.1/28.0/29 (7) | 3 | - |
| 10-04 | Battling Eve | City Ruins | 28 | 30/30.0/30.0/30 (2) | 2 | - |
| 10-05 | The End of Battle | City Ruins | 28 | - | 0 | - |

### Route A : zones du monde (placements sans sous-phase)

| Zone | min/moy/med/max (n) | Relatif au joueur | Sans niv. |
|---|---|---|---|
| Abandoned Factory | 1/13.4/8.0/55 (429) | - | 15 |
| Alien Ship | 1/1.0/1.0/1 (1) | - | 0 |
| Amusement Park | 1/23.8/10.0/80 (103) | - | 1 |
| Bunker | 10/10.0/10.0/10 (6) | - | 0 |
| City Ruins | 3/4.8/4.0/9 (17) | - | 6 |
| City Ruins (crater / underground) | 1/16.6/18.5/30 (80) | - | 3 |
| City Ruins (crater) | 1/18.5/19.0/27 (41) | - | 2 |
| Commercial Facility | 1/22.1/25.5/27 (8) | - | 0 |
| Copied City | 28/29.4/30.0/32 (13) | - | 8 |
| Desert Housing | 1/29.6/38.0/38 (17) | - | 5 |
| Desert Zone | 1/14.5/10.0/40 (126) | +3..5 | 1 |
| Flooded City | 2/17.3/18.5/27 (12) | - | 0 |
| Flooded City (sea / Grun) | 26/26.0/26.0/26 (2) | - | 0 |
| Forest Castle | 14/19.6/19.0/66 (101) | - | 53 |
| Forest Zone | 1/21.8/23.0/33 (47) | +3..5 | 5 |
| Forest Zone / Forest Castle | 6/32.0/30.0/60 (3) | - | 4 |
| Hidden underground cave (Emil's Residence route?) | 10/39.4/40.0/40 (51) | - | 0 |
| Pascal's Village | 10/10.7/10.0/30 (81) | - | 38 |
| Ravine / valley floor (谷底) | 25/27.5/27.5/30 (7) | - | 0 |
| Resistance Camp | 3/21.8/26.0/27 (26) | - | 0 |
| Resource Recovery Unit | 22/22.0/22.0/22 (2) | - | 0 |

### Route A : quetes (placements des fichiers de quete sans sous-phase)

| Quete | Nom | min/moy/med/max (n) | Boss |
|---|---|---|---|
| q000 |  | - | - |
| q005 |  | - | - |
| q031 | Machine Examination 1 | 20/20.0/20.0/20 (1) | - |
| q032 | Machine Examination 2 | 20/20.8/21.0/22 (5) | - |
| q040 | Family Squabble | 8/21.3/15.0/40 (26) | - |
| q070 | Of Machines and Beasts | 25/28.0/30.0/30 (5) | - |
| q071 | Animal Care | 30/30.0/30.0/30 (1) | - |
| q072 | Turf War | 40/40.4/40.0/44 (9) | - |
| q090 | Underground Colosseum | 10/67.4/70.0/99 (107) | - |
| q091 | Gambler's Colosseum | 20/73.3/90.0/99 (237) | emb016 80, emb016 85, em3010 95, em004d 90 |
| q092 | Trial of Sand | 15/75.7/90.0/99 (281) | - |
| q100 | Robo Dojo—White Belt | 15/17.5/17.5/20 (2) | - |
| q101 | Robo Dojo—Brown Belt | 15/20.0/15.0/30 (3) | - |
| q102 | Robo Dojo—Black Belt | 26/30.7/26.0/40 (3) | - |
| q103 | Robo Dojo—Red and White Belt | 18/28.7/18.0/50 (3) | - |
| q104 | Robo Dojo—Red Belt | 60/60.0/60.0/60 (1) | - |
| q110 | Lost Girl | 10/10.0/10.0/10 (14) | - |
| q120 | The Supply Trader's Request | 4/4.7/5.0/5 (3) | - |
| q122 | Camp Development | 20/20.0/20.0/20 (6) | - |
| q123 | Anemone's Past | 28/28.7/28.0/30 (12) | - |
| q140 | Resistance Disappearance | 30/31.6/32.0/35 (7) | - |
| q150 | Jackass's Research | 20/20.0/20.0/20 (16) | - |
| q160 | Improving Communications | 10/10.0/10.0/10 (6) | - |
| q162 | Investigating Communications | 15/16.2/17.0/17 (13) | - |
| q170 | Terminal Repairs | 22/22.0/22.0/22 (3) | - |
| q210 | Lord of the Valley | 30/34.4/32.5/50 (8) | - |
| q220 | Vanquish the Bad Bot | 50/50.0/50.0/50 (1) | - |
| q221 | Play with Us! | - | - |
| q222 | Storage Element | 49/49.6/50.0/50 (9) | - |
| q300 | Speed Star | - | - |
| q360 | In A High Place | 40/40.0/40.0/40 (3) | - |
| q400 | The Vengeful Warrior | 25/25.0/25.0/25 (7) | - |
| q440 | Treasure Hunt at the Castle | 7/18.5/18.5/30 (2) | - |
| q500 | The Wandering Couple | - | - |
| q540 | YoRHa Betrayers | 16/17.2/17.0/20 (15) | 64B 16, 22B 17 |
| q560 | Devola's Request | 50/50.0/50.0/50 (17) | - |
| q561 | Popola's Errand | 50/50.0/50.0/50 (8) | - |
| q562 | The Twins' Request | 60/60.0/60.0/60 (1) | - |
| q640 | Retrieve the Confidential Intel | 22/22.0/22.0/22 (15) | - |
| q660 | Stamp Collecting | 13/18.1/20.0/23 (36) | - |
| q680 | Parade Escort | 30/32.9/33.0/35 (34) | - |
| q720 | Gathering Keepsakes | 55/55.0/55.0/55 (2) | - |
| q800 | The Recluse | 24/24.0/24.0/24 (2) | - |
| q801 | The Recluse Stays Home | 23/23.0/23.0/23 (2) | - |
| q900 | Emil's Determination | 99/99.0/99.0/99 (1) | Emil Clones 99 |
| q910 |  | 48/48.0/48.0/48 (3) | - |
| q920 | A Steal of a Deal | 99/99.0/99.0/99 (3) | Emil 99 |
| qabd |  | 1/1.0/1.0/1 (3) | - |
| qad1 |  | - | - |
| qaeb |  | - | - |
| qb30 |  | - | Friedrich unset |
| qb31 |  | 40/40.0/40.0/40 (3) | - |
| qba0 |  | - | - |

## Route B : par chapitre

| Chapitre | Nom | Zones | Niv. prevu (StateBind) | Ennemis min/moy/med/max (n) | Sans niv. | Boss |
|---|---|---|---|---|---|---|
| 01-01 | 9S Disarms the Defense System | Abandoned Factory | 30 | 32/32.0/32.0/32 (1) | 265 | - |
| 01-02 | 9S Outside the Factory | Abandoned Factory | 30 | - | 222 | - |
| 01-03 | 9S's Aerial Combat | Abandoned Factory | 30 | 20/20.6/20.0/40 (34) | 2 | - |
| 01-04 | 9S Gets 2B Set Up | Bunker | 30 | - | 0 | - |
| 01-05 | The Mission | Bunker | 30 | - | 69 | - |
| 02-01 | Landing at the City Ruins | City Ruins, Resistance Camp | 30-31 | 40/40.0/40.0/40 (1) | 0 | - |
| 02-02 | Traveling to the Desert | Desert Zone | 33 | - | 0 | - |
| 03-01 | At the Desert | Desert Zone | 33 | 10/31.1/31.0/37 (60) | 0 | - |
| 03-02 | Desert Residential District | Desert Zone | 33 | 32/33.0/33.0/34 (55) | 1 | - |
| 03-03 | Battle with Adam | Desert Zone | 33 | 1/32.0/33.0/34 (39) | 1 | Adam (First Encounter) 1 |
| 03-04 | YoRHa Recon | Desert Zone -> Amusement Park, Pod conversation (no area) | 34 | - | 0 | - |
| 04-01 | Amusement Park | Amusement Park | 34 | - | 0 | - |
| 04-02 | Tank Boss | Amusement Park | 34 | - | 2 | em3004 unset |
| 04-03 | Advent of the Songstress | Amusement Park | 34 | 39/39.0/39.0/39 (3) | 93 | Simone 39, em3004 unset |
| 04-04 | The Messenger Arrives | Amusement Park -> Pascal's Village, City Ruins, Pascal's Village | 34 | - | 3 | - |
| 05-01 | Pascal's Village | Pascal's Village | 34 | - | 1 | - |
| 05-02 | Goliath Attack | City Ruins | 35 | 30/30.0/30.0/30 (5) | 0 | - |
| 05-03 | Alien Ship | Alien Ship, City Ruins | 37 | 13/13.3/13.0/14 (3) | 0 | - |
| 05-04 | Battle with Adam and Eve | Alien Ship, City Ruins | 37 | 16/16.0/16.0/16 (2) | 0 | Eve (Battle in the Alien Ship) 16 |
| 06-01 | Reporting to the Commander | Bunker, Pascal's Village | 37 | - | 0 | - |
| 06-02 | To the Commercial Facility | Commercial Facility (Shopping Center) | 40 | 40/40.0/40.0/40 (4) | 0 | - |
| 06-03 | Searching the Forest | Commercial Facility (Shopping Center), Forest Castle / Forest Zone | 40 | 39/40.4/39.0/46 (43) | 40 | Immanuel unset, ema020 unset |
| 06-04 | Forest Castle | Forest Castle / Forest Zone | 40 | 40/42.0/43.0/44 (5) | 9 | Immanuel unset, ema020 unset |
| 06-05 | A2's Revenge | Forest Castle / Forest Zone | 40 | 1/31.5/37.0/41 (11) | 0 | Immanuel 1, A2 41 |
| 07-01 | Reporting to Pascal | Pascal's Village, Pascal's Village -> Resistance Camp | 40 | - | 0 | - |
| 07-02 | The Aircraft Carrier | City Ruins, Flooded City, Resistance Camp -> Flooded City | 40 | 40/40.0/40.0/40 (9) | 2 | - |
| 07-03 | Battle Over the Ocean | Flooded City | 40 | 40/40.0/40.0/40 (1) | 118 | Goliath Flyer 40 |
| 07-04 | Monster | Flooded City | 40 | 10/20.0/20.0/30 (3) | 112 | Grün unset |
| 08-01 | 9S's Memory Area | Copied City | 40-42 | - | 0 | - |
| 09-01 | 9S's Data Overhaul | Bunker | 40 | - | 0 | - |
| 09-02 | 9S Supports 2B | Abandoned Factory, Bunker | 43 | 1/6.2/2.0/25 (73) | 10 | Kierkegaard 3, Kierkegaard unset, Kierkegaard 2, Kierkegaard 25 |
| 09-03 | 9S Learns the Truth | Bunker, City Ruins | 43-45 | - | 0 | - |
| 10-01 | 9S Placed in Battle | Bunker, City Ruins | 45 | 35/35.0/35.0/35 (1) | 18 | em9000 unset |
| 10-02 | Spherical Machine Battle | City Ruins | 45 | 46/46.5/46.5/47 (2) | 4 | em9000 unset, em9011 unset, em9000 47, em9010 46 |
| 10-03 | Attack on Pascal's Village | Pascal's Village | 45 | 46/46.1/46.0/47 (7) | 3 | - |
| 10-04 | Battling Eve | City Ruins | 45 | 48/48.0/48.0/48 (2) | 2 | - |
| 10-05 | The Beginning of Battle | City Ruins | 45 | - | 0 | - |

### Route B : zones du monde (placements sans sous-phase)

| Zone | min/moy/med/max (n) | Relatif au joueur | Sans niv. |
|---|---|---|---|
| Abandoned Factory | 1/16.5/11.0/55 (379) | - | 15 |
| Amusement Park | 1/39.0/34.0/80 (107) | - | 1 |
| Amusement Park (theater underground) | 34/34.0/34.0/34 (1) | - | 0 |
| Bunker | 10/10.0/10.0/10 (6) | - | 0 |
| City Ruins | 29/30.9/31.0/32 (28) | - | 6 |
| City Ruins (crater / underground) | 1/40.1/39.0/45 (64) | - | 3 |
| City Ruins (crater) | 1/31.4/39.0/45 (35) | - | 2 |
| Commercial Facility | 1/35.0/39.0/45 (9) | - | 0 |
| Copied City | 45/46.4/47.0/49 (13) | - | 8 |
| Desert Housing | 1/34.9/38.0/38 (17) | - | 5 |
| Desert Zone | 1/34.8/33.0/45 (134) | - | 1 |
| Flooded City | 2/36.0/40.0/45 (17) | - | 0 |
| Flooded City (sea / Grun) | 43/43.0/43.0/43 (4) | - | 0 |
| Forest Castle | 30/39.8/39.0/66 (78) | - | 53 |
| Forest Zone | 1/37.4/40.0/46 (65) | - | 5 |
| Forest Zone / Forest Castle | 6/32.0/30.0/60 (3) | - | 4 |
| Hidden underground cave (Emil's Residence route?) | 34/49.7/50.0/50 (51) | - | 0 |
| Pascal's Village | 10/10.7/10.0/30 (81) | - | 38 |
| Ravine / valley floor (谷底) | 37/39.5/39.5/42 (7) | - | 0 |
| Resistance Camp | 29/39.4/39.0/45 (39) | - | 0 |
| Resource Recovery Unit | 40/40.0/40.0/40 (5) | - | 0 |

### Route B : quetes (placements des fichiers de quete sans sous-phase)

| Quete | Nom | min/moy/med/max (n) | Boss |
|---|---|---|---|
| q000 |  | - | - |
| q005 |  | - | - |
| q031 | Machine Examination 1 | 40/40.0/40.0/40 (1) | - |
| q032 | Machine Examination 2 | 40/40.8/41.0/42 (5) | - |
| q040 | Family Squabble | 8/30.1/40.0/45 (26) | - |
| q070 | Of Machines and Beasts | 25/35.2/30.0/48 (5) | - |
| q071 | Animal Care | 30/30.0/30.0/30 (1) | - |
| q072 | Turf War | 40/40.4/40.0/44 (9) | - |
| q090 | Underground Colosseum | 10/67.4/70.0/99 (107) | - |
| q091 | Gambler's Colosseum | 20/73.3/90.0/99 (237) | emb016 80, emb016 85, em3010 95, em004d 90 |
| q092 | Trial of Sand | 15/75.7/90.0/99 (281) | - |
| q100 | Robo Dojo—White Belt | 20/30.0/30.0/40 (2) | - |
| q101 | Robo Dojo—Brown Belt | 30/36.7/40.0/40 (3) | - |
| q102 | Robo Dojo—Black Belt | 40/44.0/46.0/46 (3) | - |
| q103 | Robo Dojo—Red and White Belt | 48/48.7/48.0/50 (3) | - |
| q104 | Robo Dojo—Red Belt | 60/60.0/60.0/60 (1) | - |
| q110 | Lost Girl | 10/10.0/10.0/10 (14) | - |
| q120 | The Supply Trader's Request | 31/31.7/32.0/32 (3) | - |
| q122 | Camp Development | 40/40.0/40.0/40 (6) | - |
| q123 | Anemone's Past | 38/38.7/38.0/40 (12) | - |
| q140 | Resistance Disappearance | 30/31.6/32.0/35 (7) | - |
| q160 | Improving Communications | 30/30.0/30.0/30 (6) | - |
| q162 | Investigating Communications | 35/36.2/37.0/37 (13) | - |
| q180 | Data Analysis Freak | 35/36.0/35.0/38 (3) | - |
| q210 | Lord of the Valley | 40/43.1/42.5/50 (8) | - |
| q220 | Vanquish the Bad Bot | 50/50.0/50.0/50 (1) | - |
| q221 | Play with Us! | - | - |
| q222 | Storage Element | 49/49.6/50.0/50 (9) | - |
| q250 | Idiot Savant | 20/21.5/21.5/23 (4) | - |
| q290 | Game Dev Machine Lv.1 | 35/37.7/38.0/40 (3) | - |
| q300 | Speed Star | - | - |
| q360 | In A High Place | 40/40.0/40.0/40 (3) | - |
| q400 | The Vengeful Warrior | 25/25.0/25.0/25 (7) | - |
| q440 | Treasure Hunt at the Castle | 7/27.5/27.5/48 (2) | - |
| q500 | The Wandering Couple | - | - |
| q540 | YoRHa Betrayers | 38/38.8/39.0/40 (15) | 64B 38, 22B 39 |
| q560 | Devola's Request | 50/50.0/50.0/50 (17) | - |
| q561 | Popola's Errand | 50/50.0/50.0/50 (8) | - |
| q562 | The Twins' Request | 60/60.0/60.0/60 (1) | - |
| q640 | Retrieve the Confidential Intel | 40/40.0/40.0/40 (15) | - |
| q660 | Stamp Collecting | 30/38.8/42.0/44 (36) | - |
| q680 | Parade Escort | 30/32.9/33.0/35 (34) | - |
| q720 | Gathering Keepsakes | 55/55.0/55.0/55 (2) | - |
| q800 | The Recluse | 24/24.0/24.0/24 (2) | - |
| q801 | The Recluse Stays Home | 23/23.0/23.0/23 (2) | - |
| q900 | Emil's Determination | 99/99.0/99.0/99 (1) | Emil Clones 99 |
| q910 |  | 48/48.0/48.0/48 (3) | - |
| q920 | A Steal of a Deal | 99/99.0/99.0/99 (3) | Emil 99 |
| qabd |  | 1/1.0/1.0/1 (3) | - |
| qad1 |  | - | - |
| qaeb |  | - | - |
| qb30 |  | - | Friedrich unset |
| qb31 |  | 40/40.0/40.0/40 (3) | - |
| qba0 |  | - | - |

## Route C/D : par chapitre

| Chapitre | Nom | Zones | Niv. prevu (StateBind) | Ennemis min/moy/med/max (n) | Sans niv. | Boss |
|---|---|---|---|---|---|---|
| ? |  | Bunker | 47 | - | 0 | - |
| 11-01 | 2B's Invasion Begins | Bunker | 47 | - | 0 | - |
| 11-02 | 9S Hacks the Defense System | Bunker -> City Ruins, City Ruins | 47 | 45/49.4/50.0/57 (8) | 106 | - |
| 11-03 | 2B's Battle for Control | City Ruins | 47 | 20/44.4/47.0/60 (71) | 0 | - |
| 11-04 | Contaminated YoRHa | City Ruins | 47 | 20/43.0/48.0/53 (54) | 0 | - |
| 11-05 | 2B Escapes the Bunker | Bunker | 47 | 40/46.5/47.0/47 (52) | 1 | - |
| 11-06 | 2B's Final Moments | City Ruins, Flooded City | 47 | 47/47.0/47.0/47 (14) | 9 | - |
| 11-07 | 9S Gets Separated | City Ruins, Pod conversation (no area) | 47 | - | 0 | - |
| 12-01 | A2 Awakens | City Ruins | 48 | - | 0 | - |
| 12-02 | A2's Battle in the Desert | Desert Zone | 48 | 48/48.0/48.0/48 (4) | 1 | Hegel unset, Hegel 48 |
| 13-01 | 9S Awakens | Resistance Camp | 49 | - | 0 | - |
| 13-02 | 9S Accesses the Tower | City Ruins | 49 | - | 0 | - |
| 13-03 | 9S's Determination | Forest Castle / Forest Zone | 49 | - | 0 | - |
| 13-04 | 9S and the Meat Box | Forest Castle / Forest Zone, Pod conversation (no area) | 49 | 40/46.5/48.0/48 (49) | 0 | - |
| 14-01 | A2 and the Oil Filter | Desert Zone -> Resistance Camp, Pascal's Village | 49 | 48/48.1/48.0/49 (8) | 0 | - |
| 14-02 | A Day in the Life of Pascal | Pascal's Village | 49 | - | 0 | - |
| 14-03 | Pascal Needs Help | Pascal's Village | 49 | - | 0 | - |
| 14-04 | Cannibal Machines | Pascal's Village | 49 | 30/46.6/49.0/49 (16) | 0 | - |
| 14-05 | A2 and the Children | Abandoned Factory, Pod conversation (no area) | 49 | 1/28.0/21.0/70 (105) | 335 | em011e unset, Goliath Tank 49 |
| 15-01 | 9S Continues Fighting | Forest Castle / Forest Zone | 49 | - | 0 | - |
| 15-02 | 9S and the Soul Box | Flooded City, Hacking space, Pod conversation (no area) | 49-50 | 50/50.0/50.0/50 (1) | 0 | - |
| 15-03 | 9S Wounded | Resistance Camp | 50 | - | 0 | - |
| 15-04 | 9S Repaired | Resistance Camp | 50 | - | 0 | - |
| 16-01 | A2 and the Resource Unit | Abandoned Factory, Resistance Camp -> Amusement Park | 49-50 | - | 0 | - |
| 16-02 | 9S and the God Box | Amusement Park | 50 | 50/50.2/50.0/60 (45) | 0 | 21O 60 |
| 16-03 | A2 and the Machine Siblings | Amusement Park | 50 | 50/50.4/50.0/60 (24) | 1 | Friedrich 50, Auguste 60 |
| 17-01 | 9S Heads to the Tower | Amusement Park, City Ruins, Tower | 50 | 40/44.4/45.0/49 (30) | 0 | - |
| 17-02 | 9S Searches the Tower | Tower | 50 | 48/48.6/48.0/55 (20) | 0 | 2B Copy 48 |
| 17-03 | A2 Heads to the Tower | City Ruins | 50 | - | 0 | - |
| 17-04 | A2 Searches the Tower | Tower | 50 | - | 0 | - |
| 17-05 | 9S Self-repairs | Tower | 50 | 50/50.0/50.0/50 (21) | 3 | Red Girl unset |
| 17-06 | The Red Girls | Tower | 50 | 40/48.6/50.0/60 (36) | 24 | - |
| 17-07 | To the Peak | Tower | 50 | 45/51.5/50.0/60 (31) | 40 | Ko-Shi 60, Ko-Shi 50, Ro-Shi 60 |
| 17-08 | Combined Multi-leg Machine | Tower | 50 | 60/60.0/60.0/60 (1) | 0 | Ko-Shi & Ro-shi 60 |
| 17-09 | 9S and A2 | Tower | 50 | 50/50.0/50.0/50 (2) | 0 | A2 50, 9S 50 |
| 17-10 | 9S's Final Moments | Tower | 50 | 50/50.0/50.0/50 (2) | 0 | A2 50, 9S 50 |

### Route C/D : zones du monde (placements sans sous-phase)

| Zone | min/moy/med/max (n) | Relatif au joueur | Sans niv. |
|---|---|---|---|
| Abandoned Factory | 1/26.3/25.0/65 (506) | +60..64 | 15 |
| Amusement Park | 1/48.1/48.0/80 (107) | - | 1 |
| Amusement Park (theater underground) | 48/48.0/48.0/48 (1) | - | 0 |
| Bunker | 10/10.0/10.0/10 (6) | - | 0 |
| City Ruins | - | - | 6 |
| City Ruins (crater / underground) | 1/45.7/46.5/53 (51) | - | 3 |
| City Ruins (crater) | 1/38.3/46.5/53 (42) | - | 2 |
| Commercial Facility | 1/1.0/1.0/1 (1) | - | 0 |
| Copied City | 60/61.5/62.0/65 (13) | - | 8 |
| Desert Housing | 1/39.8/38.0/50 (22) | - | 5 |
| Desert Zone | 1/44.8/47.0/53 (120) | - | 1 |
| Flooded City | 2/43.6/50.0/50 (17) | - | 0 |
| Flooded City (sea / Grun) | 48/50.6/52.0/52 (7) | - | 0 |
| Forest Castle | 18/45.7/47.0/66 (68) | - | 53 |
| Forest Zone | 1/45.4/47.0/66 (74) | - | 5 |
| Forest Zone / Forest Castle | 6/32.0/30.0/60 (3) | - | 4 |
| Hidden underground cave (Emil's Residence route?) | 48/59.8/60.0/60 (51) | - | 0 |
| Pascal's Village | 10/10.7/10.0/30 (80) | - | 38 |
| Ravine / valley floor (谷底) | 42/45.0/45.0/48 (6) | - | 0 |
| Resistance Camp | 45/48.0/46.5/53 (24) | - | 0 |
| Resource Recovery Unit | 50/50.0/50.0/50 (5) | - | 0 |

### Route C/D : quetes (placements des fichiers de quete sans sous-phase)

| Quete | Nom | min/moy/med/max (n) | Boss |
|---|---|---|---|
| q000 |  | - | - |
| q005 |  | - | - |
| q031 | Machine Examination 1 | 40/40.0/40.0/40 (1) | - |
| q032 | Machine Examination 2 | 40/40.8/41.0/42 (5) | - |
| q040 | Family Squabble | 8/30.1/40.0/45 (26) | - |
| q070 | Of Machines and Beasts | 25/35.2/30.0/48 (5) | - |
| q071 | Animal Care | 30/30.0/30.0/30 (1) | - |
| q072 | Turf War | 40/40.4/40.0/44 (9) | - |
| q090 | Underground Colosseum | 10/67.4/70.0/99 (107) | - |
| q091 | Gambler's Colosseum | 20/73.3/90.0/99 (237) | emb016 80, emb016 85, em3010 95, em004d 90 |
| q092 | Trial of Sand | 15/75.7/90.0/99 (281) | - |
| q100 | Robo Dojo—White Belt | 20/30.0/30.0/40 (2) | - |
| q101 | Robo Dojo—Brown Belt | 30/36.7/40.0/40 (3) | - |
| q102 | Robo Dojo—Black Belt | 40/44.0/46.0/46 (3) | - |
| q103 | Robo Dojo—Red and White Belt | 48/48.7/48.0/50 (3) | - |
| q104 | Robo Dojo—Red Belt | 60/60.0/60.0/60 (1) | - |
| q110 | Lost Girl | 10/10.0/10.0/10 (14) | - |
| q120 | The Supply Trader's Request | 31/31.7/32.0/32 (3) | - |
| q122 | Camp Development | 40/40.0/40.0/40 (6) | - |
| q123 | Anemone's Past | 38/38.7/38.0/40 (12) | - |
| q140 | Resistance Disappearance | 30/31.6/32.0/35 (7) | - |
| q160 | Improving Communications | 30/30.0/30.0/30 (6) | - |
| q162 | Investigating Communications | 35/36.2/37.0/37 (13) | - |
| q210 | Lord of the Valley | 40/43.1/42.5/50 (8) | - |
| q220 | Vanquish the Bad Bot | 50/50.0/50.0/50 (1) | - |
| q221 | Play with Us! | - | - |
| q222 | Storage Element | 49/49.6/50.0/50 (9) | - |
| q300 | Speed Star | - | - |
| q360 | In A High Place | 40/40.0/40.0/40 (3) | - |
| q400 | The Vengeful Warrior | 25/25.0/25.0/25 (7) | - |
| q440 | Treasure Hunt at the Castle | 7/33.5/33.5/60 (2) | - |
| q500 | The Wandering Couple | - | - |
| q540 | YoRHa Betrayers | 38/38.8/39.0/40 (15) | 64B 38, 22B 39 |
| q560 | Devola's Request | 50/50.0/50.0/50 (17) | - |
| q561 | Popola's Errand | 50/50.0/50.0/50 (8) | - |
| q562 | The Twins' Request | 60/60.0/60.0/60 (1) | - |
| q640 | Retrieve the Confidential Intel | 40/40.0/40.0/40 (15) | - |
| q660 | Stamp Collecting | 30/38.8/42.0/44 (36) | - |
| q680 | Parade Escort | 30/32.9/33.0/35 (34) | - |
| q720 | Gathering Keepsakes | 55/55.0/55.0/55 (2) | - |
| q800 | The Recluse | 24/24.0/24.0/24 (2) | - |
| q801 | The Recluse Stays Home | 23/23.0/23.0/23 (2) | - |
| q900 | Emil's Determination | 99/99.0/99.0/99 (1) | Emil Clones 99 |
| q910 |  | 48/48.0/48.0/48 (3) | - |
| q920 | A Steal of a Deal | 99/99.0/99.0/99 (3) | Emil 99 |
| qabd |  | 1/1.0/1.0/1 (3) | - |
| qad1 |  | - | - |
| qaeb |  | - | - |
| qb30 |  | - | Friedrich unset |
| qb31 |  | 40/40.0/40.0/40 (3) | - |
| qba0 |  | - | - |

## Courbe recommandee (niveau du joueur par etape)

Niveau = 'Level' de StateBind (prevu par les concepteurs) ; a defaut mediane des ennemis de l'etape.

- **A** : 01-01:1 -> 01-02:2 -> 01-02:3 -> 02-01:4 -> 02-02:7 -> 03-04:10 -> 05-02:12 -> 05-03:15 -> 06-02:19 -> 07-01:22 -> 08-01:24 -> 09-01:25 -> 09-03:28
- **B** : 01-01:30 -> 02-01:31 -> 02-02:33 -> 03-04:34 -> 05-02:35 -> 05-03:37 -> 06-02:40 -> 08-01:42 -> 09-01:40 -> 09-02:43 -> 09-03:45
- **C/D** : ?:47 -> 12-01:48 -> 13-01:49 -> 15-02:50 -> 16-01:49 -> 16-01:50

## Simulation d'EXP (ennemis poses des sous-phases seulement, borne basse)

| Route | EXP debut -> fin | Niveau fin | Niveau en fin de chapitre |
|---|---|---|---|
| A | 0 -> 36986 | 25 | 01-01:1, 01-02:4, 01-03:6, 01-04:6, 01-05:6, 02-01:10, 02-02:10, 03-01:10, 03-02:11, 03-03:11, 03-04:11, 04-01:11, 04-02:11, 04-03:14, 04-04:14, 05-01:14, 05-02:14, 05-03:14, 05-04:15, 06-01:15, 06-02:15, 06-03:16, 06-04:16, 06-05:17, 07-01:17, 07-02:17, 07-03:18, 07-04:18, 08-01:20, 09-01:22, 09-02:23, 09-03:23, 10-01:24, 10-02:25, 10-03:25, 10-04:25, 10-05:25 |
| B | 36986 -> 88628 | 35 | 01-01:25, 01-02:25, 01-03:26, 01-04:26, 01-05:26, 02-01:26, 02-02:26, 03-01:27, 03-02:28, 03-03:28, 03-04:28, 04-01:28, 04-02:28, 04-03:30, 04-04:30, 05-01:30, 05-02:31, 05-03:31, 05-04:32, 06-01:32, 06-02:32, 06-03:33, 06-04:33, 06-05:33, 07-01:33, 07-02:33, 07-03:34, 07-04:34, 08-01:34, 09-01:34, 09-02:34, 09-03:34, 10-01:34, 10-02:35, 10-03:35, 10-04:35, 10-05:35 |
| C/D | 88628 -> 241605 | 52 | None:35, 11-01:35, 11-02:36, 11-03:37, 11-04:39, 11-05:41, 11-06:41, 11-07:41, 12-01:41, 12-02:41, 13-01:41, 13-02:41, 13-03:41, 13-04:42, 14-01:43, 14-02:43, 14-03:43, 14-04:43, 14-05:45, 15-01:45, 15-02:45, 15-03:45, 15-04:45, 16-01:45, 16-02:46, 16-03:46, 17-01:47, 17-02:47, 17-03:47, 17-04:47, 17-05:48, 17-06:49, 17-07:52, 17-08:52, 17-09:52, 17-10:52 |

## Joueur (pl0000ExpInfo.csv)

| Niv. | EXP cumulee | PV | col2 | col3 | EXP vers suivant | EXP/kill med. (meme niv.) | kills |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 800 | 500 | 100 | 48 | 16 | 3.0 |
| 2 | 48 | 954 | 597 | 120 | 91 | 19 | 4.8 |
| 3 | 139 | 1058 | 664 | 135 | 155 | 31 | 5.0 |
| 5 | 525 | 1212 | 764 | 160 | 318 | 59 | 5.4 |
| 7 | 1259 | 1333 | 845 | 184 | 523 | 91 | 5.7 |
| 10 | 3184 | 1489 | 955 | 223 | 896 | 142 | 6.3 |
| 15 | 9139 | 1724 | 1133 | 299 | 1670 | 236 | 7.1 |
| 20 | 19309 | 1958 | 1324 | 393 | 2611 | 338 | 7.7 |
| 25 | 34493 | 2205 | 1534 | 507 | 3703 | 447 | 8.3 |
| 30 | 55412 | 2472 | 1770 | 643 | 4931 | 561 | 8.8 |
| 35 | 82730 | 2762 | 2032 | 800 | 6287 | 681 | 9.2 |
| 40 | 117070 | 3078 | 2324 | 978 | 7762 | 804 | 9.7 |
| 45 | 159016 | 3422 | 2645 | 1179 | 9352 | 932 | 10.0 |
| 50 | 209127 | 3793 | 2996 | 1402 | 11050 | 1063 | 10.4 |
| 55 | 267937 | 4195 | 3378 | 1647 | 12851 | 1198 | 10.7 |
| 60 | 335956 | 4626 | 3791 | 1914 | 14753 | 1335 | 11.1 |
| 70 | 501585 | 5580 | 4712 | 2516 | 18844 | 1619 | 11.6 |
| 80 | 709780 | 6659 | 5762 | 3208 | 23299 | 1914 | 12.2 |
| 90 | 964096 | 7864 | 6940 | 3989 | 28100 | 2217 | 12.7 |
| 99 | 1235211 | 9057 | 8111 | 4770 | - | - | - |

## Armes (WeaponParam.csv)

| Arme | Type | Lv1 atk | Lv4 atk | Indice Lv1 | Tier | Sources (donnees) | Web (plus tot) |
|---|---|---|---|---|---|---|---|
| Angel's Folly | combat bracers | 150-165 | 570-627 | 1.145 | high | shop Emil's Item Shop | A Ch06/07 |
| Type-4O Fists | combat bracers | 140-150 | 532-570 | 1.055 | high | box st1/r110.dat | B Ch02 |
| Demon's Cry | combat bracers | 100-180 | 380-684 | 1.018 | mid | box st5/r530.dat | B Ch04 |
| Type-3 Fists | combat bracers | 110-170 | 418-646 | 1.018 | mid | shop Emil's Item Shop | A Ch06/07 |
| Virtuous Grief | combat bracers | 120-150 | 456-570 | 0.982 | mid | box st1/r160.dat | A Ch06 |
| Cruel Lament | combat bracers | 120-150 | 456-570 | 0.982 | mid | quest st1/r160.dat | A Ch06+ |
| Machine Heads | combat bracers | 110-160 | 418-608 | 0.982 | mid | shop Pascal's Shop | C Ch15 |
| Emil Heads | combat bracers | 120-150 | 456-570 | 0.982 | mid | box quest/q920.dat | after Emil's Memories |
| Beastlord | large sword | 320-350 | 1216-1330 | 1.063 | high | shop Camp Weapons Trader | A Ch02 |
| Iron Will | large sword | 250-400 | 950-1520 | 1.032 | mid | box st1/r170.dat | after A170 |
| Type-4O Blade | large sword | 320-330 | 1216-1254 | 1.032 | mid | quest q181 Data Analysis Freak 2 | B |
| Type-3 Blade | large sword | 280-360 | 1064-1368 | 1.016 | mid | shop Devola's Item Shop | C/D (GP) (?) |
| Fang of the Twins | large sword | 310-320 | 1178-1216 | 1.0 | mid | box st1/r150.dat | A Ch03 |
| Virtuous Treaty | large sword | 300-330 | 1140-1254 | 1.0 | mid | box st1/r120.dat | A (?) |
| Cruel Blood Oath | large sword | 300-330 | 1140-1254 | 1.0 | mid | box st1/r150.dat | B Ch03 |
| Machine Axe | large sword | 280-350 | 1064-1330 | 1.0 | mid | shop Castle Blacksmith; shop Village Weapons Trader | A Ch05 |
| Phoenix Sword | large sword | 270-340 | 1026-1292 | 0.968 | mid | box core/corehap.dat | B Ch02 |
| Beastbane | small sword | 190-210 | 722-798 | 1.194 | high | shop Camp Weapons Trader | A Ch02 |
| Engine Blade | small sword | 160-200 | 608-760 | 1.075 | high | box st5/r520.dat | A Ch09 |
| Faith | small sword | 160-190 | 608-722 | 1.045 | mid | BoxData 0x6 (non place); BoxData 0xa14 (non place) | C Ch15 |
| Type-4O Sword | small sword | 170-180 | 646-684 | 1.045 | mid | quest q171 Find a Present | A Ch07 (2B) |
| Type-3 Sword | small sword | 130-220 | 494-836 | 1.045 | mid | shop Devola's Item Shop | C/D (GP) (?) |
| Machine Sword | small sword | 140-210 | 532-798 | 1.045 | mid | shop Castle Blacksmith; shop Village Weapons Trader | A Ch05 |
| Ancient Overlord | small sword | 150-185 | 570-703 | 1.0 | mid | shop Camp Weapons Trader | A Ch02 |
| Virtuous Contract | small sword | 150-180 | 570-684 | 0.985 | mid | initial_equipment | A |
| Cruel Oath | small sword | 150-180 | 570-684 | 0.985 | mid | initial_equipment | B |
| YoRHa-issue Blade | small sword | 150-180 | 570-684 | 0.985 | mid | quest q410 11B's Memento | A (2B) |
| Phoenix Dagger | small sword | 130-190 | 494-722 | 0.955 | mid | box core/corehap.dat | A Ch06 |
| Iron Pipe | small sword | 30-220 | 114-836 | 0.746 | low | fishing | A Ch04 |
| Cypress Stick | small sword | 60-80 | 228-304 | 0.418 | low | box st1/r160.dat | A Ch06 |
| Dragoon Lance | spear | 250-260 | 950-988 | 1.062 | high | box st1/r160.dat | A Ch06 |
| Beastcurse | spear | 240-265 | 912-1007 | 1.052 | high | box st1/r160.dat | B Ch06 |
| Spear of the Usurper | spear | 220-270 | 836-1026 | 1.021 | mid | quest q590 Heritage of the Past | after Ch08 |
| Type-4O Lance | spear | 240-250 | 912-950 | 1.021 | mid | quest q540 YoRHa Betrayers | A/B |
| Type-3 Lance | spear | 200-280 | 760-1064 | 1.0 | mid | box st1/r170.dat | A Ch07 |
| Machine Spear | spear | 210-260 | 798-988 | 0.979 | mid | shop Castle Blacksmith; shop Village Weapons Trader | A Ch05 |
| Phoenix Lance | spear | 210-250 | 798-950 | 0.958 | mid | box st1/r150.dat | B Ch03 (after the Scanner) |
| Virtuous Dignity | spear | 220-240 | 836-912 | 0.958 | mid | box st1/r130.dat | A Ch04 |
| Cruel Arrogance | spear | 220-240 | 836-912 | 0.958 | mid | box st5/r520.dat | C/D |
