# Chargement des salles (st*/rXXX) et des unites (wd*/gXXXXX) - NieR:Automata v1.04 Steam

Analyse **statique** de `NieRAutomata.exe` + `data/*.cpk` (jeu jamais attache, rien ecrit, aucun appel distant).
Adresses = RVA (base 0x140000000). Outils : `tools/xref.py` + capstone, `tools/cpk.py`, `tools/world_positions.py`,
`tools/areas.py`, unicorn (emulation de 0x7c49f0 / 0x7c3260 / 0x7eeee0 pour convertir une position en unite et salle).
**Rien n'a ete execute** : la section 9 liste ce qui doit etre controle en jeu.

Confiance : **haute** = lu dans le desassemblage et recoupe par les donnees ; **moyenne** = lu dans le desassemblage
seul, ou donnees seules ; **faible** = deduit.

## Resume pour le client

| Constat | Confiance |
|---|---|
| Une salle `stX/rXXX.dat` n'est jamais chargee pour elle-meme : elle est demandee par le chargement d'une **unite de monde** `wdW/gWXXZZ.dat` (table unite -> salle 0xf5e8d0, ou `salle = unite >> 8` pour les unites 0x5xxxx) | haute |
| En monde ouvert (mode "seamless", `[0x12504ac] == 1`) les 7 unites chargees sont la cellule hexagonale du joueur et ses 6 voisines : seules des unites `g1XXZZ` / `g3XXZZ` (wd1 / wd3), donc seulement les salles r100..r170 et r200 | haute |
| Les unites **wd5** (`g50001` r500, `g50100` r501, `g50200` r502, `g50300` r503, `g52001` r520, `g53001` r530, `g5aX00`...) ne sont **jamais** chargees par la position. Elles le sont seulement en mode "liste fixe" (`[0x12504ac] == 0`) : sous-phase dont `RoomNo` = `gXXXXX`, ascenseur "LOOP" (ba0200), voyage rapide ft_RMI / ft_RMI2, reprise de sauvegarde dans la Tour | haute |
| Teleporter le joueur sur un coffre de r500/r501/r502/r503/r520/r530 charge donc les cellules de la ville, de l'usine ou du parc qui sont **au-dessus**, pas la salle du coffre : c'est la cause des coffres introuvables de ces salles | haute |
| r100 n'existe qu'en phase p100, r200 dans toutes les autres : les memes cellules de ville donnent 0x100 ou 0x200 selon la phase (0x7eeee0) | haute |
| Les coffres de r110/r120/r130/r140/r150/r160/r170 sont dans des cellules qui chargent bien leur salle (206 coffres st* testes) : s'ils manquent, la cause est une condition de groupe hap (section 7) ou un delai de chargement, pas la salle | haute (calcul), cause reelle non verifiee |

| Besoin | Solution | Confiance |
|---|---|---|
| Charger une unite wd5 + sa salle comme le jeu | Ecrire le **demandeur d'unites fixes** `0x11eabd0` : `wanted[8]` (0x11eabf4..0x11eac10) = {unite, -1 x7}, `[0x11eac14] = 1`, puis `[0x11eabd0] = 1`. C'est exactement ce que font le voyage rapide ft_RMI (0x2fe9b2) et les ascenseurs (0x8292ae, 0x82a141, 0x82a881) | haute (mecanisme), ecriture externe non verifiee |
| Revenir au monde ouvert | `[0x11eabd0] = 6` (0x815830) quand l'etat vaut 5 | haute (mecanisme) |
| Charger seulement la salle (haps, donc coffres) sans la geometrie | `0x7c7020(ecx = id d'unite)` (ex. 0x50200) ; liberer par `0x7c6ee0(ecx = id d'unite)`. Employe par le jeu pour r550 / r551 (0x3487ea, 0x858fb9) | moyenne (jamais employe par le jeu pour r500..r530) |
| Savoir que c'est charge | demandeur `[0x11eabd0] == 5` **et** une entree de la table des salles `0x130c890` avec `roomNo == salle` et `etat == 4` | moyenne |
| Savoir que le monde ouvert a fini de charger apres une teleportation | `[0x12504bc] == 0` et `[0x1255818] == 1` et `[0x1255978] == 1` et `[0x124e218] == 1` (predicat 0x7c58b0) | moyenne |

## 1. Unites de monde et mode de chargement - confiance haute

### Identifiants

`wd%x\g%x%04x.dat` (chaine 0xce5950, ouverte par 0x840570 / 0x831e1e) : unite = `(W << 16) | 0xXXZZ`.

- W = 1 (wd1) : cellule de la grille hexagonale, XX et ZZ en decimal code hexa (cellule (13, 18) -> `g11318`).
- W = 3 (wd3) : variante "apres effondrement" des 18 cellules du centre-ville. 0x7c3260(x, z, 1) renvoie
  `0x30000 | cellule` si la cellule est dans la liste 0xce0690 (0x1118..0x1121, 0x1217..0x1221, 0x1317..0x1320,
  0x1416..0x1419, 0x1518) **et** que `(phase & 0xf00)` vaut 0x200..0x900 sauf 0x400 ; sinon `0x10000 | cellule`.
