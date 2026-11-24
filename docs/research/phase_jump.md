# Saut de phase / selection de chapitre (NieR:Automata v1.04 Steam)

Analyse **statique** de `NieRAutomata.exe` + `data/` (jeu jamais attache, rien ecrit, aucun appel distant).
Adresses = RVA (base 0x140000000). Outils : `tools/xref.py` + capstone, `tools/cpk.py`, `tools/rf_endings.py`.
**Rien n'a ete execute** : la section 8 liste ce qui doit etre valide en jeu avant de s'y fier.

Confiance : **haute** = lu dans le desassemblage et recoupe (second chemin de code ou donnee) ; **moyenne** = lu dans
le desassemblage seul ; **faible** = deduit.

## Resume pour le client

| Besoin | Solution | Confiance |
|---|---|---|
| Sauter a (phase, sous-phase) comme le jeu | `0x761460(rcx=0x102A360, edx=phase, r8=char* sous-phase, r9d=1, [rsp+0x20]=0)` : c'est l'appel exact du chargement de sauvegarde (0x9C6B07) et de l'action hap `PhaseJumpAction` (0x358D9B) | haute (appel), non verifie depuis un fil etranger |
| Rejouer "Chapter Select" a l'identique | poser `PL/x` + `Route/x`, effacer les bits 0-3 de `[0x14957D8]`, puis `0x9C6340(ecx=phase, rdx=char* sous-phase, r8d=indice ChapterData + 1)` (ce que fait le gestionnaire du menu 0x95D210) | haute (sequence), non verifie en execution |
| Table des chapitres | `core/coregm.dat:ChapterData.cha`, 93 enregistrements de 0x50 o ; pointeur en memoire `[0x11EABC8]` ; deja dans `phases.json:chapters` | haute |
| Debloquer Chapter Select | bit 5 de `u32 [0x14957D8]` (masque `0x04000000`), dans le bloc de l'emplacement ; bit 4 (`0x08000000`) = mode debug | haute (bit 5 = dialogue CREDIT_DIALOG_CHAPTER_0), moyenne (effet sur chaque menu) |
| Phase en attente (ecriture pure) | `0xF64AF0` {u32 phase, u32 hachage, char nom[0x20]} : consommee seulement a la fin de scene ; `0xF64B18` = cible, comparee a chaque image a la phase courante `0xF64AA0` | haute (mecanisme), ecriture externe deconseillee (section 5) |
| Savoir que le saut est fini | `[0xF64AA0]` == phase, nom `0xF64AA8` == sous-phase, `[0xF64A9C]` == 2, `[0x102A368]` == 1 | moyenne |

## 1. Machine a phases (0x862540) - confiance haute

Bloc global (initialise par 0x85F8F0), 4 descripteurs de 0x28 o `{u32 phase, u32 hachage, char nom[0x20]}` :

