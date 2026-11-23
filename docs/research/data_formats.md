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
- La logique detaillee des quetes est dans les `*_scp.bin` (scripts compiles) : non decode.

## Quetes

- Noms : `PAUSE_QUEST_NAME_qXXX` (71 quetes nommees). Identifiant decimal dans les tables binaires (31 -> q031).
- `QuestChapterData.qch` : `<4sfIII>` = 'QCH', 1.0, offset 0x14, taille 130, nombre 60. Enregistrement :
  `u16 quete` + 128 octets ; l'octet i correspond a l'entree i de ChapterData.cha ; 0 = quete indisponible dans ce
  chapitre, sinon une valeur 1..4 (sens exact inconnu ; 4 le plus frequent, 2 souvent pour des chapitres 9S, 3 pour
  des quetes A2). Verifie sur q560 (Devola's Request) : chapitres 13-01..17-xx de la route C/D = conforme au jeu.
  (q020 a aussi un octet a l'indice 119, au-dela des 93 chapitres.)
- `QuestProgressInfo.que` : `<4sfIII>` = 'QUE', 1.0, 0x14, taille 24, nombre 125. Enregistrement `<HBBIHHiII>` :
  quete, groupe d'etat, ?(100), ?(1), emplacement 1..5, ?(53), objet requis (-1 = vide), quantite, ?(1).
  = objets a livrer (texte `<ITEM_NAME>: <ITEM_NUM>/<REQ_NUM>`).
- `QuestRewordData.drp` ('DQR') : format .drp ci-dessous, A = 14 o `<7H>` (indice, debut B, nb, 4 inconnus),
  B = (id, valeur 100). Les copies multiples d'un id = quantite. Apres les `nb` entrees il y a toujours 2 entrees
  en plus (ex. 5000 et 500/1200) : probablement argent et EXP, NON verifie. Le lien indice -> quete n'a pas ete trouve
  (242 tables pour ~70 quetes ; sans doute reference depuis les scripts).
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
(skill_act_*, nom anglais non relie : l'ordre de `CORE_ACT_SKILL_NAME_NN` ne correspond pas), 3001-3999 puces,
4001.. capacites, 5020.. succes, 6001.. composition pod, 7001.. picEvent, >= 1000000 archives.

## Points d'acces
Terminaux = objets `ba1000` (Bunker, camp) et `ba1100` (forme de distributeur, groupes `自販機*`) avec le parametre
`codeName = ft_XX`. Deblocage / panne : `MiscState.setvar "ft_XX true|false"` ; `BehaviorTransporterBa.lock`.
22 codes trouves dans NieRAutomata.exe (= 22 noms `CORE_MAP_TRANS_0001..0022`). Aucune table code -> nom n'a ete
trouvee (chaines referencees par le code) : la correspondance de `access_points.json` est DEDUITE (noms des groupes
japonais, commentaires, position) avec un niveau de confiance. Codes sans entite placee trouvee : ft_AP_C, ft_AP_T,
ft_AP_T2, ft_PV (ft_PV apparait seulement dans des commandes setvar). Seuls les placements des hap ont ete lus.

## Fins
`phf/pf30_sub.bxm` : sous-phases `Ending_E..Ending_Z` avec la condition en commentaire japonais (traduction non
officielle ajoutee). `pf10` : `EndRoll_A`, `BackTitle_A/B/CD/True/FIN`, `EndRoll_CD`. Titres : `CREDIT_END_TITLE_NN`.
`SceneStateSystem.set ending_A` (p200) / `ending_B` (pf10) ; succes 0x10 (A), 0x11 (B), 0x17 (C).

## Limites
- Rien n'est lu dans les fichiers monde `wd*/g*.dat` (geometrie uniquement) ni dans les `*_scp.bin`.
- Les XML sont analyses avec `xml.etree` (fichiers locaux du jeu, non fiables par nature mais pas d'entites externes).
