# Formats de donnees NieR:Automata (v1.04 Steam) - recherche

Genere par `tools/extract_research.py` (lecture seule des CPK ; cache disque dans
`%TEMP%/nier_research_cache` ou `$NIER_RESEARCH_CACHE`). Relancer : `python tools/extract_research.py`
(option `--out`). Les fichiers sont extraits un par un ; les gros CPK (data014/015/016) ne sont lus que via leur TOC.

Fichiers produits (dans ce dossier) : `phases.json`, `quests.json`, `endings.json`, `shops.json`, `chests.json`,
`access_points.json`, `items.json`.

## Textes

### .tmd (txtmess/txt_*_us.dat -> txt_*.tmd)
Petit-boutiste. `u32 n` puis n fois : `u32 nbCarCle` (NUL inclus), cle UTF-16LE, `u32 nbCarTexte` (NUL inclus),
texte UTF-16LE. Les fichiers sans suffixe sont en japonais, `_us` = anglais, `_fr` = francais.
Cles utiles : `PAUSE_QUEST_NAME_qXXX`, `PAUSE_QUEST_HELP_QXXX/RUN_n|DONE|CLR|FIN|FAIL_n`, `CORE_ITEM_NAME_%03d`,
`CORE_WP_NAME_<id>`, `CORE_PSV_SKILL_NAME_%03d` (puce = id-3000), `CORE_ARCHIVE_%03d_%03d` (id = 1000000 + a*1000 + b),
`CORE_MAP_TRANS_00NN` (22 points d'acces), `CHAPTER_NAME_CC_SS[_V]`, `CORE_MAIN_SCENARIO_TEXT_*`.
Une variante `_US` d'une cle (ex. `PAUSE_QUEST_NAME_q020_US`) est le texte localise US.

### .mcd (ui/ui_*_us.dat -> mess*.mcd)
En-tete 10 u32 (offset/nombre de : messages, symboles, glyphes, polices, evenements). Evenement 0x28 o :
`u32 hachage, u32 indice message, char[32] cle`. Message 16 o : `u32 offset paragraphes, u32 nb, ...`.
Paragraphe 20 o : `u32 offset lignes, u32 nb, ...`. Ligne 24 o : `u32 offset lettres, u32 0, u32 nb lettres, u32,
float largeur, u32`. Lettres = paires u16 (indice de symbole, crenage), `0x8001`+crenage = espace, `0x8000` = fin.
Symbole 8 o : `u16 police, u16 caractere UTF-16, u32 glyphe`. Offsets relatifs au debut du fichier.
Beaucoup de messages ont 2 paragraphes identiques (variantes) : `mcd()` les dedoublonne.
Cles : `CREDIT_END_TITLE_NN` (titres des fins A..Z), `CORE_MAP_SHOP_00NN` (noms des magasins, NN = Id de
ShopInfoTable), `CORE_MAIN_SCENARIO_TITLE_NNNN`, `CORE_ITEM_HELP_*`, `CORE_WP_HELP_*`.

## Phases

- `core/coreph.dat:PhaseInfo.bxm` : liste de toutes les phases (`Phase name=pXXX`) et noms de sous-phases dans l'ordre.
- `phX/pXXX.dat:pXXX_sub.bxm` (BXM) : `SubPhase` = Name, Comment (japonais), RoomNo, PlayerPos, isRestartPoint,
  ManualMap, BgmStart... Les noms `NN_MM_<route>_<lieu>` donnent la route (A, B, AB, CD) et l'ordre.
- `core/coregm.dat:ChapterData.cha` (selection de chapitre) : en-tete `<4sfIII>` = 'SCH', 1.0, offset 0x14,
  taille 80, nombre 93. Enregistrement : `u8 indice, u8 chapitre, u8 sous-chapitre, u8 variante,
  u32 groupe de routes (0=A, 1=B, 2=A+B, 3=C/D), u32 personnage (1=2B, 2=9S, 3=2B+9S, 4=A2, 6=?),
  u16 phase (0x100 = p100), char[] sous-phase` ; le reste (adresses) est du remplissage. Nom anglais =
  `CHAPTER_NAME_<chapitre>_<sous>[_<variante>]`. Valeur 'personnage' deduite des noms de sous-phase (2B/9S/A2).
- Sauts de phase : action de code `0x227440da` dans les hap.z, champs `<phase>0xf30</phase><subPhase>Ending_G`.
  Liste dans `phases.json:phase_jumps` (fichiers de phase) et `endings.json:ending_jumps` (tous fichiers).

## Logique (hap)

- `*_hap.z` : XML compresse zlib, Shift-JIS, version 0x108 ; quelques `&` non echappes (corriges avant analyse).
  Structure : `<group>` (id, name, parent, tokens), `<hap>` (name, group, actions). `<action>` : `code` (type),
  `name` (japonais, tres parlant), `command/label` + `args` (ex. `MiscState.setvar "ft_RC false"`,
  `SceneStateSystem.set ending_A`, `MiscState.unlockAchievement 0x10`), placements d'objets
  `<layouts>...<value><location><position>x y z</position></location><objId>ba2014</objId><param><value><name>
  ItemTable</name><body>0xa00</body>`.
- `*_hap.pak` : meme contenu en arbres YAX (balises hachees ; `cpk.pak_yax`). Hachages connus : position 0x462CE4F5,
  objId 0x624B37F2, nom de parametre 0x5E237E06, valeur de parametre 0xDBA80BB2. `core/corehap.dat:core_hap.pak`
  n'a pas de version .z : il est lu en YAX (nom de groupe japonais = valeur du noeud racine).
- La logique detaillee des quetes est dans les `*_scp.bin` : bytecode **mruby 1.x** ("RITE0003"), lu par
  `tools/mruby.py` (voir "Scripts mruby" plus bas).

## Quetes

- Noms : `PAUSE_QUEST_NAME_qXXX` (71 quetes nommees). Identifiant decimal dans les tables binaires (31 -> q031).
- `QuestChapterData.qch` : `<4sfIII>` = 'QCH', 1.0, offset 0x14, taille 130, nombre 60. Enregistrement :
  `u16 quete` + 128 octets ; l'octet i correspond a l'entree i de ChapterData.cha ; 0 = quete indisponible dans ce
  chapitre, sinon une valeur 1..4 (sens exact inconnu ; 4 le plus frequent, 2 souvent pour des chapitres 9S, 3 pour
  des quetes A2). Verifie sur q560 (Devola's Request) : chapitres 13-01..17-xx de la route C/D = conforme au jeu.
  (q020 a aussi un octet a l'indice 119, au-dela des 93 chapitres.) Sens des valeurs : voir "Disponibilite des
  quetes" plus bas (1 = 2B, 2 = 9S, 3 = A2, 4 = tout personnage).
- `QuestProgressInfo.que` : `<4sfIII>` = 'QUE', 1.0, 0x14, taille 24, nombre 125. Enregistrement `<HBBIHHiII>` :
  quete, groupe d'etat, ?(100), ?(1), emplacement 1..5, ?(53), objet requis (-1 = vide), quantite, ?(1).
  = objets a livrer (texte `<ITEM_NAME>: <ITEM_NUM>/<REQ_NUM>`).
- `QuestRewordData.drp` ('DQR') : voir la section "Recompenses de quete" plus bas (format corrige, lien
  quete -> table trouve via `getReWard` dans les scripts mruby).
- `MailTable.bxm` : mails (QuestId, StateBefore/After = `qXXX/RUN_n`) ; `MsgQueInfo.bxm` : etats des messages de quete.
- Fichiers `quest/qXXX.dat` : qa*, qb*, qc*, qe*, qf* = quetes internes (evenements, collecte...) sans nom.

## Tables .drp (BoxData, QuestRewordData, CommonEmDropData, UniqueEmDropData)

En-tete `<4sfIIIHH>` : magic ('DBO', 'DQR', 'DEM', 'DUE'), 1.0, offset table A (0x18), taille enregistrement A,
taille enregistrement B (8), nombre A, nombre B. Table A puis table B. B = paires `u32 id, u32 valeur`
(poids/probabilite ou 100 = garanti).

### BoxData.drp (coffres, points de collecte)
A = 24 o `<HHIIHHII>` : `type_objet` (0x2014/0x2015/0x2016 = objId ba2014/ba2015/ba2016, 0x20 = it0020,
0 = generique/it0000, 0x800.., 0x40..), `flags` (7, 12, 15), `box_id` (= parametre ItemTable de l'entite),
`groupe` (0xa00 = coffres communs du monde, 0xb1, 0x1x0/0x5xx...), `debut B`, `nb B`, u32 (0), u32 (1 ; 3 quand
3 objets garantis). Jointure : entite placee avec `ItemTable = box_id` et `type_objet = nombre hexa de l'objId`.
Resultat : 194 entites sur 248 ont un contenu unique (`contents`), dont 121/124 coffres ba201x. Les it0000
(points de collecte) restent ambigus entre groupes. Le sens de `groupe` (0xb1 notamment) n'est pas confirme.

## Magasins (ShopInfoTable.bxm)
`ShopInfo/<shop_xxx>` : `Id` (-> `CORE_MAP_SHOP_%04d`), `StateName` (State_0..6 -> `Shop/1..7` = etat de
progression du magasin), `Item/<nom interne>/State_n = 0|1` (disponible dans l'etat n). Nom interne -> UniqueID via
ItemInfoTable/WeaponInfoTable/PSkillInfoTable. 33 magasins dont 8 de test.

## Objets (ItemInfoTable.bxm, WeaponInfoTable.bxm, PSkillInfoTable.bxm)
Objets : ObjID, UniqueID, MaxNum, NoTrash, DieDiscard, IdType, Category, prix Buy/Sell par etat (State_0 Default,
State_1 Route/B, State_2 Route/C). Plages d'id : 0-999 objets, 1000-1999 armes, 2001-2024 programmes de Pod
(skill_act_*, nom = `CORE_ACT_SKILL_NAME_%02d` avec UniqueID-2000, voir plus bas), 3001-3999 puces,
4001.. capacites, 5020.. succes, 6001.. composition pod, 7001.. picEvent, >= 1000000 archives.

## Points d'acces
Terminaux = objets `ba1000` (Bunker, camp) et `ba1100` (forme de distributeur, groupes `自販機*`) avec le parametre
`codeName = ft_XX`. Deblocage / panne : `MiscState.setvar "ft_XX true|false"` ; `BehaviorTransporterBa.lock`.
22 codes trouves dans NieRAutomata.exe (= 22 noms `CORE_MAP_TRANS_0001..0022`). La correspondance de `access_points.json` est DEDUITE (remplacee par `access_points_resolved.json`, lue
dans l'exe, voir plus bas) (noms des groupes
japonais, commentaires, position) avec un niveau de confiance. Codes sans entite placee trouvee : ft_AP_C, ft_AP_T,
ft_AP_T2, ft_PV (ft_PV apparait seulement dans des commandes setvar). Seuls les placements des hap ont ete lus.

## Fins
`phf/pf30_sub.bxm` : sous-phases `Ending_E..Ending_Z` avec la condition en commentaire japonais (traduction non
officielle ajoutee). `pf10` : `EndRoll_A`, `BackTitle_A/B/CD/True/FIN`, `EndRoll_CD`. Titres : `CREDIT_END_TITLE_NN`.
`SceneStateSystem.set ending_A` (p200) / `ending_B` (pf10) ; succes 0x10 (A), 0x11 (B), 0x17 (C).

## Scripts mruby (*_scp.bin)
Bytecode mruby 1.x, gros-boutiste : en-tete 22 o (`RITE0003`, crc u16, taille u32, `MATZ0000`), section `IREP`
(taille u32, `0000`), enregistrements IREP en profondeur d'abord : `u32 taille, u16 nlocals, u16 nregs,
u16 nb enfants, u32 nb instructions`, bourrage jusqu'a un offset de fichier multiple de 4, instructions u32
(op = i & 0x7f, A = i>>23, B = (i>>14)&0x1ff, C = (i>>7)&0x7f, Bx = (i>>7)&0xffff, sBx = Bx-0x7fff ; opcodes
standard 1.x : SEND 0x20, LOADI 3, STRING 0x3d, LAMBDA 0x40, METHOD 0x46...), pool (`u8 type, u16 long, octets`),
symboles (`u16 long | 0xFFFF, octets, NUL`), puis enfants. Fin : sections LVAR et `END\0`.
Nom de methode d'un irep = `LAMBDA R(a+1), enfant` puis `METHOD R(a), sym` dans le parent
(`resolve_quests.method_names`). Methodes natives liees par `mrb_define_method` (0x295300) ; ex. la classe des
scripts de quete enregistre `addItem` / `getReWard` en RVA 0x303f20.

## Recompenses de quete (QuestRewordData.drp, getReWard)
- Chargement : RVA 0x81ecb0 (chaine `QuestRewordData.drp` RVA 0xce8010, lea 0x81ed0e), pointeur global RVA
  0x1250490 (ecrit en 0x81ed29).
- Format (corrige) : en-tete `<4sfIIIHH>` ('DQR', 1.0, 0x18, 14, 8, 242, 1093). A = 14 o
  `<HHHHHBBBB>` : **id de recompense**, debut B, nb objets, nb argent, nb EXP, tirages objets, tirages argent,
  tirages EXP, 0. Les entrees B de la table sont dans l'ordre objets, argent, EXP (`u32 id|montant, u32 poids`).
  Si tirages < nb (ou poids != 100) : tirage pondere (poids = pourcentage), ex. id 112 = 1 parmi Small/Medium/
  Large Recovery 34/33/33. Plusieurs copies d'un id = quantite. Id objet 10 = `none` (table 47 = 320 EXP seuls).
  Le decodage est prouve par la fonction de tirage RVA 0x7df1d0 (lit [rec+2..+0xa] : nb objets, `[+4]` nb argent
  -> cumule en sortie +0x50, `[+6]` nb EXP -> sortie +0x54, octets `[+8..+0xa]` = tirages).
- Ids : 0-66 = recompenses de fin de quete (popup ; l'exe passe `id < 100` a 0x7cbcd0), 100-132 / 200-239 =
  objets d'histoire ou d'etape, 300-302 = peche / divers, 400-405 et 500-592 = DLC (arenes), 900-938 = vides ou
  1 objet (debug ?).
- Script : `getReWard("NNN")` (chaine decimale). Natif RVA 0x32d660 : conversion en chaine, `strtol(s, 0, 10)`
  (0xbb4cac), puis **RVA 0x7ca970 = attribution** : recherche lineaire de l'id dans A (pas de 14), tirage
  (0x7df1d0), ajout des 20 emplacements d'objets (0x8006f0, id 10 ignore), argent x bonus joueur
  (float a +0x17140 de l'objet 0x3085c0), plafond 9 999 999 G, succes 0x25 si >= 100 000 G, EXP (0x7c9ef0).
  Une 2e routine RVA 0x7cacc0 (meme recherche, sans popup) est appelee par l'interface (0x9305ec, 0x93c1e3,
  0x96e8aa) : sans doute la reception des pieces jointes de mail (`MailTable.bxm Attachment` = id DQR : q170 -> 20,
  q171 -> 21, q180 -> 26, q181 -> 27 ; contenu conforme au web, lien code non trace en entier).
- Resultat `docs/research/quest_rewards.json` (`python tools/resolve_quests.py`) : 188 appels getReWard dans
  quest/, ph1-3, st1, st2 (+ 4 pieces jointes de mail) ; 0 non resolu (q550 passe `reward_item` : 236/237/238/61 selon q550/RUN_1..4).
  Proprietaire = fichier quest/qXXX.dat, sinon nom de methode `this_qXXX_*` (q290 -> q291/q292), sinon etat
  `qXXX/...` teste dans la methode (st1/r140 -> q250, q802 ; st1/r160 -> q072 ; st2/r200 -> q032), sinon
  table `OWNER_GUESS` (deduit, 1 cas : r160 animalrobo1 -> q072). 63 quetes nommees ont au moins une table (61 avec une recompense de fin).
- Validation (section 5 de web_reference.md) : 45/47 quetes conformes. Ecarts : q240 Half-wit Inventor (aucun
  getReWard ; Alien Mask n'est que dans ShopInfoTable : recompense via magasin ; tables 226-235 non referencees
  sont des candidates), q550 (web 17 000 G ; donnees 3000/5000/7000/10000 par palier, 7000+10000 = 17 000).
- Non referencees : 75 tables, dont 38/39 (= 40, Vengeful Warrior q400/q401 sans script), 55 (= 239 YoRHa
  Betrayers), 119-132, 206-235, 302, 400-405, 575, 590/591, 900-938.

## Disponibilite des quetes (QuestChapterData.qch)
Valeur d'un octet (quete, entree de ChapterData) = **personnage requis** : 1 = 2B, 2 = 9S, 3 = A2, 4 = tout
personnage. Preuve : 59/60 quetes conformes a la colonne Route du web (Sh/All3/A2+9S -> 4 partout, 2B -> 1,
9S -> 2, A2 -> 3). Seul ecart : q590 Heritage of the Past = 2 (9S) dans les chapitres communs 03-01..07-04 puis 4
a partir de 08-01 (GP indique "Route B" : coherent). Les fenetres = chapitres de la selection de chapitre ou la
quete existe (pas les prerequis). Detail par quete : `quest_availability.md` / `.json`.

## Limites
- (Corrige par "Positions monde" : les wd*/g*.dat ont 20 hap.pak et des Layout.lay.) Les scripts mruby ne sont parcourus
  que dans quest/, ph*, phf, core, novel, st1/2/5 (pas ba/em/bg...).
- Les XML sont analyses avec `xml.etree` (fichiers locaux du jeu, non fiables par nature mais pas d'entites externes).

## Resolution statique exe (tools/resolve_static.py)

Produit `access_points_resolved.json` et `pod_programs.json`. Toutes les adresses sont des RVA (base 0x140000000).
Hachage des chaines : 0x28EE00 = crc32 zlib (verifie : crc32('ft_PV') = 0x6B5E8223 code en dur dans 0x86F0D0).

### Points d'acces
- 0x109EE0 (initialiseur statique) : crc32 de 27 codes -> tableau u32 0x13FD4A0, dans l'ordre ft_BK, ft_RC, ft_CC,
  ft_CRb, ft_CS, ft_DC, ft_DI, ft_DO, ft_DD, ft_AP, ft_AP_C, ft_AP_T2, ft_AP_T, ft_PV, ft_FC, ft_FC2, ft_FC3, ft_RME,
  ft_RMI2, ft_RMI, ft_SC, ft_AS, re_tower_start, re_tower_cathedral, re_tower_library, re_tower_elevator, re_SC_2Bdie.
- 0x86F0D0(codeName) : cherche crc32(codeName) dans ce tableau (27 entrees) -> `CORE_MAP_TRANS_%04d` (indice+1).
  Donc ft_AP_T2 = 0012 Above Theater, ft_AP_T = 0013 Theater, ft_RMI2 = 0019 Hangar, ft_RMI = 0020 Furnace,
  ft_SC = 0021, ft_AS = 0022 City Ruins: Cave. Cas ft_PV : `CORE_SUB_MAP_AREA_111` ('???') tant que la variable
  `UI_namePV` est fausse. 0x86FD90 = codeName -> indice+1 (ou -1). 0x86F250(numero) : 23-26 -> CORE_MAP_AREA_090
  (The Tower), 27 -> CORE_MAP_TRANS_0021.
- 0x105A90 : 21 crc32 (sans ft_BK) -> 0x13EC770 ; 0x7E43C0(codeName) -> numero de bit (switch, table de sauts
  0x7E45F4) : RC 0, CC 1, CRb 2, CS 3, DC 4, DI 5, DO 6, DD 7, AP 8, AP_C 9, AP_T 10, AP_T2 11, (12 libre), RME 13,
  RMI2 14, RMI 15, AS 16, PV 17, FC 18, FC2 19, FC3 20, SC 21.
- Bits d'activation (terminal deja utilise = present dans le menu Transport) : 0x14957E0, bit n =
  `dword[n>>5] & (0x80000000 >> (n&31))`. 0x7F82D0 = test (ft_BK toujours vrai), 0x818040 = mise a 1 (appelee par le
  terminal ba1100 0x604BD0 a la premiere activation, et par 0x7623D0).
- Variable 'ft_XX' (terminal en marche / en panne) : table nom -> octet 0xF23540, ecrite par `MiscState.setvar`
  (0x3AEBD0) et `FastTravel.enableTransporter` (0x324CB0), lue par `FastTravel.transporterIsEnabled` (0x3587F0).
  `FastTravel.transporterIsReadyToUnlock` = 0x358800 (variable vraie, ou etat de l'objet terminal), `FastTravel.travel`
  = 0x358860. Ces commandes sont enregistrees par 0xB12B0..0xB15B0.
- 0x8BC580 : liste des destinations. Verrous globaux (variables) : WarpLock / Electronic_Lock (rien), TerminalLock
  (ft_RC seul), WarpPartialLock (seuls BK, RC, CC, CRb, CS, PV ; sinon CORE_PM_TM_HELP_11), lock_ft_PV et
  Pascal_Terminal_txt (ft_PV grisee).
- 0x7623D0 : force ft_RC (p100 apres '40_AB_Resistance_Camp_Leader', p200, p300) et ft_CC (sous-phase
  '100_A_Submerge_City_2B') : enableTransporter + bit. Phase courante = 0xF64AA0 {u32 phase, u32 hachage sous-phase} ;
  0x85E180 = phase ==, 0x85E110 = sous-phase >= (ordre de la phase), 0x85E3C0 = sous-phase ==.
- Hap : action 'ファストトラベル条件リセット' (code 0x5797C250, `<codeName>ft_XX`) a chaque terminal ; conditions
  `FastTravel.transporterIsReadyToUnlock` / `transporterIsEnabled` avec `<args>ft_XX</args>` (q170 Terminal Repairs :
  CC, CRb, CS ; p200 : SC, AS). ft_AP_C, ft_AP_T, ft_AP_T2 : aucune reference trouvee dans les hap.

### Programmes de Pod
- Les 3 sites qui formatent `CORE_ACT_SKILL_NAME_%02d` (0xCE8488) : 0x7DAACB (fn 0x7DAA90), 0x7E9631 (fn 0x7E9530),
  0x86E5ED (fn 0x86E4B0, switch de categorie via 0x86FDD0) font tous `lea r9d, [id - 0x7D0]` : indice = UniqueID-2000.
  2001 skill_act_spear = R010 Laser ... 2024 skill_act_sonar = A170 Scanner (17 programmes). Indices sans texte :
  13, 14, 16, 17, 18, 20, 23. Aide = `CORE_ACT_SKILL_HELP_%02d` (meme indice, coherente avec les noms internes :
  wire/Wire, repair/Repair, ride/'ride atop a Pod', sonar/Scanner).

## Parcours des routes (tools/routes_full.py)

`python tools/routes_full.py [routes|endings|enemies|md|all]` -> `routes_full.json`, `endings_triggers.json`
(tools/rf_endings.py), `enemies_by_area.json` (tools/rf_enemies.py), `routes_full.md` (resume). Un fichier de phase
a la fois via le cache de `extract_research`.
- Etapes = `SubPhase` de `pXXX_sub.bxm` dans l'ordre du fichier. Route = jeton du nom `NN[_MM]_<route>_...` :
  A = A + AB, B = B + AB (p100 puis p200), C/D = CD/C/D (p300). Commentaire `Aルート専用` / `Bルート専用` = exclu de
  l'autre route. Exclus : noms hors format, `TEST`, `e3_`, `PlayGo`, commentaires `未使用` / `削除予定`
  (sauf si l'entree est un point de ChapterData). p400 = DLC (Plato, salle g5ac00), hors route.
- Chapitre = entree de `ChapterData.cha` qui commence a cette sous-phase, sinon la precedente dans l'ordre du fichier
  (`chapter_assignment`). En C/D, les blocs A2 (12, 14) et 9S (13, 15-01/02) sont entrelaces dans le fichier : tri par
  numero de chapitre puis ordre du fichier ; `220_CD_Submerge_City_9S` (point de jonction des deux pistes, prouve par
  les sauts 120_95 -> 220_CD -> 220_10 et 180_30 -> 220_10) est place avant 15-03.
- Zone : mot-cle japonais le plus tot dans le commentaire (format `lieu_detail` ; `XからYへ` -> `X -> Y`), sinon jeton
  anglais du nom (RobotM = Abandoned Factory, Submerge_City = Flooded City, Danchi = Desert Housing...), sinon zone
  majoritaire de la salle. RoomNo r001 = monde ouvert ; g50001 Tour, g50100 Copied City, g52001 usine souterraine,
  g5a000/g5a100/g5a200 Meat/Soul/God Box ; r000 = generique E. Traduction non officielle.
- Position de depart = `PlayerPos` (x y z [rotation Y]) ; 0 0 0 = cinematique / STG / menu (null).
- **Jetons de groupe hap** : `<group><tokens><value><code>0xF3B97443</code><id>X</id>` avec X = **crc32(nom de
  sous-phase)** (verifie sur p300) ; le groupe le plus proche (en remontant `parent`) portant des jetons donne les
  sous-phases ou le hap est actif. Sert a `phase_transitions[].from_subphases` (187/189 resolus).
- Quetes par etape = octets de QuestChapterData.qch de l'entree de chapitre, filtres par personnage (1 2B, 2 9S, 3 A2,
  4 tous). Points de non-retour = derniere entree de la route ou la quete existe < derniere entree ayant des quetes.
- Frontieres (hap) : fin A = p200 `..M1090_S0320_GM_a` -> pf10 EndRoll_A ; fin B = `..M1090_S0320_GM_b` -> p300
  00_CD_Bunker_2B ; choix final 330_CD_Tower_Versus -> 335_CD_Tower_sele9S / seleA2 -> 340_C_Tower_9Swin
  (`フェーズジャンプ_CEnd`) / 340_D_Tower_A2win (`_DEnd`) -> pf10 EndRoll_CD ou pf31 (`_TrueEnd`, STG du generique E)
  -> 360_CD_TrueEnd_FIN (reussite) ou pf10 BackTitle_CD (abandon). Choix de personnage C/D : actions
  `フェーズジャンプ_A2_1/_A2_2/_9S_1/_9S_2` (hap `UI画面会話`, `フェーズジャンプ(12)`/`(23)`).
- Objets cles : Fuel Filter Ch05 = getReWard 107 (`pascal_ON_TALK_ev1`, p100) puis `addItem('item_uq_filter', -1)`
  dans `ane_ON_TALK_ev0` (remis a Anemone) ; Ch14 = `this_q300_91_itemCheck_a1` (+1 Rigid Tree Bark), test
  `item_uq_pascalReq_3?`, `pascal_ON_TALK_ev2` (-1 ecorce, getReWard 107). Cles d'acces : getReWard 101/102/103 (p300) ;
  verification dans l'exe : vtable `Bg6001` (unite principale / secondaire de la Tour, placee par quest/qb20 en
  (102.4, -68.4, 354.0)) : 0x5EA5B0 = possede une des 3 cles (0x7E3D30 = nombre d'un objet par nom), 0x574200 = retire
  une cle (0x7CA680) et met un drapeau par cle ; 0x31DCF0 refuse de redonner une cle deja inseree. Elevator Key :
  getReWard 224 (q330 `finish`) ; test `count(item_uq_mallKey) > 0` dans 0x8344B0 (objet non identifie).
  A170 Scanner : aucune remise trouvee (scripts, DQR) ; seul test = condition hap `Pl0000.isActiveSkillSonar` (dialogue
  tutoriel p200). Les conditions hap sont `<condition><state><label>` (INSIDE, SceneStateSystem.has,
  Pl0000.hasBuddy...) : aucune condition d'objet dans les hap.

## Ennemis et donnees d'unite (tools/rf_enemies.py)
- `core/coregm.dat:EmList.bxm` : sections Category (CategoryID -> UIID -> `PAUSE_ENEMY_CTGR_%02x`), Type (TypeID -> UIID),
  EmList (189 entrees : SortID, Category, Type, **SaveID** = numero de donnee d'unite (175 distincts), EmID, UmID,
  setType, setFlag, bDie, bTalk, QueID, UIID (variante), RepUIID (autre description, 0x999a/b)).
- Nom affiche (Intel > Unit Data) = `PAUSE_ENEMY_%04x` (format lu dans l'exe RVA 0xce6640 ; valeurs UIID lues en
  hexadecimal : Type UIID '110' -> PAUSE_ENEMY_0110) dans `ui/ui_pause_us.dat:messpause.mcd` (cle `_US` prioritaire) ;
  description = meme cle dans `txtmess/txt_pause_add_us.dat`. `CORE_RECORD_ENEMY_*` (messdlc1) = noms generiques seulement.
- Lien placement -> donnee : (objId, setType) = (EmID, setType) de EmList (setType absent = 0). DEDUIT. Le setFlag de
  EmList (0/1 = bouclier / bouclier EM) ne correspond pas au setFlag (masque de bits) des placements : non resolu.
- Placements : valeurs avec `objId em*` dans hap.z (XML), `*_hap.pak` (si pas de hap.z) et `*_grp.pak` (YAX ; balise =
  **crc32 du nom de balise**, ex. setType 0x192fea25). Deux formes : ennemi pose (`location/position`, `setType`, `setFlag`,
  `setRtn`, `param` Lv/Lv_B/Lv_C) et generateur `敵発生機` (`points/nodes/value/point`, `items/value` objId+rate+setType,
  `levelRange`, `spawnRange`).
- Jetons de groupe : code 0xf3b97443 = crc32(nom de sous-phase), 0x35c92545 = crc32('qXXX/ETAT') ; remonter les parents.
- Salles : r100 City Ruins, r110 Resistance Camp, r120 Abandoned Factory, r130 Amusement Park, r140 Pascal's Village,
  r150 Desert, r160 Forest/Forest Castle, r170 Flooded City, r200 City Ruins crater/underground (+ Copied City lock,
  Tower, ravine), r500 Tower, r501 Copied City, r502 hidden cave, r520 Factory underground, r530 Theater underground,
  r5a2 God Box (deduit des noms de groupes).
- Resultat `enemies_by_area.json` : 5640 placements, 164 types, 145/175 donnees placees ; 30 sans placement (EMP setType 10,
  Gunman, Pascal, Ernst, Hegel, variantes Adam/Eve, 21O, Zombie Clown, variantes bouclier...).
- Non lus : scripts mruby (EmBase.callEnemy), ennemis de hacking/STG, fichiers wd*.

## Fins : declencheurs (tools/rf_endings.py)
- Source fiable = arbres YAX des `*_hap.pak` et `*_grp.pak` (les `*_hap.z` XML sont incomplets : Ending_M/R/V absents de
  p300_hap.z, Ending_Y seulement dans q900_9e77724b_grp.pak, Ending_N dans st1/r140).
- Balises YAX = crc32 zlib du nom de balise (subPhase 0xacf1615, name 0x5e237e06, args 0x161b2ea2) ; noms recuperes dans les hap.z.
- Table des groupes : `*_hap.pak` version 4, en-tete `<III>` (4, ?, h) ; a h+4 : u32 taille + zlib d'un YAX
  `count/group(id,name,parent,tokens,comment)`.
- Jetons : code 0xf3b97443 = sous-phase (id = crc32 du nom), 0x35c92545 = etat SceneState (crc32, ex. Route/A 0x583082bb,
  Route/B 0xc139d301), 0x5cda8ece = salle (0x502 -> r502).
- puid = reference par id a une action/hap du meme fichier ; 0xcecad9ce = objet systeme (id = crc32 du nom).
- Saut : action 0x227440da (`<phase>0xf30</phase><subPhase>Ending_X</subPhase>`) ; 0xf10 = pf10 (EndRoll_A/CD, BackTitle_*),
  0xf31 = pf31 (STG du generique, fin E).
- exe : 0x7614a0(phase, nom de sous-phase) = saut de phase. Ending_K 0x991b77 (objet 'fish_16' = Mackerel) ; Ending_T
  0x899125/0x9893e8/0x98ba08 (puce 0xd0a = OS Chip, test 0x7f54c0) ; Ending_U/W 0x83dc4b (fin du game over : [0x11eac20]
  1 -> U, 0 -> W) ; ContinueState.setBadEnd = 0x80e200 (qb40 Bunker `自爆バッドエンド` -> setBadEnd 1). Table des 22 noms
  Ending_E..Z en 0x85ff90 (initialisation, pas un declencheur).
- C/D : exe 0x863730 : SceneState select/9S -> ending_C, select/A2 -> ending_D ; p300 340_C_Tower_9Swin (CEnd) /
  340_D_Tower_A2win (DEnd) ; INVERSE du web (A2 -> C) ; titre affiche non trace.
- Non resolu : W (aucun setBadEnd 0 trouve), invite Pod 153 (fin E), saut de fin de la route B vers pf10.

## Positions monde (tools/world_positions.py -> world_positions.json)

Relancer : `python tools/world_positions.py [--out docs/research] [--no-wd]` (un .dat a la fois ; 1er passage
lent : les cellules wd* sont decompressees une fois, seuls leurs membres hap/pak/scp/lay sont gardes dans
`%TEMP%/nier_research_cache/world_positions`). 588 fichiers : ph*, phf, quest, st1/2/5, core, wd1-5/wda.

### Corrections importantes par rapport aux passes precedentes
- **`*_hap.z` est un XML d'edition PERIME.** L'exe (RVA 0x3b8020) charge d'abord `%s_hap.pak` (0x3b4d00) et ne
  lit `%s_hap.z` que si le .pak manque. Le .pak a plus de haps et des contenus differents (ex. r200 : points de
  collecte ItemTable 0xa14/0xa15/0xa11 dans le .pak, 0xa00 dans le .z). Toutes les donnees viennent donc du .pak.
- **`*_<groupe hexa>_grp.pak`** (format `%x_grp.pak` dans l'exe) = haps supplementaires d'un groupe (charges a la
  demande) : ils n'etaient pas lus avant. `core/corehap.dat` contient aussi `qa*_hap.pak`.
- Les entites SANS parametre ItemTable etaient ignorees (ItemTable absent = table 0) : 265 coffres au lieu de 124.
- Les correspondances "uniques" vers les enregistrements BoxData de salle 0xb1 etaient fausses (voir ci-dessous).

### Format .pak (hap)
En-tete `u32 ?, u32 taille decompressee des groupes, u32 offset H` ; de 12 a H : entrees `u32 type, u32 taille,
u32 offset` (une par hap, arbre YAX eventuellement zlib) ; a H : `u32 taille compressee` + zlib = arbre YAX des
groupes (`count`, `group{id, name, parent, tokens{size, value{code, id}}, attribute, priority}`).
Balises YAX = **crc32 zlib du nom de balise** (position 0x462CE4F5 = crc32('position'), etc.) : on les renomme avec
le vocabulaire des hap.z. Un arbre de hap = `name, id, group, size, action*` ; une action peut avoir
`layouts/{normal,hard,extream}/layouts/value{id, location{position, rotation}, scale, objId, setType, setRtn,
alias, param{value{name, code, body}}, comment}`, `script{id}` et `variables{value{name, value{code 0xd8efbb45,
value = id d'entite}}}`.
- Script d'une action : membre `<prefixe>_<id en %x>_scp.bin` (ex. r160 action script 0x441c44e3 ->
  `r160_441c44e3_scp.bin`). Les variables pointent vers des entites **de n'importe quel fichier** (les scripts de
  quest/qXXX visent des PNJ places dans st1/rXXX). Les methodes mruby `<variable>_ON_TALK...` = dialogue du PNJ.
- Jetons de groupe : id = **crc32 du nom**. code 0xf3b97443 = sous-phase (ex. crc32('50_00_A_City')), code
  0x35c92545 = etat de scene ('Route/A' 0x583082bb, 'Route/B' 0xc139d301, 'Route/C' 0xb63ee397, 'Route/D'
  0x285a7634, 'PL/2B', 'PL/9S', 'qXXX/RUN_n', 'Serious_RC', 'Tower_Appear'...). attribute & 0x10 = condition
  inversee (ex. '森のキャンプが出てない時' 0x50 / '森の出張レジスタンスキャンプ' 0x40, memes jetons). 1003/1163
  jetons resolus par dictionnaire (sous-phases, etats de quete generes, chaines exe/scripts/hap).

### BoxData : algorithme de l'exe (RVA 0x7e37d0, appele par 0x4e5ba0 pour les objets a ItemTable)
- cle = `[objet+0x5b8]` = objId numerique : prefixe 'ba' = 0xf, 'it' = 0x7, 'bg' = 0xc (bg0800..0805 = coffres
  bg avec ItemTable : verifie par jointure). Le champ u32 a +0 de l'enregistrement A = cle (0xf2014...).
- `ItemTable` lu **en hexa** meme sans '0x' (q440 : '100' -> 0x100 = enregistrement (0x160, 0xf2015, 0x100)).
- salle = 0x7eefc0 : variable globale RVA 0x130c890 (0x550 force si le bit 0x400000 de RVA 0x1029b00 est mis ;
  calcul depuis la position en phase 0xe01/0xe03). Recherche : 0 < box < 0xa00 : (salle, cle, box) puis
  (salle, cle, 0) ; box = 0 : (salle, cle, 0) ; box > 0xa00 : (0xa00, cle, box) ; toujours repli final
  (0xa00, cle, 0xa00). Les enregistrements de salle 0xb1 (box 0x0..0xa63) ne sont choisis que dans la salle 0xb1.
- Salle par entite : nom du fichier st*/rXXX (sur) ; sinon salles candidates par proximite des entites des
  salles connues (<= max(60, 1.5 x min)) ; si toutes donnent le meme enregistrement -> 'resolved' (confiance
  medium), sinon 'ambiguous_room' avec le contenu par salle.

### Resultats (v1.04)
- Coffres : 265 entites (260 positions distinctes) ba2014 131, ba2015 71, ba2016 58, bg0800-0805 5 ; contenu
  resolu pour 265/265 (234 high, 31 medium). Points de collecte : 1090 (it0000 1025, it0020 56, it0003 4,
  it0040/41 5) ; 990 resolus high/medium, 95 ambigus (surtout core_hap, salle inconnue), 5 sans enregistrement
  (it0003 : pas de BoxData pour la cle 0x70003).
- PNJ de quete : donneur = PNJ dont la methode de dialogue contient `qXXX/RUN_1`, rendu = `qXXX/DONE`.
  71 quetes nommees : 55 donneur trouve, 11 seulement entites du script (q070, q095, q150, q162, q170, q181,
  q221, q360, q540, q561, q900), non resolus q085, q171, q401, q403, q920.
- Marchands (methode de dialogue contenant le nom du magasin) : 20 PNJ trouves ; shop_chipEmile/rareEmile/
  rareChipEmile = scripts trouves mais via une methode commune (`shop_branch`) -> candidats seulement ; non
  trouves : shop_CS_Grocery, shop_CD_Grocery (arenes DLC ?) + 8 magasins de test.
- Terminaux : 19/22 codes ft_ avec position (ba1000/ba1100 `codeName`) ; aucun placement pour ft_AP_C, ft_AP_T,
  ft_AP_T2 (ni les re_tower_* / re_SC_2Bdie).
- Peche : zones = objets `bga104` (BehaviorFishingArea), 18 haps de zones. Tables =
  `core/core.dat:FishParam.csv` (`indice, etfXXX, poids`, indices 0-8 et 20 remplis). NON resolu : quel indice
  s'applique a quelle zone (champs +0x3ec8/+0x3ecc de l'objet de peche, RVA 0x59bf30, aucun parametre dans le hap)
  et la correspondance etfXXX -> fish_NN (8001-8041, noms `CORE_FISH_NN`). etf040/etf041 choisis selon le
  personnage (cle 0x10200).
- Objets uniques : 67 dans des coffres/points (MaxNum 1, armes, programmes de Pod : skill_act_ride, _hold,
  _fixedBattery via it0040/it0041), 34 donnes par `addItem` de scripts (PNJ donneur via la methode).
- `Layout.lay` (117 cellules wd) : decors bg/bh et quelques ba (ba0000, ba010x, ba55xx...) sans ItemTable ; aucun
  coffre ni point de collecte. Archives ba/, em/, bg/, bh/, it/, et/, um/ : ni hap ni script (modeles, motions,
  col, ObjectParam.bxm de rendu seulement).