| RVA | Role |
|---|---|
| `0xF64A9C` | u32 etat de la machine (0..8) |
| `0xF64AA0` | phase **courante** (nom en `0xF64AA8`) |
| `0xF64AC8` | phase precedente |
| `0xF64AF0` | phase **en attente** (`-1` = aucune) ; ecrite par 0x85F200 |
| `0xF64B18` | phase **cible** (nom en `0xF64B20` = `currentPhase` de offsets.py : c'est la cible, pas la courante) |

`phase` = numero (0x100 = p100, 0x300 = p300, 0xF00 = titre, 0xF31 = pf31). `hachage` = 0x14C5B0(nom) =
`crc32(nom en minuscules) & 0x7FFFFFFF` (verifie : `00_85_A_RobotM_Pro_2ndArea` -> 0x24C4B954, cf. runtime_state.md).

Etats (table de saut 0x862B10) :

| Etat | Code | Role |
|---|---|---|
| 0 | 0x862A59 | inactif |
| 1 | 0x8625A9 | attend la fin des chargements (0x85E320) et `[0x13ECE98] != 0`, puis etat 3 |
| 2 | 0x86293C | **en jeu** : si cible (`0xF64B18/1C`) != courante (`0xF64AA0/A4`) : meme phase -> etat 5 ; phase differente -> rappels de fin, `0x85F300(cible)` (chargement), etat 3 ; cible == -1 -> etat 7 |
| 3 | 0x8625D3 | attend les chargements, cree l'objet de phase (table `0xF64B50`, 15 x {u32 phase, fonction}), etat 4 |
| 4 | 0x862672 | rappel d'init `[0x13ECE48]` jusqu'a != 0 ; etat 5 (ou 1 si cible == -1) |
| 5 | 0x8626C1 | rappel `[0x13ECE58]` ; etat 6 |
| 6 | 0x8626E5 | rappel `[0x13ECE60]` jusqu'a != 0 ; precedente = courante ; **courante = cible** ; etat 2 |
| 7 | 0x8627ED | rappel de fin `[0x13ECE80]` ; etat 8 |
| 8 | 0x862809 | rappel `[0x13ECE88]` jusqu'a != 0 ; **si en attente != -1 : cible = en attente, en attente = -1, `[0x13ECE98]` = 1, etat 3** ; sinon courante = cible (-1), etat 0 |

Fonctions d'ecriture :

- `0x85F200(ecx=phase, rdx=nom)` : ecrit **en attente** (`0xF64AF0`, hachage en `0xF64AF4`, nom en `0xF64AF8` via
  0xBB4F38 (copie bornee 0x20)) et demande le chargement des donnees de la phase par `0x85F300` si elle n'est pas
  deja chargee (liste `0x13ECF10..0x13ECF18`, entree `{u32 etat, u32 phase, ...}`, etat 2 = chargee).
- `0x85F290(ecx=phase, rdx=nom)` : ecrit directement la **cible** + `[0x13ECE98] = 1` (pas de fin de scene).
- `0x85F760(ecx=phase, rdx=nom ou 0)` : idem + `0x85F300` ; nom nul = sous-phase par defaut (table `[0x13ECE38]`,
  0x20 o par phase). Seul appelant : demarrage du jeu (0x762226, phase 0xF00 `SIGNIN`).
- `0x85F5A0()` : cible = -1 (fin de phase), appele par la tache de scene a la fin du fondu.

## 2. Tache de scene et fonction de saut - confiance haute

Gestionnaire de scene = objet global **`0x102A360`** ; etat `u32 [0x102A368]`, poignee de fondu `[0x102A36C]`.
`SceneTask` = 0x75FC50 (`--- SCENE STARTUP ---` / `--- SCENE CLEANUP ---`) :

| `[0x102A368]` | Role |
|---|---|
| 0 | demarrage (rappel `[0x102A3A0]` = 0x7623D0) |
| 1 | en jeu (`0x760BF0` a chaque image, appel en 0x75FF29) |
| 2 | fin demandee : `0x760BF0` continue ; quand le fondu est fini (`0x18EF70([0x102A36C])`) et `0x7C58B0()` : nettoyage, **`0x85F5A0()`** (cible = -1), etat 3 |
| 3 | rappel 0x760850 (attente des liberations) ; puis etat 4 |
| 4 | sortie : nettoyage (0x760300) puis la tache se relance (0x26FB30 sur 0x75FC50) -> etat 0 |

Donc un saut = **redemarrage complet de la scene** : fondu, fin de phase (etats 7, 8), consommation de la phase en
attente (etat 8), rechargement (3..6). C'est le seul chemin que le jeu emploie pour changer de chapitre.

### `0x7614A0(rcx=scene 0x102A360, edx=phase, r8=nom, r9=params*)`

```
7614d0  cmp edx, -1 ; je -> [0x1029FB8] = 0x101 (relance sans changer de phase)
7614e1  cmp dword [r9+0x10], 0 ; [0x1029FB8] = 1 (ou 0x100 si != 0)
7614f5  test r8, r8 ; nom nul -> 0x85DFB0(phase) = sous-phase par defaut
761509  call 0x85f200            ; phase en attente
76151b  eax = [r9] - 1 ; table 0x76174C (types 1..8)      ; type 1 : [0x1029B30] = ([0x1029B30] & ~1) | 0x40
7616e1  call 0x18edb0            ; fondu "Scene Fade", duree [r9+8] (0x78 images), si [r9+0xc] == 0
7616f2  "se_fade_out"
761716  mov dword [rbx+8], 2     ; [0x102A368] = 2
761720  or  dword [0x1029B04], 8
```
`params` (0x18 o) : `+0` type, `+4` drapeau de couleur, `+8` duree, `+0xC` sans fondu, `+0x10`, `+0x14`.

Enveloppes (meme `rcx`, `edx`, `r8`) :

| RVA | params construits | Appelants |
|---|---|---|
| `0x7613E0` | {0, 0, 0x78, 0, 0, 0} | retour titre, fin de partie, 0x9C885B |
| `0x761410` | {0, 0, 0x78, 1, 0, 0} ; force (0xF00, `START`) si `[0x1029B34] & 0x4000000` | 0x83DCD4, 0x9C887A |
| **`0x761460`** | {r9d, 0, 0x78, arg5, 0, 0} | **chargement de sauvegarde 0x9C6B07**, **hap PhaseJumpAction 0x358D9B**, relance au point de reprise 0x358BA7 |

### Qui saute, et comment

| Origine | Code | Appel |
|---|---|---|
| Menu Chapter Select | 0x95D210 -> 0x9C6340 -> 0x9C65D1 | `0x7614A0(scene, [0x14958B4], 0x14958B8, {1,0,0x78,0,0,0})` (identique a `0x761460(..., 1, 0)`) |
| Chargement d'un emplacement | 0x9C6A60..0x9C6B07 | `0x761460(scene, [0x14958B4], 0x14958B8, 1, 0)` puis `[0x1422260] = 4`, `[0x1422264] = 0xA` |
| Ecran de chargement apres choix de l'emplacement | 0x97C8C6 | bits 2 ou 3 de `[0x14957D8]` -> nouvelle partie p100 `00_30_A_RobotM_Prologue_STG1` ; bit 1 -> p300 `00_10_CD_Bunker_Hangar_2B` (efface le bit 1) ; bit 0 -> p100 `00_00_B_RobotM_Pro_RobotBrother` (efface le bit 0) ; sinon phase et sous-phase de la sauvegarde |
| Action hap `PhaseJumpAction` (code 0x227440DA, vtable 0xC3FF60) | 0x358BD0..0x358DBC | `0x761460(scene, [action+0x58], nom [action+0x60]+0x28, 1, r12d)` ; ecrit avant le point de reprise dans le bloc de sauvegarde (0x9CC7C0 sur 0x14958B0) et `[0x1495920]` |
| mruby `phase_jump(phase, sous-phase[, opt])` | 0x332310 (enregistre en 0x34BAD6, arguments `"oo|o"`) | `0x85F290(phase, nom)` : **cible directe, sans redemarrage de scene** (avance de sous-phase en cours de jeu) |
| Game over "reessayer" | 0x97DB78 | `0x7614A0(scene, phase courante, nom courant, {1,0,0x78,...})` |
| Fins (pf30 `Ending_X`), titre (0xF00 `START`), DLC (0x400), essai (0xF50) | 0x991B98, 0x899138, 0x3A012F..., 0x3A4963 | `0x7614A0` avec constantes |

Aucun saut de phase de debug restant n'a ete trouve (pas de chaine `debug`/`phase` hors `phase_jump` et
`PhaseJumpAction`) ; les phases de test existent encore dans les donnees (`p001` : `ColTest`, `STG_test`... cf.
`phases.json:phase_info`) et sont atteignables par les fonctions ci-dessus (non verifie).