- W = 2, 4 : basse definition (second gestionnaire 0x1255960), sans salle (0x7c69f0 les ignore).
- W = 5 (wd5) : interieurs. Fichiers presents : g50001, g50010, g50100, g50200, g50300, g52001, g53001, g5a000,
  g5a001, g5a002, g5a100, g5a200, g5a300, g5a400, g5a500, g5a800, g5a900, g5aa00, g5ab00, g5ac00, g5f000, g5f001.
- W = 0xa (wda) : ga0001, ga0002, toujours demandees (0x7c8a3a).

Position -> cellule : 0x7c49f0(out, &x, &z, pos) (grille hexagonale, y ignore). Voisinage du gestionnaire 1
(decalages axiaux ecrits par 0x7c7778.. dans 0x1255880 + 0x20 * i) : (0,0), (0,-1), (-1,0), (-1,1), (0,1), (1,0),
(1,-1).

### Les deux modes

`u32 [0x12504ac]` : **1 = seamless** (unites choisies par la position), **0 = liste fixe**.
Changement : `0x7c7260(ecx = mode)` vide les unites voulues de tous les emplacements, pose `[0x12504b8] = mode`,
`[0x12504bc] = 1` (en attente) ; applique par 0x7c8aa7..0x7c8c4e quand tout est decharge (`[0x12504ac] = [0x12504b8]`,
`[0x12504bc] = 0`).

Boucle du monde 0x7c86c0 (appelee a chaque image depuis 0x7632f5) :

- centre de chargement = `vec4 0x1255760`, recopie de la position du joueur a chaque image par 0x7c8c70..0x7c8d60
  (sauf si `[0x1029b30] & 0x4000` ou `[0x11e1f88] == 0`). **Ecrire la position du joueur suffit donc a deplacer le
  chargement** en mode seamless.
- mode 1 : cellule du centre -> `0x815840(0x1255800, 0x1255ac0, cellule)` ecrit l'unite voulue des 7 emplacements
  (centre + 6 voisines, `0x7c3260(x + dx, z + dz, 1)`).
- mode 0 : les emplacements ne sont ecrits que par `0x7c7140(ecx = indice, edx = unite, r8 = vec4*)` (refuse si
  mode 1) et effaces par `0x7c4250(ecx = indice)`.

Gestionnaire 1 = objet `0x1255800` : `[0x1255808]` pointeur des emplacements (0x50 o), `[0x1255810]` nombre (7),
`[0x1255814]` actif, `[0x1255818]` = 1 quand tous les emplacements sont stables. Emplacement : `+8` unite courante,
`+0xc` unite voulue (-1 = aucune), `+0x10` vec4 de decalage, `+0x20`, `+0x38` etat.
Noeud d'unite (0x58 o, automate 0x8317a0) : `+0x20` etat (1 ouverture des fichiers, 2 attente, 3 -> **0x7c69f0**
(inscription + demande de salle), 4 -> pret quand `0x7c5430(unite)`, 5 charge, 6 -> **0x7c6c30** (liberation de la
salle), 7), `+0x38` id d'unite, `+0x40` compteur.

