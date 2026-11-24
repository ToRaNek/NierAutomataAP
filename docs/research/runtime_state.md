# Etats d'execution lisibles en memoire (NieR:Automata v1.04 Steam)

Analyse **statique** (exe + data en lecture seule, jeu jamais lance ni attache). Toutes les adresses sont des RVA
(base du module 0x140000000) ; le client lit `base + RVA` avec ReadProcessMemory, sans appel distant.
Donnees machine : `runtime_state.json`, regenere par `python tools/runtime_state.py` (qui re-verifie chaque fait
dans l'exe : `verify_exe()` echoue sur une autre version). Controles hors ligne :
`--save <SlotData_N.dat>` et `--snap tools/snaps/x.bin`.

Niveaux de confiance : **haute** = lu dans le desassemblage et recoupe par une donnee independante (fichier de
sauvegarde reel, photo memoire `tools/snaps`, constantes de l'exe) ; **moyenne** = lu dans le desassemblage seul ;
**faible** = deduit.

## Resume pour le client

| Fait | Lecture | Confiance |
|---|---|---|
| Etat de scene X actif | tableau trie `[0xFC2718]` (n = `[0xFC2720]`, entrees 0x20) ; X actif ssi une entree a `u32 [[e+0x10]+0x20] == crc32(X)` | haute |
| Quete terminee | `i32 [0x14946D0 + 4*i]` (i = indice de la table exe) dans {2, 3, 4} ; ou etat `qXXX/DONE` / `qXXX_DONE` | haute |
| Point d'acces active | bit n de `u32 [0x14957E0]` : `v & (0x80000000 >> n)` | haute |
| Fin obtenue | A..E : etats `ending_A/B/C/D/CD` ; F..Z : bits 9..29 de `u32 [0x14957D8]` | haute (A-D, F-Z), moyenne (E) |
| Route | etat actif du groupe `Route` (`Route/A`, `Route/B`, `Route/C`) ; phase `u32 [0xF64AA0]` | haute |
| Personnage | `u32 [0x11E1F84]` : 0x10000 2B, 0x10200 9S, 0x10100 A2 ; ou etat du groupe `PL` | moyenne (instant de mise a jour) |

## 1. Etats de scene (SceneStateSystem)

### Hachage - confiance haute

`hash(nom) = crc32 zlib(nom complet ASCII)`, casse conservee, 32 bits **sans masque**, groupe compris
(`crc32("q170/DONE") = 0x6565667C`). Ce n'est PAS le `key_hash` des textes (crc32 en minuscules & 0x7fffffff, 0x14C5B0).
Fonction 0x28ECC0 (table 0xD81190 = table crc32 standard) ; 0x28EE00 = strlen + crc ; 0x28EE30 = (ptr, len).

Verifications (toutes refaites par l'outil) :
- `0x356884 cmp dword ptr [rax+0x20], 0x26b80d1f` = crc32("DONE") ;
- 0x9CC290 compare les sections du document de sauvegarde a 0x18B8C0DE "Scene", 0x6B8CE530 "SceneState",
  0xCAC46EBE "Flags", 0x3D0B49D0 "Values", 0xBF1CD3C3 "version" ;
- 86 sites `mov edx, imm32 ; lea rcx,[0xFC2680] ; call 0x495A70` : les 86 immediats sont le crc32 d'un etat declare
  (ex. 0x7A76C1 `mov edx, 0xc139d301` = "Route/B", 0x912D74 0x6570125A = "ending_C", 0x8F8446 0xAEC1C5CE = "WarpLock") ;
- donnees : le puid hap `0x35c92545` = crc32("@SceneState") ; aucun doublon de crc32 parmi les 1185 etats ;
- sauvegarde reelle `SlotData_0.dat` : les 25 noms de la section `SceneState` sont ecrits dans l'ordre croissant de
  leur crc32 (= ordre du tableau en memoire).

### Conteneur - confiance haute

Objet global `hap::scene_state::SceneStateSystem` en **0xFC2680** (construit par 0xB06F0, nom `@SceneState`).

| Offset | RVA | Contenu |
|---|---|---|
| +0x60 | 0xFC26E0 | `DynamicArray<SceneState>` **registre** : +8 ptr (0xFC26E8), +0x10 nombre (0xFC26F0), +0x18 capacite |
| +0x90 | 0xFC2710 | `DynamicArray<SceneState>` **etats actifs** : ptr **0xFC2718**, nombre **0xFC2720**, capacite 0xFC2728 |
| +0xC0, +0xF0 | | deux autres tableaux (liaisons, non utilises ici) |

`SceneState` (0x20 o) : `+0x00` chaine du groupe, `+0x08` chaine du nom, `+0x10` chaine du nom complet, `+0x18` u32 rang
dans le groupe. Chaque champ pointe un enregistrement de chaine internee (table 0xF8C4E0, 0x150E70) :
`+0x20 u32 crc32`, `+0x28 char*` (= enregistrement + 0x38), `+0x30 u64 compteur`, `+0x38` caracteres.
`SceneStateName` (0x354980) coupe au **premier** `/` : groupe avant, nom apres ; sans `/` le groupe est vide.

Le tableau actif est **trie par crc32 croissant du nom complet** ; tous les tests sont des recherches dichotomiques :

```
760a44  mov r8, [rcx+0xa0]          ; nombre
760a4e  mov r9, [rcx+0x98]          ; tableau
760a6d  mov r10, [rdx+0x10]         ; nom complet cherche
760a7a  shl rax, 5                  ; entrees de 0x20
760a7e  mov rdx, [rax+r9+0x10]      ; entree.nom complet
760a88  mov edx, [rdx+0x20]         ; son crc32
760a95  cmp edx, [r10+0x20]
```
0x495A70 fait la meme chose avec le crc en `edx` (310 sites) ; 0x33DFA0 = `SceneStateSystem.has`.
Recoupe par les photos memoire : `[0xFC26F0] = 1185` (= nombre d'etats declares dans core_hap.pak),
`[0xFC2720] = 29..30`, capacites 2048 / 64.

### Ecriture

- `SceneStateSystem.set` = 0x354B20 -> 0x356800 : l'etat doit exister dans le registre (0x326D30), sinon refus.
  **Si le groupe n'est pas vide, tous les etats actifs du meme groupe sont retires (0x321DF0)** : un groupe a au plus
  un etat (`q150/RUN_18` remplace `q150/RUN_17`, `Route/B` remplace `Route/A`, `PL/9S` remplace `PL/2B`).
  Si le nom est `DONE` et le groupe `qXXX` (4 caracteres), l'exe pose aussi l'etat sans groupe **`qXXX_DONE`**
  (s'il est declare) : il survit aux changements ulterieurs du groupe.
- `reset` 0x34F8E0 (retire un etat), `clear` 0x321DC0 (tout ; seul appel direct : menu titre 0x9B4380, sinon
  commande hap), `clearGroup` 0x321DF0. Aucun des trois ne passe par 0x3F1C60.
- mruby : `scene_state?` 0x333BE0, `set_scene_state` 0x335510, `reset_scene_state` 0x333820,
  `clear_scene_state` 0x329B40, `forward_scene_state` 0x32CDF0 -> 0x328380 (si l'etat courant du groupe a un rang
  inferieur a la cible, passe a l'etat de rang +1 ; scripts : 634 set, 64 reset, 21 forward).
- Apres chaque set : 0x35CC40 (signature de changement) et **0x3F1C60** (tableau d'etat des quetes, section 2).

### Registre

1185 etats declares dans `core/corehap.dat:core_hap.pak`, arbres `SceneState` (tables `Scene_State_subQuest` 772,
`_Scenario` 317, `_Player` 16, `_Quest_negishi` 24, `_Quest_hasegawa` 3, `_Quest_rokumoto` 56). Liste complete avec
hachage, groupe et rang dans `runtime_state.json:scene_states.registry`. Exemples :
`q150/RUN_18` 0x48455AA4, `q170/DONE` 0x6565667C, `q330/RUN_5` 0x17F27AA1,
`ShoppingMall_ElevatorUnlock` 0x8BBBB191, `q080Mail/CLOSE` 0xEC8E4A41.

### Persistance - confiance haute

Les etats ne sont **pas** dans un champ binaire : a la sauvegarde, 0x9CC290 ecrit un document texte dans le bloc de
l'emplacement ; le chargement (0x9CB320, appele en 0x9C6AE6 sur ce meme tampon) le relit.

- Bloc d'emplacement en memoire : **0x145C2D0**, 0x399C0 o (0x9C3A20) ; fichier `SlotData_N.dat` = 0xC o d'en-tete +
  ce bloc (235980 o) : `offset fichier = RVA - 0x145C2D0 + 0xC`.
- Texte hap : **0x145C340**, 0x30000 o (fichier 0x7C). Format : `version v0.0.2`, sections `Scene` (actions hap),
  `SceneState` (une ligne ` <nom>` par etat actif), `Flags` (variables MiscState vraies, ex. ` ft_CRb`).
- Ce texte n'est rempli qu'a la sauvegarde / au chargement (nul dans une partie jamais sauvegardee : photos
  `tools/snaps`) : **ne pas l'utiliser pour l'etat courant**, seulement pour un controle.

### Algorithme de lecture

```python
ptr, n = read_u64(base + 0xFC2718), read_u64(base + 0xFC2720)      # relire a chaque passe (reallocation)
raw = read(ptr, n * 0x20)
active = set()
for i in range(n):
    rec = u64(raw, i * 0x20 + 0x10)          # enregistrement du nom complet
    active.add(HASH_OF_REC.get(rec) or read_u32(rec + 0x20))       # nom : read(rec + 0x38, ...)
is_set = crc32(b"q170/DONE") in active
```
- Cache : les enregistrements de chaine des etats declares sont tenus par le registre ; lire une fois le registre
  (`[0xFC26E8]`, `[0xFC26F0]` entrees) pour construire `pointeur -> crc32` ; ensuite une seule lecture par passe.
- Lecture concurrente : valider `n <= capacite [0xFC2728]` et crc32 strictement croissants, sinon relire.
- Implementation de reference : `tools/runtime_state.py:read_scene_states`.

## 2. Quetes

### Tableau d'etat par quete (bloc de sauvegarde) - confiance haute

L'exe tient un etat entier par quete, **dans le bloc de l'emplacement** (donc sauvegarde tel quel) :

```
3f5ec0  movsxd rax, ecx
3f5ec3  add ecx, -0x42
3f5ec6  lea rcx, [0x145c2d0]
3f5ecf  mov eax, [rcx + rax*4 + 0x38400]     ; indice < 0x42  -> 0x14946D0 + 4*i
3f5ed7  mov eax, [rcx + rax*4 + 0x3856c]     ; indice >= 0x42 -> 0x149483C + 4*i (q085 0x1494944, q095 0x1494948)
```
0x3F5EC0 est l'accesseur du menu Quetes (0x8FB710, qui en tire `PAUSE_QUEST_HELP_Q%03d/RUN_%d|CLR|DONE|FIN|END`).
Ecrivain unique : 0x3F1C60, appele apres chaque `set` d'un etat `q...` ; il cherche la quete dans la table exe
**0xC4D820** (68 enregistrements de 0x34 o : `u32 numero, char nom[5], char pnj[...]`, `+0x2C` DLC, `+0x30` ignoree),
verifie que l'etat pose est l'etat courant du groupe, convertit le suffixe (0x3F5D30) et ecrit la valeur si elle change :

| Suffixe | Valeur |
|---|---|
| (jamais suivie ; `REQ` et `BREAK` ne changent rien) | -1 (initialisation 0x9C5E1A) |
| `CLR` | 1 |
| `DONE` | 2 |
| `END` | 3 |
| `FIN` | 4 |
| `RUN_n` | 100 + n |
| `FAIL_n` | 200 + n |

Indice = position dans la table exe (q020 0, q031 1, q032 2, q040 3, ... q900 65, q085 66, q095 67 ; table complete
dans le JSON). q070 (4), q131 (21) et q470 (44) ont `+0x30 != 0` : indices reserves mais jamais suivis. 65 quetes suivies = 60 + 5 DLC.
Sous-quetes (`q020_1_1` ..., 28 entrees, table 0xC4E5F0) : `i32 [0x14948D0 + 4*j]`.
Recoupe : dans `SlotData_0.dat` et dans les photos memoire (aucune quete commencee) les 66 + 2 valeurs sont -1 et rien
d'autre autour ne l'est ; l'offset 0x38400 est aussi celui de l'initialisation (`[0x148C830 + 0x7EA0]`).

`CLR` n'est **pas** la fin : c'est "objectif atteint, retourner voir le donneur" (ex. q020 : recompense et
`q020/DONE` dans la meme methode `sartre_navinpc_ON_TALK_3_ev0`). Classement de l'exe (0x3F5EE0) : `FIN` -> terminee ;
`DONE` / `END` -> terminee seulement si 0x3F24E0 (pas d'etat `qXXX/FIN` declare, ou ni END ni FIN dans
MsgQueInfo.bxm ; q032 jamais) ; sinon "en cours" (ex. q170 : `DONE`, puis mail 4 "Rewards!" -> `FIN`).

### Regle retenue pour "quete terminee"

`valeur in {2, 3, 4}` (DONE atteint ou depasse). Equivalent par etats : `qXXX/DONE` actif, ou un etat ulterieur du
groupe (`qXXX/END`, `qXXX/FIN`), ou l'etat collant `qXXX_DONE` quand il est declare.
Le tableau est preferable aux etats : une lecture de 264 + 8 octets, et il n'est pas touche par les `reset`
(StateBind `StateOff` peut masquer `qXXX/DONE` sur certaines sous-phases, le tableau garde la valeur).

Colonnes : indice et RVA du tableau ; etat de fin et crc32 ; etat collant ; valeurs "DONE ou apres" ; valeurs que le
menu de l'exe considere terminees.

| Quete | Nom | i | RVA | Etat de fin | crc32 | Etat collant | Valeurs | Menu | Conf. |
|---|---|---|---|---|---|---|---|---|---|
| q020 | Sartre's Melancholy | 0 | 0x14946d0 | `q020/DONE` | 0xfbf74945 | `q020_DONE` 0x0225a98a | 2 | 2 | haute |
| q031 | Machine Examination 1 | 1 | 0x14946d4 | `q031/DONE` | 0x96dc9154 | `q031_DONE` 0x6f0e719b | 2 | 2 | haute |
| q032 | Machine Examination 2 | 2 | 0x14946d8 | `q032/DONE` | 0x1048e3fa | - | 2,4 | 4 | haute |
| q040 | Family Squabble | 3 | 0x14946dc | `q040/DONE` | 0x98277c7f | `q040_DONE` 0x61f59cb0 | 2 | 2 | haute |
| q071 | Animal Care | 5 | 0x14946e4 | `q071/DONE` | 0x6293b547 | `q071_DONE` 0x9b415588 | 2 | 2 | haute |
| q072 | Turf War | 6 | 0x14946e8 | `q072/DONE` | 0xe407c7e9 | `q072_DONE` 0x1dd52726 | 2 | 2 | haute |
| q085 | Mysterious Letter (DLC) | 66 | 0x1494944 | `q085/DONE` | 0x0f4a87b8 | `q085_DONE` 0xf6986777 | 2 | 2 | haute |
| q090 | Underground Colosseum (DLC) | 7 | 0x14946ec | `q090/DONE` | 0xf9f01dbf | `q090_DONE` 0x0022fd70 | 2 | 2 | haute |
| q091 | Gambler's Colosseum (DLC) | 8 | 0x14946f0 | `q091/DONE` | 0x32acce1a | `q091_DONE` 0xcb7e2ed5 | 2 | 2 | haute |
| q092 | Trial of Sand (DLC) | 9 | 0x14946f4 | `q092/DONE` | 0xb438bcb4 | `q092_DONE` 0x4dea5c7b | 2 | 2 | haute |
| q095 | Mysterious Invitation (DLC) | 67 | 0x1494948 | `q095/DONE` | 0xa93d8c0c | - | 2,4 | 2,4 | moyenne |
| q100 | Robo Dojo-White Belt | 10 | 0x14946f8 | `q100/DONE` | 0xa0c258f2 | `q100_DONE` 0x5910b83d | 2 | 2 | haute |
| q101 | Robo Dojo-Brown Belt | 11 | 0x14946fc | `q101/DONE` | 0x6b9e8b57 | `q101_DONE` 0x924c6b98 | 2 | 2 | haute |
| q102 | Robo Dojo-Black Belt | 12 | 0x1494700 | `q102/DONE` | 0xed0af9f9 | `q102_DONE` 0x14d81936 | 2 | 2 | haute |
| q103 | Robo Dojo-Red and White Belt | 13 | 0x1494704 | `q103/DONE` | 0x26562a5c | `q103_DONE` 0xdf84ca93 | 2 | 2 | haute |
| q104 | Robo Dojo-Red Belt | 14 | 0x1494708 | `q104/DONE` | 0x3b531ae4 | - | 2,4 | 2,4 | haute |
| q110 | Lost Girl | 15 | 0x149470c | `q110/DONE` | 0x06b55346 | `q110_DONE` 0xff67b389 | 2 | 2 | haute |
| q120 | The Supply Trader's Request | 16 | 0x1494710 | `q120/DONE` | 0x375d49db | `q120_DONE` 0xce8fa914 | 2 | 2 | haute |
| q121 | The Manager's Request | 17 | 0x1494714 | `q121/DONE` | 0xfc019a7e | - | 2,4 | 2,4 | haute |
| q122 | Camp Development | 18 | 0x1494718 | `q122/DONE` | 0x7a95e8d0 | `q122_DONE` 0x8347081f | 2 | 2 | haute |
| q123 | Anemone's Past | 19 | 0x149471c | `q123/DONE` | 0xb1c93b75 | - | 2,4 | 2,4 | haute |
| q130 | Amnesia | 20 | 0x1494720 | `q130/DONE` | 0x912a426f | `q130_DONE` 0x68f8a2a0 | 2 | 2 | haute |
| q140 | Resistance Disappearance | 22 | 0x1494728 | `q140/DONE` | 0x548d7ce1 | - | 2,3,4 | 4 | haute |
| q150 | Jackass's Research | 23 | 0x149472c | `q150/DONE` | 0xf2fa7755 | `q150_DONE` 0x0b28979a | 2 | 2 | haute |
| q160 | Improving Communications | 24 | 0x1494730 | `q160/DONE` | 0xc3126dc8 | `q160_DONE` 0x3ac08d07 | 2 | 2 | haute |
| q162 | Investigating Communications | 25 | 0x1494734 | `q162/DONE` | 0x8edaccc3 | `q162_DONE` 0x77082c0c | 2 | 2 | haute |
| q170 | Terminal Repairs | 26 | 0x1494738 | `q170/DONE` | 0x6565667c | - | 2,4 | 4 | haute |
| q171 | Find a Present | 27 | 0x149473c | `q171/DONE` | 0xae39b5d9 | - | 2,4 | 4 | haute |
| q180 | Data Analysis Freak | 28 | 0x1494740 | `q180/DONE` | 0x932d1695 | - | 2,4 | 4 | haute |
| q181 | Data Analysis Freak 2 | 29 | 0x1494744 | `q181/DONE` | 0x5871c530 | - | 2,4 | 4 | haute |
| q210 | Lord of the Valley | 30 | 0x1494748 | `q210/DONE` | 0x883a54a5 | `q210_DONE` 0x71e8b46a | 2 | 2 | haute |
| q220 | Vanquish the Bad Bot | 31 | 0x149474c | `q220/DONE` | 0xb9d24e38 | `q220_DONE` 0x4000aef7 | 2 | 2 | haute |
| q221 | Play with Us! | 32 | 0x1494750 | `q221/DONE` | 0x728e9d9d | - | 2,4 | 2,4 | haute |
| q222 | Storage Element | 33 | 0x1494754 | `q222/DONE` | 0xf41aef33 | `q222_DONE` 0x0dc80ffc | 2 | 2 | haute |
| q240 | Half-wit Inventor | 34 | 0x1494758 | `q240/DONE` | 0xda027b02 | `q240_DONE` 0x23d09bcd | 2 | 2 | moyenne |
| q250 | Idiot Savant | 35 | 0x149475c | `q250/DONE` | 0x7c7570b6 | `q250_DONE` 0x85a79079 | 2 | 2 | haute |
| q290 | Game Dev Machine Lv.1 | 36 | 0x1494760 | `q290/DONE` | 0xbbd51ac2 | - | 2,4 | 4 | haute |
| q291 | Game Dev Machine Lv.2 | 37 | 0x1494764 | `q291/DONE` | 0x7089c967 | - | 2,4 | 4 | haute |
| q292 | Game Dev Machine Lv.3 | 38 | 0x1494768 | `q292/DONE` | 0xf61dbbc9 | - | 2,4 | 4 | haute |
| q300 | Speed Star | 39 | 0x149476c | `q300/DONE` | 0xe2e75f8f | `q300_DONE` 0x1b35bf40 | 2,4 | 2,4 | haute |
| q330 | Emil's Memories | 40 | 0x1494770 | `q330/DONE` | 0xd30f4512 | `q330_DONE` 0x2adda5dd | 2 | 2 | haute |
| q340 | Photographs | 41 | 0x1494774 | `q340/DONE` | 0x16a87b9c | - | 2,4 | 2,4 | haute |
| q410 | 11B's Memento | 42 | 0x1494778 | `q410/DONE` | 0x4e555d22 | - | 2,3,4 | 4 | haute |
| q440 | Treasure Hunt at the Castle | 43 | 0x149477c | `q440/DONE` | 0x1c6d7285 | `q440_DONE` 0xe5bf924a | 2 | 2 | haute |
| q500 | The Wandering Couple | 45 | 0x1494784 | `q500/DONE` | 0x24885608 | `q500_DONE` 0xdd5ab6c7 | 2,4 | 4 | haute |
| q520 | Data on the Old World | 46 | 0x1494788 | `q520/DONE` | 0xb3174721 | - | 2,3,4 | 4 | haute |
| q532 | Culinary Researcher | 47 | 0x149478c | `q532/DONE` | 0x58a8ed9e | `q532_DONE` 0xa17a0d51 | 2 | 2 | haute |
| q540 | YoRHa Betrayers | 48 | 0x1494790 | `q540/DONE` | 0xd0c7721b | `q540_DONE` 0x291592d4 | 2 | 2 | haute |
| q550 | Reconnaissance Squad | 49 | 0x1494794 | `q550/DONE` | 0x76b079af | `q550_DONE` 0x8f629960 | 2 | 2 | haute |
| q560 | Devola's Request | 50 | 0x1494798 | `q560/DONE` | 0x47586332 | `q560_DONE` 0xbe8a83fd | 2 | 2 | haute |
| q561 | Popola's Errand | 51 | 0x149479c | `q561/DONE` | 0x8c04b097 | - | 2,4 | 4 | haute |
| q562 | The Twins' Request | 52 | 0x14947a0 | `q562/DONE` | 0x0a90c239 | `q562_DONE` 0xf34222f6 | 2,4 | 2,4 | haute |
| q590 | Heritage of the Past | 53 | 0x14947a4 | `q590/DONE` | 0xb11013db | `q590_DONE` 0x48c2f314 | 2 | 2 | haute |
| q640 | Retrieve the Confidential Intel | 54 | 0x14947a8 | `q640/DONE` | 0x5e4875f8 | - | 2,3,4 | 4 | haute |
| q650 | Sorting Trouble | 55 | 0x14947ac | `q650/DONE` | 0xf83f7e4c | `q650_DONE` 0x01ed9e83 | 2 | 2 | haute |
| q651 | Sorting Trouble 2 | 56 | 0x14947b0 | `q651/DONE` | 0x3363ade9 | `q651_DONE` 0xcab14d26 | 2 | 2 | haute |
| q652 | Sorting Trouble 3 | 57 | 0x14947b4 | `q652/DONE` | 0xb5f7df47 | `q652_DONE` 0x4c253f88 | 2 | 2 | haute |
| q660 | Stamp Collecting | 58 | 0x14947b8 | `q660/DONE` | 0xc9d764d1 | `q660_DONE` 0x3005841e | 2 | 2 | haute |
| q680 | Parade Escort | 59 | 0x14947bc | `q680/DONE` | 0x99e81f8c | - | 2,3,4 | 4 | haute |
| q720 | Gathering Keepsakes | 60 | 0x14947c0 | `q720/DONE` | 0xf132405c | - | 2,4 | 4 | haute |
| q770 | The Weapon Dealer's Request | 61 | 0x14947c4 | `q770/DONE` | 0xa30a6ffb | - | 2,4 | 4 | haute |
| q800 | The Recluse | 62 | 0x14947c8 | `q800/DONE` | 0xbf8d43d9 | `q800_DONE` 0x465fa316 | 2 | 2 | haute |
| q801 | The Recluse Stays Home | 63 | 0x14947cc | `q801/DONE` | 0x74d1907c | `q801_DONE` 0x8d0370b3 | 2 | 2 | haute |
| q802 | The Permanent Recluse | 64 | 0x14947d0 | `q802/DONE` | 0xf245e2d2 | `q802_DONE` 0x0b97021d | 2 | 2 | haute |
| q900 | Emil's Determination | 65 | 0x14947d4 | `q900/DONE` | 0x73274347 | - | 2,4 | 2,4 | haute |

Le JSON donne en plus, par quete : etats du groupe dans l'ordre, etats collants (`qXXX_FIN`...), codes MsgQueInfo,
preuve de la recompense (`getReWard` + etat pose dans la meme methode, ou piece jointe de mail), poseurs de chaque
etat terminal, etats `FAIL_n` et `BREAK`.

Cas particuliers :
- **Recompense apres DONE** : l'etat pose avec la recompense principale est `qXXX/FIN` (valeur 4) pour q170, q171,
  q180, q181 (piece jointe du mail `qXXX/DONE -> qXXX/FIN`) et pour q140, q290, q291, q292 (`getReWard` puis
  `set_scene_state("qXXX/FIN")` dans la meme methode). Pour "recompense recue", tester 4 ; pour "quete finie", 2 ou plus.
- **Recompense avant DONE** : q540 (`getReWard("239")` puis `q540/CLR` ; `q540/DONE` pose par `Ane_ON_TALK_ev1`).
- **Recompense non reliee a un etat** (appel isole ou absent des scripts parcourus) : q072, q085, q090, q091, q092,
  q095, q240, q550, q770, q900 : l'etat de fin vient de la declaration et des poseurs de `qXXX/DONE`.
- **q240, q095** (confiance moyenne) : `qXXX/DONE` est declare (et present dans MsgQueInfo) mais aucun appel qui le
  pose n'a ete trouve dans quest/, ph*, st*, core (q240 n'a pas de script dans son .dat ; q095 : seul `q095/FIN` est
  pose par `this_q095_lastmailSend_a0`). Controle d'execution : finir la quete et lire `[0x1494758]` (q240) /
  `[0x1494948]` (q095) : 2 ou 4 attendu.
- **Valeur 3 (END)** : q140, q410, q520, q640, q680 ont une branche `qXXX/END` (fin alternative) ; comptee comme
  terminee, sens exact de chaque branche non trace.
- **Hors table exe** (pas de tableau, pas dans le menu) : q360, q400, q401, q403, q920 (textes presents, contenu
  coupe ; les etats `q401/...` et `q403/...` ne sont meme pas declares, donc jamais actifs) ; q070, q131, q470 sont
  dans la table mais ignorees.
- Les etats `FAIL_n` (200 + n) ne sont pas une fin de quete.

## 3. Points d'acces - confiance haute

Tableau de bits **0x14957E0** (u32[2], dans le bloc de sauvegarde : fichier 0x3951C). Bit n :
`u32le[n >> 5] & (0x80000000 >> (n & 31))` (0x7F82D0 test, 0x818040 mise a 1, indice par 0x7E43C0 ; ft_BK toujours
actif, sans bit). Lu en un seul u32 : `v = read_u32(base + 0x14957E0)`.

| Code | Texte | Bit | Masque u32 |
|---|---|---|---|
| ft_BK | CORE_MAP_TRANS_0001 | - | toujours actif |
| ft_RC | CORE_MAP_TRANS_0002 | 0 | 0x80000000 |
| ft_CC | CORE_MAP_TRANS_0003 | 1 | 0x40000000 |
| ft_CRb | CORE_MAP_TRANS_0004 | 2 | 0x20000000 |
| ft_CS | CORE_MAP_TRANS_0005 | 3 | 0x10000000 |
| ft_DC | CORE_MAP_TRANS_0006 | 4 | 0x08000000 |
| ft_DI | CORE_MAP_TRANS_0007 | 5 | 0x04000000 |
| ft_DO | CORE_MAP_TRANS_0008 | 6 | 0x02000000 |
| ft_DD | CORE_MAP_TRANS_0009 | 7 | 0x01000000 |
| ft_AP | CORE_MAP_TRANS_0010 | 8 | 0x00800000 |
| ft_AP_C | CORE_MAP_TRANS_0011 | 9 | 0x00400000 |
| ft_AP_T2 | CORE_MAP_TRANS_0012 | 11 | 0x00100000 |
| ft_AP_T | CORE_MAP_TRANS_0013 | 10 | 0x00200000 |
| ft_PV | CORE_MAP_TRANS_0014 | 17 | 0x00004000 |
| ft_FC | CORE_MAP_TRANS_0015 | 18 | 0x00002000 |
| ft_FC2 | CORE_MAP_TRANS_0016 | 19 | 0x00001000 |
| ft_FC3 | CORE_MAP_TRANS_0017 | 20 | 0x00000800 |
| ft_RME | CORE_MAP_TRANS_0018 | 13 | 0x00040000 |
| ft_RMI2 | CORE_MAP_TRANS_0019 | 14 | 0x00020000 |
| ft_RMI | CORE_MAP_TRANS_0020 | 15 | 0x00010000 |
| ft_SC | CORE_MAP_TRANS_0021 | 21 | 0x00000400 |
| ft_AS | CORE_MAP_TRANS_0022 | 16 | 0x00008000 |

- **Bit 12** (0x00080000) n'est pas un point d'acces : il est mis par la methode mruby `visible_rm`
  (0x33A610 -> 0x818080(12, 1)) et teste par la carte (0x613FC0). Il est a 1 des le prologue : le masquer.
- Recoupe : `SlotData_0.dat` contient `00 00 08 20` = 0x20080000 = bits 2 (ft_CRb) et 12, et sa section `Flags`
  contient `ft_CRb` ; les photos du prologue n'ont que le bit 12. 0x613FC0 teste les groupes 0x70008000 (CC, CRb, CS,
  AS), 0x06000000 (DI, DO), 0x00C00000 (AP, AP_C), 0x00300000 (AP_T, AP_T2) : coherent avec la table.
- Autres ecrivains : 0x820C39 (`or [0x14957E0], 0x80000000` : ft_RC), 0x7623D0 (ft_RC / ft_CC forces).
- Rappel : ce bit = "terminal deja active" (present dans le menu Transport). "Terminal en marche" est la variable
  `ft_XX` (table 0xF23540, voir data_formats.md).

## 4. Fins

Tableau de bits **0x14957D8** (u32[2], juste avant les points d'acces ; fichier 0x39514), meme convention
(0x9CBD90 mise a 1, 0x9CAE50 test, 0x9CBD60 remise a 0). Dans le bloc de l'emplacement : une fin obtenue avec une
autre sauvegarde n'y figure pas.

| Fin | Source | Detail |
|---|---|---|
| A | etat `ending_A` 0x8B7E7376 ; bit 0 | bit 0 pose a EndRoll_A / BackTitle_A (0x85C21C) |
| B | etat `ending_B` 0x127722CC ; bit 1 | BackTitle_B (0x85C288) |
| C | etat `ending_C` 0x6570125A | 0x863730 : `select/9S` -> `ending_C` |
| D | etat `ending_D` 0xFB1487F9 | 0x863730 : `select/A2` -> `ending_D` |
| E | etat `ending_CD` 0x2868A2FC | pose en 0x85E636 (fin du generique E), avant BackTitle_FIN / BackTitle_CD |
| F..Z | bit 9 + (lettre - 'F') | 0x85FF90 : `Ending_F` -> 9 ... `Ending_Z` -> 29 ; pose par 0x862E90 apres l'affichage du titre |

- Lecture F..Z : `v = read_u32(base + 0x14957D8)` ; fin de lettre L obtenue ssi `v & (0x80000000 >> (9 + ord(L) - ord('F')))`
  (F 0x00400000, G 0x00200000 ... Z 0x00000004). Apres le bit, 0x862EE0 appelle 0x9C9B80(emplacement, bit) qui pose le
  meme bit dans la copie `[0x1422290] + 0x39508` et reecrit le fichier de l'emplacement : la fin survit au retour au
  titre (0x39508 = 0x14957D8 - 0x145C2D0, second recoupement de l'offset).
- Bits 2 / 3 : generique C/D termine (0x85C160 pose 3 si `Route/D`, etat jamais pose en v1.04, sinon 2) : ils ne
  distinguent pas C de D ; utiliser les etats. Bit 8 : jamais ecrit. Bits 4-7 et 30-33 : autres drapeaux uniques
  (messages post-generique, 32 = A2 selectionnee) ; sens non trace, sans rapport avec les fins.
- Le masque du resume de sauvegarde (0x9CD320 / 0x9CCD50, `[resume+0x14]`) confirme la source : 0x1 `ending_A`,
  0x2 `ending_B`, 0x4 `ending_C`, 0x8 `ending_D`, 0x10 `ending_CD`, puis `1 << (bit - 3)` pour les bits 8..29.
- Global (hors emplacement, toutes sauvegardes) : **0x1495E20**, bits 0 / 1 / 2 (3 si `Route/D`) = generique A / B /
  C-D termine (0x9CBDC0, memes sites d'appel que les bits 0-3 de l'emplacement).
- Limites : libelle C / D (conflit noms internes / web, voir data_formats.md "Titre affiche des fins A/C/D") ; la fin
  E efface les sauvegardes si le joueur accepte : `ending_CD` n'est alors lisible qu'entre 0x85E636 et l'effacement.
  Controle d'execution : lire les etats actifs pendant le generique E.

## 5. Route et personnage

- **Route** (confiance haute) : groupe exclusif `Route` : `Route/A` 0x583082BB, `Route/B` 0xC139D301,
  `Route/C` 0xB63EE397 (`Route/D` 0x285A7634 declare, jamais pose). Poses par StateBind selon la sous-phase.
  Presents dans la sauvegarde reelle (`Route/A`, `PL/2B`).
- **Phase courante** (confiance haute) : **0xF64AA0** = `{u32 phase (0x100 = p100), u32 key_hash(sous-phase),
  char nom[0x20]}` ; le hachage est ici crc32(minuscules) & 0x7fffffff. Photos : p100, `00_85_A_RobotM_Pro_2ndArea`,
  0x24C4B954. Le nom donne la route (`_A_`, `_B_`, `_AB_`, `_CD_`) sans lire les etats.
- **Personnage** : groupe exclusif `PL` : `PL/2B` 0x6940AA43, `PL/9S` 0xE004537A, `PL/A2` 0x3D57F14A (+ variantes
  `PL/2B_Armed`, `PL/2B_Armed_NoMask`, `PL/2B_Dying`, `PL/9S_2Barm`, `PL/9S_NoPatch`, `PL/9S_2Barm_NoPatch`).
  0x7C7B00 les traduit en identifiant d'objet joueur : **`u32 [0x11E1F84]`** = 0x10000 (2B, pl0000), 0x10200 (9S),
  0x10100 (A2) ; sans etat `PL/*`, `Route/A` pose `PL/2B` et `Route/B` pose `PL/9S`. Photos : 0x10000 au prologue.
  Confiance moyenne sur l'instant : 0x7C7B00 n'a qu'un appelant (0x761A30, preparation de scene) ; pendant un
  changement de personnage en cours de phase, la valeur peut suivre le chargement. Controle d'execution : lire
  `[0x11E1F84]` et le groupe `PL` pendant une bascule A2 / 9S de la route C.
- `Buddy/9S|2B|A2|Auto` (groupe `Buddy`) = partenaire.

## Ce que l'analyse statique ne tranche pas

| Point | Controle d'execution qui tranche |
|---|---|
| Rang `+0x18` des entrees (base 0 ou 1, egal a l'ordre de declaration ?) | lire le registre `[0xFC26E8]` et comparer a `rank_in_group` du JSON |
| Reallocation du tableau actif (capacite 64 observee) | surveiller `[0xFC2718]` quand le nombre depasse la capacite |
| Poseur de `q240/DONE`, `q095/DONE` | finir la quete, lire le tableau d'etat |
| Branches `END` (valeur 3) de q140, q410, q520, q640, q680 | lire le tableau a chaque fin alternative |
| Sens des bits 4-7, 30-33 de 0x14957D8 | photo avant / apres chaque generique |
| Instant de mise a jour de `[0x11E1F84]` | lecture pendant un changement de personnage |
| `ending_CD` apres la fin E avec effacement | lecture pendant le generique E |
| Etats masques par StateBind `StateOff` (ex. `[!ending_A] !q120_DONE`) | comparer tableau d'etat et etats actifs apres un changement de route |