## 3. Chapter Select - confiance haute

### Table

`core/coregm.dat:ChapterData.cha`, charge par 0x81D530, pointeur **`[0x11EABC8]`**. En-tete : `+8` u32 offset des
enregistrements (0x14), `+0x10` u16 nombre (93). Accesseurs : 0x7DE910 (nombre), 0x7DD310(i) (pointeur),
0x7EB250 (recherche par chapitre / sous-chapitre / variante). Enregistrement de 0x50 o (disposition lue dans
0x95D210, 0x8A2F80, 0x7EB250 et verifiee sur le fichier) :

| Offset | Type | Contenu |
|---|---|---|
| +0 | u8 | indice (0..92) |
| +1, +2, +3 | u8 | chapitre, sous-chapitre, variante (`CHAPTER_NAME_%02d_%02d_%d`) |
| +4 | i32 | groupe de route : 0 = A, 1 = B, 2 = A ou B selon le personnage choisi, 3 = C/D |
| +8 | u32 | **masque** de personnages : bit 0 = 2B, bit 1 = 9S, bit 2 = A2 (3 = choix 2B/9S, 6 = choix 9S/A2) |
| +0xC | i16 | phase (0x100, 0x200, 0x300, 0xF31) |
| +0xE | char[] | nom de sous-phase |