Au demarrage d'une phase (0x855620) : si la sous-phase a une liste d'unites (`RoomNo`, 8 jetons au plus, analyse
0x85d2de : texte apres `g` lu en hexa, `r001` = pas d'unite) -> mode 0 puis `0x7c7140(i, unite, vec)` pour chaque
entree de `0x13ecfd4` (nombre `0x13ecff4`) ; sinon mode 1. Reprise de sauvegarde (bit 29 de `[0x14958b0]`) : point de
reprise `re_tower_start` / `re_tower_cathedral` / `re_tower_library` / `re_tower_elevator` -> unite 0x50001 ;
`ft_RMI` / `ft_RMI2` -> 0x52001 (0x85577d..0x85582d).

## 2. Salles - confiance haute

### Unite -> salle : `0x7eeee0(ecx = unite, edx = phase)`

- unite dans 0x50000..0x5ffff : `salle = unite >> 8` (g50200 -> 0x502, g52001 -> 0x520, g55100 -> 0x551).
- sinon table `0xf5e8d0` (9 entrees de 0x84 o : `u32 salle`, 16 x `{u32 debut, u32 fin}`) :

| Salle | Plages d'unites |
|---|---|
| 0x100 | 0x11019-0x11023, 0x11118-0x11123, 0x11216-0x11222, 0x11315-0x11321, 0x11415-0x11419, 0x11518 |
| 0x110 | 0x11420 |
| 0x120 | 0x10622-0x10626, 0x10721-0x10726, 0x10820-0x10832, 0x10920-0x10932, 0x11024-0x11032 |
| 0x130 | 0x11517, 0x11616-0x11618, 0x11715-0x11718, 0x11815-0x11818, 0x11914-0x11917, 0x12014-0x12016 |
| 0x140 | 0x11515-0x11516, 0x11615 |
| 0x150 | 0x10118-0x10119, 0x10217-0x10222, 0x10316-0x10322, 0x10415-0x10422, 0x10514-0x10522, 0x10613-0x10621, 0x10712-0x10720, 0x10811-0x10819, 0x10911-0x10919, 0x11010-0x11018, 0x11110-0x11117, 0x11209-0x11215, 0x11309-0x11313 |
| 0x160 | 0x11314, 0x11409-0x11414, 0x11508-0x11514, 0x11608-0x11614, 0x11708-0x11714, 0x11808-0x11814, 0x11908-0x11913, 0x12008-0x12013, 0x12108-0x12112 |
| 0x170 | 0x11223-0x11227, 0x11322-0x11327, 0x11421-0x11426, 0x11519-0x11526, 0x11619-0x11625, 0x11719-0x11725, 0x11819-0x11824, 0x11918-0x11924, 0x12018-0x12023, 0x12119-0x12122 |
| 0x200 | 0x31019-0x31023, 0x31118-0x31123, 0x31216-0x31222, 0x31315-0x31321, 0x31415-0x31419, 0x31518 |

- cas particulier : resultat 0x100 et phase ni -1, ni 0x100, ni 0x90 -> **0x200**. La ville est donc r100 en p100
  et r200 en p200 / p300 (y compris pour les cellules de ville restees en wd1, ex. 0x11315).

### Table des salles chargees : `0x130c890`, 16 entrees de 0x178 o

| Offset | Contenu |
|---|---|
| +0 | u32 numero de salle (0x502 = r502) |
| +4 | u32 etat : 0 libre, 1 demandee, 2 fichiers en lecture, 3 initialisation (0x809470, sous-etapes en +0xac), **4 active**, 5 dechargement (0x800200), 6 liberation (compte a rebours +0xa4) |
| +8 | donnees du .dat / .dtt |
| +0x18, +0x58 | chemins `st%1x/r%03x.dat` (0xce6f50) et `.dtt` (0xce6f60) : `st = salle >> 8`, `r = salle & 0xfff` |
| +0x98, +0x9c | poignees de fichier |
| +0xa0 | dechargement demande pendant le chargement |
| +0xa8 | compteur de references (une par unite chargee) |

Automate : 0x82f680, a chaque image (0x7632fa). A la fin de la lecture (etat 2 -> 3) le message
`cRoomReadInfo` (0x7c0140 sur 0x1274510) fait charger `r%03x_hap.pak` par le systeme hap (0x3006b0, 0x345c3e).

- **Demande** : `0x7c7020(ecx = id d'unite)` : `salle = 0x7eeee0(unite, [0xf64b18])` ; si `0x81bdd0(salle) == 0` :
  entree existante -> `+0xa8 += 1`, sinon premiere entree libre : `+0 = salle`, `+4 = 1`, `+0xa8 += 1`.
  Meme code en ligne dans 0x7c69f0 (inscription d'une unite, 0x7c6b37..0x7c6bcc). Appels directs : 0x3487ea
  (0x55000, salle de piratage, avec `[0x1029b00] |= 0x400000`) et 0x858fb9 (0x55100).
- **Liberation** : `0x7c6ee0(ecx = id d'unite)` : `+0xa8 -= 1` ; a 0 : etat 4 -> 5, sinon `+0xa0 = 1`.
  Meme code dans 0x7c6c30 (retrait d'une unite).
- **Blocage** `0x81bdd0(ecx = salle demandee)` (1 = refusee), selon la salle du centre de chargement :
  centre en 0x120 hors des unites 0x10921 / 0x10922 -> toute salle autre que 0x120 est refusee ; centre en 0x160 ->
  0x150 refusee ; centre en 0x200 dans les unites 0x11315 / 0x11316 -> 0x150 refusee.
- **Salle courante** `0x7eefc0(pos*)` (BoxData, zones...) : mode 1 (ou phases 0xe01 / 0xe03) -> calculee par la
  position ; mode 0 -> `u32 [0x130c890]` (numero de la **premiere** entree de la table).

## 3. Demandeur d'unites fixes `0x11eabd0` - confiance haute (mecanisme)

Objet global, automate 0x82d1e0 appele a chaque image par la mise a jour de scene (0x763a4a..0x763a51).

| RVA | Champ |
|---|---|
| `0x11eabd0` | u32 etat |
| `0x11eabd4..0x11eabf0` | u32 courant[8] |
| `0x11eabf4..0x11eac10` | u32 voulu[8] (id d'unite, 0xffffffff = aucune) |
| `0x11eac14` | u32 liste modifiee |
| `0x11eac18` | f32 minuterie |

| Etat | Code | Role |
|---|---|---|
| 0 | - | inactif (monde ouvert) |
| 1 | 0x82d225 | `0x7c7260(0)` (passage en liste fixe : tout le monde ouvert est decharge) ; etat 2 |
| 2 | 0x82d238 | attend `0x7c58b0()` ; courant[] = -1 ; etat 3 |
| 3, 5 | 0x82d271 | si `[+0x44]` : pour i < 8, `0x7c4250(i)` si courant != voulu, puis emplacement i = voulu[i] (decalage nul) ; courant = voulu ; `[+0x44] = 0` ; minuterie = 180.0 ; etat 4. **L'etat 5 est l'etat stable "liste fixe chargee"** ; on peut y changer la liste (ecrire voulu[] puis `[+0x44] = 1`) |
| 4 | 0x82d380 | decompte, puis attend pour chaque unite `0x7c5430(unite)` (unite prete **et salle a l'etat 4**) et ses objets ; etat 5 |
| 6 | 0x82d4ae | retour : en mode 0, emplacement 0 = -1 ; `0x7c7260(1)` ; minuterie = 180.0 ; etat 7 |
| 7 | 0x82d4ff | decompte ; quand mode == 1 et `0x7c58b0()` : etat 0 |

API du jeu : `0x806d60(rcx = 0x11eabd0, rdx = u32[8])` (copie la liste, `[+0x44] = 1`), `0x813240` (etat = 1),
`0x815830` (etat = 6), `0x7f7b10` (pret = etat 0 ou 5, et etat de scene `ElevatorLoop` absent).

Appelants :

- `hap::FastTravel` (vtable 0xc26e28, 0x2fe220) : destination `ft_RMI` / `ft_RMI2` -> `0x806d60(0x11eabd0,
  0xf2b088 = {0x52001, -1 x7})` + `0x813240` (0x2fe9b2..0x2fe9cc) ; autre destination -> `0x815830` (0x2fe8e4).
- Gestionnaire des ascenseurs LOOP (objet `0x13df730`, 0x8291c0, `[+8]` = id d'ascenseur = `setType` de l'objet
  ba0200) : table `0xf64050`, entrees de 0x28 o `{u32 A, u32 B, u32 unites[8]}` :

| Id | A | B | Unite | Salle | Ascenseur (fichier, hap, position de la cabine) |
|---|---|---|---|---|---|
| 0 | 1 | 1 | 0x53001 | r530 | quest/qb50 `劇場内エレベーター`, ba0200 `cage_park2` (836.18, 1.34, 302.83) |
| 1 | 1 | 1 | 0x52001 | r520 | quest/qb60 `教祖部屋入口`, `cage` (-418.53, 0.98, 436.69) |
| 2 | 1 | 0 | 0x52001 | r520 | quest/qb60 `ボス部屋出口`, `cage2` (-445.20, 47.88, 212.30) |
| 3 | 1 | 1 | 0x50100 | r501 | quest/qb70 `コピー都市エレベーター`, `cage` (325, -117, 406) |
| 4 | 0 | 0 | 0x50001 | r500 | quest/qb20 `塔_エレベーター本体と内壁外壁扉`, ba6003 `cage_tower` (168.6, -68.9, 351.68) |
| 5 | 0 | 0 | 0x5a000 | r5a0 | quest/qb31 (unite de la foret), `cage_forest` (676.20, -59.50, -339.63) |
| 6 | 0 | 1 | 0x5a100 | r5a1 | quest/qb32 (ville engloutie), `cage_water` (602.18, -68.85, 860.42) |
| 7 | 0 | 1 | 0x5a200 | r5a2 | quest/qb30 (parc), `cage_park` (745.47, 19.42, 295.26) |
| 8 | 1 | 1 | 0x5a800 | r5a8 | quest/qb90 `ループエレベーター`, `cage_forest` (549.31, -25.15, -591.35) |
| 9 | 1 | 1 | 0x5a900 | r5a9 | quest/qb85 `コロシアムへのエレベーター`, `cage_water` (369.62, -80.64, 782.08) |
| 10 | 1 | 1 | 0x5aa00 | r5aa | quest/qb80, `cage_park2` (-1169.02, -34.75, -354.32) |
| 11 | 1 | 1 | **0x50200** | **r502** | quest/qb00 `地下ダンジョンエレベーター`, `cage` (262.03, -21.76, 366.13) |
| 12 | 1 | 1 | **0x50300** | **r503** | quest/qb95 `カイネの部屋へのエレベーター`, `s_cage1` (115.64, -4.78, -192.67) |

  Les deux sens du trajet (0x82a12b et 0x82a877) : si `A != 0`, un sens ecrit la liste de l'entree + etat 1, l'autre
  ecrit l'etat 6 ; si `A == 0` c'est l'inverse (exterieur = liste fixe). Le sens de B n'a pas ete lu.
  Un ascenseur LOOP est une cabine qui boucle entre deux portes distantes de 12 m (alias `0` = porte basse, `1` =
  porte haute) pendant que le monde est echange. 0x50200 et 0x50300 n'apparaissent **nulle part ailleurs** dans l'exe
  (recherche des constantes u32 dans tout le fichier) : ces deux ascenseurs sont le seul chargement de r502 et r503.
- `0x3ac870` : liste vide (0xf2b108) + etat 1.

## 4. Appeler ou ecrire depuis un client externe

### A. Demandeur (recommande) : unite + salle, comme le jeu

1. Preconditions : `[0x102A368] == 1`, `[0xF64A9C] == 2` (phase_jump.md), `[0x11eabd0] == 0` (ou 5), pas de piratage.
2. Ecrire `u32[8]` en `0x11eabf4` : {unite, 0xffffffff x7}. Ecrire `[0x11eac14] = 1`. Ecrire **en dernier**
   `[0x11eabd0] = 1` (depuis l'etat 5 : ne pas toucher l'etat, la liste est relue).
3. Le monde ouvert est decharge autour du joueur : **maintenir la position du joueur** (la reecrire a chaque
   passage, a la position cible dans la salle) jusqu'a la fin, sinon il tombe. Le jeu ne fait jamais cela joueur
   libre : cabine d'ascenseur ou fondu du voyage rapide (non verifie hors de ces cas).
4. Attendre `[0x11eabd0] == 5`, puis une entree `i` de `0x130c890 + 0x178 * i` avec `+0 == salle` et `+4 == 4`.
   Delai de garde 60 s (dechargement complet + minuterie de 180 images + lecture).
5. Verifier les coffres. Pour une autre unite wd5 : reprendre en 2 depuis l'etat 5.
6. Retour : teleporter le joueur a une position du monde ouvert, ecrire `[0x11eabd0] = 6`, maintenir la position,
   attendre `[0x11eabd0] == 0`.

Ecritures de simples u32, aucune allocation ni pointeur ; l'etat est lu par le fil du jeu a l'image suivante.

Risque r120 / r520 : la demande de salle faite a la fin de la lecture de l'unite passe par 0x81bdd0, qui en mode 0
lit la salle de la premiere entree de `0x130c890`. Si cette entree contient encore 0x120 a ce moment et que le
joueur n'est pas dans les unites 0x10921 / 0x10922, la salle 0x520 est refusee sans erreur (l'unite est quand meme
declaree prete). Le jeu s'en protege par l'exception 0x10921 / 0x10922 (l'ascenseur id 1 est dans l'unite 0x10921 ;
l'id 2 est dans 0x10920). Pour r520 : lancer la demande depuis une position hors de r120, ou depuis la cabine id 1
(-418.53, 0.98, 436.69), et toujours controler l'entree 0x520 a l'etat 4 (non verifie).

### B. Salle seule (plus leger, moins fidele) : `0x7c7020`

`remote_call 0x7c7020(ecx = 0x50200)` : charge `st5/r502.dat` (haps, donc entites `EntityLayoutAction`) sans
`wd5/g50200.dat` (pas de sol, pas de collision) et sans quitter le monde ouvert. Attendre l'entree `0x502` a
l'etat 4. Liberer par `0x7c6ee0(ecx = 0x50200)` (sinon la salle reste chargee). Refuse si le centre de chargement est
dans r120 hors des unites 0x10921 / 0x10922 (0x81bdd0). Equivalent en ecritures : premiere entree a `+4 == 0` :
`+0 = salle`, `+0xa8 = 1`, puis `+4 = 1` ; liberation : `+0xa8 = 0`, `+4 = 5` quand `+4 == 4`.
Non verifie : que les coffres soient crees sans l'unite (l'attribut des actions `オブジェ配置` vaut 0xff000010,
0x01000010 ou 0x10 selon les haps ; son octet haut n'a pas ete lu dans l'exe) ; pas de contenu BoxData fiable en
mode 1 (la salle courante 0x7eefc0 reste celle de la position).

### C. Ascenseur ou saut de phase

Voir section 5 (positions des cabines, sous-phases). Monter dans une cabine demande des entrees manette et, selon
l'ascenseur, un etat de deblocage.

## 5. Procedure par salle

Coffres : `chests.json` / `world_positions.json`. "Unite du dessus" = ce que le mode seamless charge a la
position du coffre (emulation de 0x7c49f0 / 0x7c3260 / 0x7eeee0 sur les 206 coffres de st*).

### r502 - City Ruins: Deep Cave / Emil's Residence (11 coffres) - unite 0x50200

- Au-dessus : cellules (12,19), (13,18), (14,18) de la ville -> r100 (p100) ou r200. **Jamais chargee par la
  position.** Aucune sous-phase n'a `RoomNo` g50200 : pas de saut de phase possible.
- Entree du jeu : ascenseur LOOP id 11, `quest/qb00.dat`, hap `地下ダンジョンエレベーター` (aucun groupe, aucune
  condition), cabine ba0200 (262.03, -21.76, 366.13), portes ba0202 `0` (261.39, -21.76, 363.51) et `1`
  (261.39, -9.76, 363.51). Aucun etat de deblocage dans l'exe pour l'id 11 (cas par defaut de la table 0x82ab18).
  Cote salle = porte basse `0` (deduit des autres ascenseurs, confiance moyenne).
- Recommande : **A** avec {0x50200}. Position sure : cabine (262.03, -21.7, 366.13) (objet de qb00, present dans les
  deux mondes), puis directement les coffres.
- Coffres : B1 (61.4, -36.3, 286.8), (-63.0, -58.4, 307.2), (144.9, -26.3, 343.8) ; B2 (-21.0, -135.7, 351.8),
  (72.1, -114.5, 343.3), (53.0, -109.8, 295.3), (52.7, -114.5, 313.2) ; B3 (32.9, -231.0, 353.5),
  (-29.9, -223.1, 359.9), (-74.9, -222.3, 316.5) ; residence (337.2, -248.0, 407.3).
- Conditions : groupe `宝箱・採取ポイント` sans jeton (+ arret pendant le piratage) pour les 10 premiers ; le
  coffre (337.2, -248.0, 407.3) est dans le groupe `q900クリア後宝箱` (etat `q900_FIN`) : **absent tant que q900
  n'est pas finie**.
- A l'interieur : ascenseur ordinaire (`ElevatorAction`, r502 `エレベーター/自動ドア`) entre `1f`
  (134.20, -27.55, 356.10) et `0f` (134.17, -238.82, 355.98), verrouille par une zone cylindrique tant que des
  ennemis sont la : sans effet pour une teleportation.

### r503 - salle de l'ascenseur du Shopping Center (4 coffres) - unite 0x50300

- Au-dessus : cellule (13,16), unite 0x11316 -> r100 / r200. Aucune sous-phase g50300.
- Entree du jeu : ascenseur LOOP id 12, `quest/qb95.dat`, hap `カイネの部屋へのエレベーター`, cabine
  (115.64, -4.78, -192.67), portes `s_door0` (115.64, -4.78, -190) et `s_door1` (115.64, 7.21, -190).
  Deblocage : etat de scene `ShoppingMall_ElevatorUnlock` (0x829764) ; objet `item_uq_mallKey` lu en 0x8345f0.
- Recommande : **A** avec {0x50300}. Coffres : (94.2, -2.6, -158.4), (94.8, -3.0, -155.8), (96.3, -2.6, -159.8),
  (126.6, -3.8, -150.5). Aucune condition de groupe.

### r500 - Tour (6 coffres) - unite 0x50001

- Au-dessus : ville (r100 / r200). Les 6 coffres sont dans des `EntityLayoutArea` (`オブジェ配置エリア_*`) :
  l'entite n'est creee que si le joueur est dans le volume de l'action (chaque coffre est dans son volume,
  distance 0 par `areas.distance`) : **se teleporter sur le coffre apres le chargement**.
- Saut de phase (p300, `RoomNo` g50001, liste fixe posee par le jeu) : `275_CD_Tower_walk_9S` (148, -58, 352),
  `290_CD_Tower_A2` (153, -58, 353), `293_CD_Tower_LibraryHack_A2` (136.72, -10.57, 450),
  `295_CD_Tower_SelfHack_9S` (0, -92, 352), `300_00_CD_Tower_Elevator_A2` (210, -15, 412) : toutes points de
  reprise, mais ce sont des sous-phases d'histoire (cinematiques, combats).
- Ou **A** avec {0x50001} depuis n'importe quelle phase. Ascenseur LOOP id 4 (`quest/qb20.dat`, cabine ba6003
  (168.6, -68.9, 351.68)) : groupes conditionnes par la salle (jetons 0x5cda8ece 0x501 et 0x5a4, attribut 0x10).
- Coffres : (6.0, -92.1, 346.4), (-22.7, -28.6, 353.9), (162.4, -2.6, 462.9), (159.3, -2.6, 435.2),
  (235.0, -15.3, 404.3), (94.1, -48.4, 302.4). Condition : piratage seulement.

### r501 - Copied City (5 coffres) - unite 0x50100

- Saut de phase (p200) : `110_00_A_Copy_City` (318, -115, 406), `115_AB_Copy_City_AdamDie` (271, -111, 629).
  Ou **A** avec {0x50100}. Ascenseur LOOP id 3 (`quest/qb70.dat`, cabine (325, -117, 406), deblocage `CC_Opening`).
- Le coffre (244.6, -112.0, 647.8) est dans le groupe `アダム戦中無効` (attribut 0x20, etats `CC_Adam_battle` et
  0xaaf4be20) : absent pendant le combat contre Adam, donc **pas** en `110_00_*`.

### r520 - Abandoned Factory: Underground / His Grace's Room (23 coffres) - unite 0x52001

- Au-dessus : r120 (et r100 / r200 en bordure). Les 5 coffres de la salle du gourou sont a y = 1..6, a la hauteur
  de l'usine de surface, mais dans r520.
- Saut de phase (p200) : `140_20_A_RobotM_CR_GuruRoom` (-424.03, 1.08, 437.26), `140_90_A_RobotM_CR_UF_Exit`
  (-459, 48, 212), `140_80_A_RobotM_CR_UF_BossArea` (-599.8, 49.8, 212.3). Voyage rapide `ft_RMI` (Factory:
  Furnace) / `ft_RMI2` (Factory: Hangar) : charge {0x52001}. Ou **A** avec {0x52001}.
- Ascenseurs LOOP id 1 (cabine (-418.53, 0.98, 436.69), deblocage `R1_ElevatorUnlock_entrance`) et id 2
  ((-445.20, 47.88, 212.30), `R2_ElevatorUnlock_exit`), `quest/qb60.dat`.
- Condition des coffres : piratage seulement.

### r530 - Amusement Park: Under the Theater (1 coffre) - unite 0x53001

- Au-dessus : cellule (18,16) -> r130. Aucune sous-phase g53001.
- Ascenseur LOOP id 0, `quest/qb50.dat`, hap `地形(4)` / groupe `劇場内エレベーター` (attribut 0x10, etats
  0x17cd65ae et 0x4e86405c non nommes), cabine (836.18, 1.34, 302.83), portes (836.18, 1.33 / 13.33, 305.52).
- Recommande : **A** avec {0x53001}. Coffre (948.3, -3.7, 309.9) (`Demon's Cry`), piratage seulement.

### r100 / r200 - City Ruins

- Chargees par la position. **r100 seulement en p100, r200 en p200 / p300** : les 3 coffres de st1/r100 sont
  introuvables hors p100, les 12 de st2/r200 introuvables en p100. Verifier la phase courante `[0xF64AA0]`.
- r200 (69.8, 10.7, 239.5) `Nuclear Arms Manual` : groupe `q520で有効` (etats q520/RUN_1..3, CLR, DONE, FIN,
  END...) : seulement pendant ou apres q520.

### r110 - Resistance Camp (unite 0x11420, cellule (14,20))

- Chargee par la position. Les 13 coffres sont dans des `r110_<groupe>_grp.pak` (groupes charges a la demande) :
  `宝箱` (39e33c4a, sans condition) ; `オブジェ配置(19)` (15c7bcce, groupe `q650(2)` attribut 0x50 : absent des
  qu'un etat q651 / q652 est pose) ; `オブジェ配置(20)` (d8aa9dd1, groupe `q651(2)` attribut 0x40 : present
  seulement avec un etat q651 / q652).

### r120 - Abandoned Factory (15 coffres)

- Chargee par la position (toutes les cellules des coffres donnent 0x120). Les 15 coffres, dont les 12 de
  `設置オブジェクト`, sont dans **`r120_13b2704d_grp.pak`** : groupe `ロボット山-オブジェクト関連` (attribut 0x50,
  jeton `RobotMt_Boss/A` inverse), parent `STG,巨大ロボ操作時中無効` (attribut 0x10, `GiantRobot_battle`,
  `PrologueSTG`). Ils sont donc absents pendant le prologue / le boss de l'usine (route A) et le combat du robot
  geant ; `2Bの大剣` et `宝箱+採取P+死体採取ポイント` exigent en plus l'absence de `RobotMt_Prologue/A` ;
  `MyHap(3)` (-452.1, 12.9, 433.3) exige `religion_after` ou `religion_start`.
- Rien dans le chargement de salle n'explique 9 coffres manquants sur 12 dans un meme hap : a examiner en jeu
  (etats ci-dessus, delai de chargement du grp.pak, attribut d'action 0x01000010 propre a ce hap). Non resolu.
- Pendant que le centre est dans r120 (hors unites 0x10921 / 0x10922), aucune autre salle ne peut etre demandee
  (0x81bdd0).

### r130, r140, r150, r160, r170

- Chargees par la position ; aucune cellule de coffre ne donne une autre salle.
- r130 : `園内宝箱` / `オブジェ配置エリア_*` et `奉納武器` sont des `EntityLayoutArea` (le joueur doit etre dans
  le volume).
- r140 : groupe `宝箱・採取ポイント`, attribut 0x20, etat `PV_NPCLayout_3` : les 8 coffres disparaissent quand
  cet etat est pose (village detruit, route C/D).
- r150 : (15.7, -116.8, -537.3) dans `r150_76411fc3_grp.pak`, groupe `ボスエリア埋め立て後` (0x50,
  `DT_NPCLayout_q006` inverse).
- r160 : groupe `専用EVサブフェーズ中に無効` (0x10, `eventsubphase`) pour tous ; `q440用宝箱など` (3 coffres
  `Machine Part`, attribut d'action 0xff000418) appartient a la quete q440.
- r170 : coffres par route dans des grp.pak (`Route/A`, `Route/B`, `Route/C` ou `Route/D`, attribut 0x42).

## 6. Savoir que le chargement est fini - confiance moyenne

- Salle : entree de `0x130c890` avec `+0 == salle` et `+4 == 4`.
- Liste fixe : `[0x11eabd0] == 5`.
- Monde ouvert stable (predicat 0x7c58b0) : `[0x12504bc] == 0`, `[0x1255818] == 1`, `[0x1255978] == 1`,
  `[0x124e218] == 1`. A attendre apres **chaque** teleportation avant de chercher un coffre : le changement de
  cellule decharge et recharge jusqu'a 7 unites, la salle n'est demandee qu'a la fin de la lecture de l'unite
  (etat 3 du noeud), puis les haps et les grp.pak sont lus.
- Unite : `0x7c5430(ecx = unite)` renvoie 1 (lecture seule, mais lit des listes du jeu : appel distant non conseille).

## 7. Conditions des coffres (groupes hap)

Attributs de groupe (deduits des noms et de `world_positions.py`, non lus dans l'exe) : 0x10 = condition inversee,
0x20 = arret tant que l'etat est pose, 0x40 = groupe dans un `<fichier>_<id>_grp.pak` charge a la demande.
Jeton 0x743b077d id 1 = piratage en cours (tous les groupes `ハッキング中停止`). Voir la section 5 pour le detail
par salle. Coffres des salles wd5 soumis a un etat d'histoire : r502 residence (`q900_FIN`), r501 (`CC_Adam_battle`).

## 8. Preuves (desassemblage)

```
82f6cd  mov r9d,[rbx] ; lea r8,"st%1x/r%03x.dat" ; and eax,0xfff ; sar r9d,8          ; table 0x130c890, pas 0x178
7c7038  call 0x7eeee0 ; 7c7041 call 0x81bdd0 ; 7c70b8 mov [rcx],ebx ; mov [rcx+4],1 ; inc [rcx+0xa8]
7c6f3d  dec [rcx+0xa8] ; cmp [rcx+4],4 ; mov [rcx+4],5 / mov [rcx+0xa0],1
7eeee0  lea eax,[rcx-0x50000] ; cmp eax,0xffff ; ja ; shr r8d,8 ; ret                    ; unite 0x5xxxx -> salle
7eef5b  cmp eax,0x100 ; ... cmp r11d,0x90 ; mov eax,0x200                                 ; r100 -> r200 hors p100
7eefca  cmp [0x12504ac],1 ; ... 7ef012 mov eax,[0x130c890]                                ; salle courante
8318ae  lea rcx,[rsi+8] ; call 0x7c69f0 ; mov [rsi+0x20],4                                ; unite chargee -> salle
831922  call 0x7c6c30                                                                     ; unite retiree
7c8d54  lea rdx,[rsp+0x30] ; lea rcx,[0x1255760] ; call 0x263f80                          ; centre = joueur
8158d2  add ecx,[r15-0x10] ; add edx,[r15-0xc] ; call 0x7c3260 ; cmp ebx,7                ; 7 cellules
7c7146  cmp [0x12504ac],0 ; jne ; ... 7c7194 mov [rbx+0xc],eax                            ; 7c7140 : liste fixe seule
85587c  call 0x7c7140 ; 8557bf mov edx,0x50001 ; 855828 mov edx,0x52001                   ; demarrage de phase
82d227  call 0x7c7260 (ecx=0) ; 82d330 mov [rbx+rbp+0xc],eax ; 82d3bf call 0x7c5430 ; 82d466 mov [r14],5
82d4e6  call 0x7c7260 (ecx=1) ; mov [r14],7
2fe9b2  lea rdx,[0xf2b088] ; lea rcx,[0x11eabd0] ; call 0x806d60 ; call 0x813240          ; FastTravel ft_RMI
82a12b  cmp [rdx+rcx*8+0xf64050],0 ; je liste ; mov [0x11eabd0],6                         ; ascenseur, sens 1
82a877  cmp [rdx+rcx*8+0xf64050],0 ; je etat6 ; ... mov [0x11eabd0],r15d(1)               ; ascenseur, sens 2
3487e5  mov ecx,0x55000 ; call 0x7c7020 ; 858fb4 mov ecx,0x55100 ; call 0x7c7020
```

Donnees : `LoopElevatorAction` = code hap 0x223e4df9 (14 instances, toutes dans quest/qb*.dat) ; les ids viennent
du `setType` de l'objet ba0200 (ba6003 pour la Tour) ; `ElevatorAction` (0x367aa6d3) = ascenseurs internes a une
salle (r502, r520, core_hap `谷底`), sans changement d'unite. Aucune action hap de r100 / r200 / core_hap ne charge
une unite (types presents : pas de `PositionLoadJump`, `ReadMapBack`...). `SeamlessMapStopArea` (0xfd74c4a9) :
p100, p200, p300, r130, r200 (non analyse, hors sujet).

## 9. A valider en execution

| Point | Controle |
|---|---|
| Ecriture du demandeur (4.A) depuis l'exterieur | {0x50200} depuis la ville : `[0x11eabd0]` 1 -> 2 -> 3 -> 4 -> 5 ; entree 0x502 a l'etat 4 ; coffres de r502 presents |
| Joueur pendant le dechargement du monde | maintien de position suffisant ? mort par chute, zone de recuperation, camera |
| Retour par l'etat 6 | `[0x11eabd0]` 6 -> 7 -> 0, `[0x12504ac]` == 1, ville rechargee |
| `[0x130c890]` (premiere entree) == salle wd5 en mode 0 | sinon le contenu BoxData lu par le jeu serait celui d'une autre salle |
| Appel 4.B `0x7c7020(0x50200)` | la salle atteint l'etat 4 sans l'unite ; les coffres sont-ils crees ? liberation propre par 0x7c6ee0 |
| Cote des portes des ascenseurs LOOP | porte `0` (basse) = interieur pour les ids 0, 11, 12 (deduit) |
| Sens des champs A / B de la table 0xf64050 | journal de `[0x11eabd0]` pendant un trajet reel (id 1 ou 3) |
| Deblocage des ascenseurs 11 et 12 | id 11 sans condition ? id 12 : `ShoppingMall_ElevatorUnlock` / `item_uq_mallKey` |
| r120 `設置オブジェクト` | etats `RobotMt_Boss/A`, `GiantRobot_battle`, `PrologueSTG` au moment du test ; attendre le predicat de la section 6 ; role de l'attribut d'action 0x01000010 |
| Predicat "monde stable" (section 6) | journal des 4 valeurs pendant une teleportation entre deux zones |
| Coffres `EntityLayoutArea` (r500, r130) | creation seulement joueur dans le volume |
| Blocage 0x81bdd0 | depuis l'interieur de r120, une demande de salle wd5 par 4.B echoue ; 4.A (mode 0) non concerne ? |