Liste complete : `phases.json:chapters` (meme ordre ; `index` = octet +0). La liste de l'ecran (0x912CDA) reprend
**tous** les enregistrements ; seuls sont filtres : 17-10 variante 1 (exige l'etat `ending_C` 0x6570125A),
17-10 variante 2 (`ending_D` 0xFB1487F9), 17-11 (bit 0x21 de `[0x14957D8]`). Il n'y a pas de deblocage par chapitre.

### Deblocage du menu

Sequence de fin C/D (0x8639E0, sous-phase `BackTitle_CD` de pf10) :
```
863b33  mov ecx, 5 ; call 0x9cae50        ; bit 5 deja pose ?
863b52  lea ecx, [rax+5] ; call 0x9cbd90  ; pose le bit 5
863b5a  "CREDIT_DIALOG_CHAPTER_0"          ; dialogue "selection de chapitre debloquee"
863be0  mov ecx, 4 ... call 0x9cbd90 ; "CREDIT_DIALOG_DEBUG_0"   ; bit 4 = mode debug
```
0x9CBD90(n) : `[0x14957D8 + 4*(n>>5)] |= 0x80000000 >> (n & 31)`. Donc :

- **Chapter Select debloque = `u32 [0x14957D8] & 0x04000000`** (bit 5) ; mode debug = `& 0x08000000` (bit 4).
  Ces drapeaux sont dans le bloc de l'emplacement (fichier `SlotData_N.dat` : offset `0x14957D8 - 0x145C2D0 + 0xC`
  = 0x39514), donc sauvegardes avec lui.
- Lecteurs du bit 5 : menu titre 0x9B4428 (`[menu+0x938] = 1`), 0x860B08, 0x8F0A30, 0x91ED15, 0x863A44.
  L'ecran lui-meme (UI 0x7D, classe `UIChapterSelectLayout`, vtable 0xD06338) est cree par 0x9132B0, appele par
  le menu pause (0x8AF337, sous-ecran 15 de `[0x13FD7B8]`), le menu titre (0x96C654) et 0x95DBD5.
  Le test exact qui affiche l'entree dans le menu pause n'a pas ete isole (confiance moyenne : le bit 5 suffit).

### Ce que fait la validation d'un chapitre (0x95D210)

1. Personnage `c` = 0x8A2F80(ecran) : 0 = 2B, 1 = 9S, 2 = A2. Regle : chapitre 17 sous-chapitre 9 -> 9S, 17-11 ->
   A2 ; sinon liste des bits poses du masque `+8` dans l'ordre 2B, 9S, A2, indexee par le choix du joueur (0 ou 1).
2. `SceneStateSystem.set` (0x354B20, objet 0xFC2680) de `PL/2B`, `PL/9S` ou `PL/A2` (aucun personnage :
   `clearGroup("PL")` 0x321DF0).
3. Route : groupe `g` = octet +4 ; si `g == 2` : 2B -> 0, 9S -> 1. Puis `g == 1` -> `Route/B`, `g == 3` -> `Route/C`,
   sinon `Route/A` (0x95D42E..0x95D51E).
4. Si 2B et chapitre == 1 : 0x9C3B30 (remet les jeux d'armes `[0x14949B8..C8]` = 0x42E, 0x4EC, 0x4EC, 0x42E, -1).
5. `0x9CBD60(0..3)` : **efface les bits 0-3 de `[0x14957D8]`** (fins A/B/C/D "en attente de nouvelle route").
6. Musique `BGM_Chapter_Start`, `u32 [0xF64040] = 1`.
7. **`0x9C6340(ecx = i16 +0xC, rdx = &enregistrement+0xE, r8d = octet +0 + 1)`**.
8. `[ecran+0x68] = 1`, `u8 [0x1006A04] = 1`, `[0x1029B00] &= 0x7FFFFFFF` (sortie de pause).

### `0x9C6340(ecx=phase, rdx=nom, r8d=indice+1)`

```
9c636a  [0x145C2D0] = 0x09025954 ; [0x145C2D4] = 0x9ceb90()      ; en-tete du bloc d'emplacement
9c637f  [0x14958B0] = 0x10000000 puis btr 28 / bts 30  -> 0x40000000
9c6389  0x1495900, 0x1495910 remis a zero (0x265f10) ; 0x14958D8..0x14958F7 = 0 ; [0x1495920] = 1
9c63c9  [0x14958B4] = phase ; 0x14958B8 = nom (0x20 o)
9c6411  0x3f0780(0xFCA888) : si faux, retourne 0 sans sauter
9c6425  0x9c05f0(tmp, indice+1) : modificateur hap "ChapterSelect" ; 0x9bf3d0(0x1006A08, tmp)  -> ChapterBind
9c646b  serialise le document hap (etats de scene compris) dans le texte de sauvegarde 0x145C340 (0x30000 o)
9c652c  [0x1495944..4C] = 0 ; [0x149593C] = flottant ; [0x1495638] = -1 ; 0x7d8a60(0x125E300)
9c6560  0x9c0190(0x145C2D0, ...) : retire de l'inventaire les objets "item_uq_qXXX..." des quetes non terminees
9c6587  copie le bloc (0x399C0 o) vers les tampons [0x1422278] et [0x1422290]
9c65b9  0x7614a0(0x102A360, [0x14958B4], 0x14958B8, {1,0,0x78,0,0,0})
9c65e7  [0xF04310] = indice+1 ; [0x1422260] = 4 ; [0x1422264] = 0xA ; retourne 1
```
`[0x1422264] = 0xA` puis 2 (0x9C84B0) : quand la scene atteint l'etat 4, le jeu **recharge depuis le bloc
d'emplacement en memoire** : document hap relu depuis 0x145C340 (0x9C0330), puis donnees joueur (0x7C9190 /
0x7F2B40, 0x7D3A40, 0x7D4370, 0x7C3E10, 0x7CC610). Meme sequence qu'un chargement de sauvegarde (0x9C6B26).
Chapter Select = "modifier l'emplacement en memoire, puis le recharger". Aucun appel d'ecriture disque dans
0x9C6340 (confiance moyenne : deduit de l'identite avec le chemin de chargement).

`ChapterBind` (`core/corehap.dat:core_hap.pak`, arbre `ChapterBind`, 93 entrees de cle 1..93 = indice + 1,
classe `hap::chapter_bind::ChapterBind`) : seules 10 entrees ne sont pas vides :

| Cle | Chapitre | Effet |
|---|---|---|
| 23 | 05-01 | Item `-item_uq_filter`, `-item_uq_oil` |
| 51 | 10-02 | State `Electronic_Lock` |
| 63 | 12-01 | `*Branch9S/0`, `*qb31/FLT`, `*qb32/FLT` |
| 64 | 12-02 | `!Branch9S/0`, `!qb31/FLT` |
| 65 | 13-01 | `*BranchA2/1`, `*qb31/GRD` |
| 68 | 13-04 | `!BranchA2/1`, `!qb31/GRD` |
| 69 | 14-01 | `*Branch9S/1`, Item `-item_uq_pascalReq_3` |
| 73 | 14-05 | `!Branch9S/1`, `!qb32/FLT` |
| 74 | 15-01 | `*BranchA2/2`, `*qb32/GRD` |
| 75 | 15-02 | `!BranchA2/2`, `!qb32/GRD` |

(cle -> chapitre calcule par `phases.json:chapters[cle-1]` ; a recontroler.) Tous les autres etats d'histoire
viennent de `StateBind` (0x31E0B0) applique a l'entree dans la sous-phase (data_formats.md).

## 4. Route, personnage, ce qui est conserve

- **Route** : `StateBind` ne pose `Route/A` / `Route/B` que sur les sous-phases `_A_` / `_B_` de p100
  (`00_00_B...` -> `Route/B` + `PL/9S`, `00_30_A...` -> `Route/A`, `13_A_bunker_Setup`, `13_B_bunker_Setup`...) et
  `*Route/C` en p300 `00_10_CD`. **Les sous-phases `_AB_` ne posent rien** : avant un saut vers un chapitre A/B
  commun il faut poser soi-meme `Route/A` + `PL/2B` ou `Route/B` + `PL/9S`, comme 0x95D210. Pour C/D : `Route/C`
  + `PL/2B` (chapitre 11, masque 1), `PL/9S` (masque 2) ou `PL/A2` (masque 4).
- **Personnage** : 0x7C7B00 (appele par la preparation de scene 0x761A30, donc a chaque redemarrage de scene)
  traduit l'etat `PL/*` en objet joueur `[0x11E1F84]` (runtime_state.md, section 5). Poser `PL/x` avant le saut suffit.
- **Position de depart** : `[0x14958B0]` bit 29 = "reprendre a la position sauvegardee" (teste en 0x8556EF ->
  0x9CB2B0), ignore si le bit 30 est pose (0x8556E9) ; les bits 29 et 30 sont effaces au demarrage de la phase
  (0x85675E, 0x85677C). Chapter Select met `0x40000000` : depart au `PlayerPos` de la sous-phase.
- **Conserve par Chapter Select** (0x9C6340 n'y touche pas) : niveau, experience, argent, inventaire, armes, puces,
  tableau d'etat des quetes `[0x14946D0..]`, points d'acces `[0x14957E0]`, bits 4+ de `[0x14957D8]`.
- **Modifie** : `PL/*`, `Route/*`, etats et objets de `ChapterBind`, bits 0-3 de `[0x14957D8]` (effaces), phase et
  sous-phase de l'emplacement (`0x14958B4`, `0x14958B8`), point de reprise (`0x14958D8`, `0x1495900`, `0x1495910`),
  objets uniques `item_uq_qXXX` des quetes non terminees (retires), jeux d'armes si 01-01 en 2B, puis tous les
  etats que `StateBind` pose ou efface pour la sous-phase d'arrivee.
- Les etats de quete `qXXX/...` ne sont pas remis a zero par l'exe dans ce chemin (hors `StateBind` /
  `ChapterBind`) : le comportement "les quetes non finies sont reinitialisees" du web n'a pas ete retrouve
  statiquement (non verifie).

## 5. Points d'entree possibles pour le client

### A. Rejouer Chapter Select (recommande) - sequence haute, execution non verifiee

Entree : enregistrement `E` de ChapterData (lu en memoire : `[0x11EABC8] + 0x14 + 0x50 * i`, ou `phases.json`),
personnage `c` choisi dans le masque `E+8`.

1. `PL` : `rec = 0x150E70(rcx=0xF8C4E0, edx=crc32(nom), r8=char* nom, r9=longueur)` ; `tmp = rec` ;
   `0x354B20(rcx=0xFC2680, rdx=&tmp)` ; `0x150C60(rcx=&tmp)` (libere la reference), avec nom = `PL/2B` | `PL/9S` |
   `PL/A2` (crc32 zlib : 0x6940AA43, 0xE004537A, 0x3D57F14A).
2. Idem pour `Route/A` (0x583082BB), `Route/B` (0xC139D301) ou `Route/C` (0xB63EE397) selon la regle de la section 3.
3. Ecriture : `u32 [0x14957D8] &= 0x0FFFFFFF`.
4. Ecriture : `u32 [0xF64040] = 1`.
5. `rax = 0x9C6340(ecx=phase, rdx=char* sous-phase, r8d=i+1)` ; 1 = saut lance, 0 = refuse (0x3F0780).
6. Ecriture : `u8 [0x1006A04] = 1` ; `u32 [0x1029B00] &= 0x7FFFFFFF`.

Le nom de sous-phase peut pointer directement dans la table en memoire (`E + 0xE`), sinon dans une page allouee
par le client (chaine ASCII terminee par 0, moins de 0x20 caracteres).

Fil d'execution : tout ceci tourne normalement sur le fil de `SceneTask`. Deux manieres :

- **Cave sur le fil du jeu (preferable)** : detourner l'appel `0x75FF29` (`E8 C2 0C 00 00` = `call 0x760BF0`,
  precede de `48 8D 0D 37 A4 8C 00` = `lea rcx,[0x102A360]` en 0x75FF22 ; boucle de SceneTask, etat 1) vers une cave
  proche (rel32) : `sub rsp,0x28` ; si `[requete] != 0` : la remettre a 0, executer les etapes 1 a 6, ecrire le
  resultat ; `add rsp,0x28` ; `lea rcx,[0x102A360]` ; `jmp 0x760BF0`. Le client n'ecrit plus que les parametres et
  le drapeau de requete. `0x760BF0` appelle lui-meme `0x7614A0` (0x760F93) : le contexte est celui d'un saut normal.
- **`remote_call` (fil etranger)** : possible pour un premier essai (5 parametres suffisent pour chaque appel), mais
  0x9C6340 serialise le document hap et 0x354B20 modifie le tableau trie des etats pendant que le jeu les lit :
  course possible. A reserver a un jeu stable (`[0x102A368] == 1`, `[0xF64A9C] == 2`, pas de chargement).

### B. Saut brut, sans rechargement de l'emplacement - appel haute, effets moyenne

`0x761460(rcx=0x102A360, edx=phase, r8=char* sous-phase, r9d=1, arg5=0)` (5 parametres : compatible `remote_call`).
Avant : poser `PL/x` et `Route/x` (etapes A1, A2) et ecrire `u32 [0x14958B0] = 0x40000000` (sinon le bit 29 peut
replacer le joueur a la position sauvegardee). C'est ce que fait `PhaseJumpAction` pour les transitions d'histoire
(p100 -> p200...). Differences avec A : pas de `ChapterBind`, pas de retrait des objets de quete, l'emplacement en
memoire garde son ancienne phase (`0x14958B4`), pas de relecture du document hap.

### C. Ecritures seules (pas d'appel) - deconseille

- Ecrire la **cible** (`0xF64B20` nom 0x20 o, puis les 8 o `{phase, hachage}` en `0xF64B18` en dernier) quand
  `[0xF64A9C] == 2` declenche la transition au prochain passage de 0x862540 (c'est l'effet de mruby `phase_jump`),
  **sans** redemarrage de scene : monde, joueur et objets charges restent ceux de l'ancienne zone. Acceptable
  seulement pour avancer d'une sous-phase dans la meme zone ; jamais employe par le jeu pour changer de chapitre.
- Ecrire la phase **en attente** (`0xF64AF0`) ne suffit pas : elle n'est lue qu'a l'etat 8, apres une fin de scene,
  et suppose que 0x85F300 a deja charge la phase. Forcer `[0x102A368] = 2` a la main saute le fondu, le son et
  les drapeaux `[0x1029B04] |= 8`, `[0x1029FB8]`, `[0x1029B30]` : non recommande.

## 6. Attendre la fin du saut - confiance moyenne

Ordre observe dans le code apres l'appel :

1. `[0x102A368]` : 1 -> 2 (fondu, 0x78 images) -> 3 -> 4 -> 0 -> 1.
2. `[0xF64A9C]` : 2 -> 7 -> 8 ; a l'etat 8 la cible `0xF64B18` (nom `0xF64B20`) prend la valeur demandee et
   `[0xF64AF0]` repasse a -1 ; puis 3 -> 4 -> 5 -> 6 -> 2.
3. A la sortie de l'etat 6, `[0xF64AA0]` = phase et `0xF64AA8` = nom demandes.

Condition proposee : `[0xF64AA0] == phase` et `nom(0xF64AA8) == sous-phase` et `[0xF64A9C] == 2` et
`[0x102A368] == 1`, puis les indicateurs deja utilises par le client (`isLoading` 0x13ECEB8, `isWorldLoaded`
0xF6E3C0, entite joueur 0x1020C88 non nulle). Delai de garde conseille : 60 s. La sous-phase peut avancer seule
(scripts `phase_jump`) : comparer avec `>=` dans l'ordre de `pXXX_sub.bxm`, pas seulement `==`.
Ne pas lancer un second saut tant que `[0x102A368] != 1` ou `[0xF64AF0] != -1`.

## 7. Risques pour la sauvegarde

- **Rien n'est ecrit sur disque par le saut lui-meme** (0x7614A0, 0x761460, 0x9C6340 : aucun appel aux demandes
  de sauvegarde ; confiance moyenne). Mais A modifie le **bloc d'emplacement en memoire** (phase, sous-phase,
  bits 0-3, etats) : toute sauvegarde ulterieure (point d'acces, ou ecriture declenchee par le jeu) enregistre la
  partie a l'endroit du saut. B ne change que `[0x14958B0]` et les etats de scene.
- La machine de sauvegarde est `[0x1422260]` / `[0x1422264]` (0x9C73B4, 0x9C7C00, 0x9C84B0). Valeur 4 = application
  d'un chargement ; 3 = ecriture du bloc `0x1495C90` (donnees systeme, drapeaux globaux `0x1495E20`), declenchee
  automatiquement (0x9C7CC7). Les valeurs qui ecrivent `SlotData_N.dat` et leurs declencheurs n'ont pas ete
  cartographies : **non verifie** qu'aucune sauvegarde automatique d'emplacement n'existe en cours de chapitre.
- **Fins** : laisser un chapitre aller jusqu'au generique pose les bits 0-3 de `[0x14957D8]` (0x85C160) ; au
  chargement suivant de cet emplacement le jeu demarre la route suivante au lieu de reprendre (0x97C8C6).
  L'entree 92 (17-11, pf31 `endroll1`, fin E) peut **effacer les sauvegardes** si l'offre est acceptee : ne jamais
  l'inclure dans une visite automatique.
- Le mode Chapter Select du menu efface les bits 0-3 : une route "en attente" (fin vue, route suivante pas encore
  commencee) est perdue pour cet emplacement en memoire.
- Recommandations : copier `SlotData_0..2.dat`, `GameData.dat`, `SystemData.dat` avant la campagne de test ;
  travailler sur un emplacement dedie ; ne jamais envoyer d'entree "sauvegarder" pendant la visite ; restaurer les
  fichiers a la fin plutot que de compter sur l'etat en memoire.

## 8. A valider en execution

| Point | Controle |
|---|---|
| `0x761460` depuis un fil etranger | un saut p100 -> p100 (meme zone), puis un saut inter-phases ; surveiller plantage et fuite de la page |
| Cave en 0x75FF29 sur le bon fil | identifiant du fil dans la cave == fil qui execute 0x760BF0 ; pile alignee |
| Sequence A complete | comparer etats actifs, `[0x14958B0..B8]`, `[0x14957D8]` avec un vrai Chapter Select du menu |
| `Route/x` et `PL/x` suffisent pour les sous-phases `_AB_` | personnage `[0x11E1F84]` et etats apres saut en 02-01 route B |
| Bit 5 de `[0x14957D8]` fait apparaitre Chapter Select (menu pause et titre) | poser le bit sur une sauvegarde route A, ouvrir les menus |
| Chapitres 17-10 (exigent `ending_C` / `ending_D`) et 17-11 | hors menu, 0x9C6340 ne filtre pas : verifier que le saut direct fonctionne |
| Saut vers une sous-phase qui n'est pas une entree de ChapterData | `0x761460` avec une etape de `routes_full.json` ; position de depart `PlayerPos` |
| Aucune ecriture de `SlotData_N.dat` pendant une visite | date de modification des fichiers avant / apres |
| Sens de `[0xF64040]`, `[0x1006A04]`, `[0x1029FB8]`, `[0x1495920]` | photo memoire avant / apres un Chapter Select du menu |
| Condition de fin de saut (section 6) | journal des 4 valeurs pendant un saut |
| Correspondance cle ChapterBind -> chapitre | etats `Branch9S/*`, `BranchA2/*` apres saut en 12-01..15-02 |
| Reinitialisation des quetes non finies | tableau `[0x14946D0..]` avant / apres |

## Preuves (desassemblage)

```
85f23c  mov [0xF64AF0], ebx ; 85f24a call 0x14c5b0 ; 85f252 mov [0xF64AF4], eax ; 85f25d lea rcx,[0xF64AF8]
862840  mov eax,[0xF64AF0] ; cmp eax,-1 ; je ... ; 862852 mov [0xF64B18],eax ; 862896 mov [0xF64AF0],-1 ; 8628ad etat=3
86293c  mov eax,[0xF64B18] ; cmp [0xF64AA0],eax ; ... ; 862a01 call 0x85f300 ; 862a06 etat=3
75feb8  call 0x85f5a0 ; 75ff11 mov [0x102A368],3            ; fin de scene -> cible = -1
9c6aeb  mov edx,[0x14958B4] ; lea r9d,[rsi+1] ; lea r8,[0x14958B8] ; mov [rsp+0x20],esi ; lea rcx,[0x102A360] ; call 0x761460
358d83  mov edx,[rsi+0x58] ; lea rcx,[0x102A360] ; mov r9d,1 ; mov [rsp+0x20],r12d ; mov r8,rbx ; call 0x761460
33263b  mov ecx,esi ; call 0x85f290                           ; mruby phase_jump
95d610  movsx ecx, word [rcx+rax+0xc] ; movsx r8d,r9b ; inc r8d ; mov rdx,rdi ; call 0x9c6340
9132c5  lea ecx,[rbx+0x7d] ; call 0x9d4400                    ; creation de l'ecran Chapter Select
```
