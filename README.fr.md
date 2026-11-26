# NieR:Automata pour Archipelago

Monde Archipelago (`.apworld`) et client pour **NieR:Automata (PC Steam, v1.04)**, toutes les routes.
Le client lit et modifie la memoire du jeu en cours (aucun fichier du jeu n'est modifie).

## Installation
**Avec le lanceur** : telecharge `NierAutomataAP.exe` dans les Releases et lance-le. Il trouve Archipelago,
installe/met a jour le `.apworld` dans `custom_worlds`, puis ouvre le client NieR:Automata.
Un lien `archipelago://pseudo@serveur:port` peut lui etre passe (ou associe aux liens archipelago://).

**A la main** : copie `nier_automata.apworld` dans `<Archipelago>/custom_worlds`, puis
Launcher Archipelago -> *NieR:Automata Client*.

Prerequis : NieR:Automata **Steam v1.04** (la version Steam actuelle : la mise a jour de novembre 2026,
build Steam 26534214, il suffit de laisser Steam mettre le jeu a jour), Archipelago **0.6.8+**. Celui qui genere la partie doit aussi
avoir le `.apworld`. Modele de reglages : `NieR Automata.yaml`.

**Le mod (`dinput8.dll`, facultatif sous Windows)** : un petit fichier pose a cote de `NieRAutomata.exe`. Le
lanceur l'y copie tout seul (il cherche le jeu dans tes bibliotheques Steam ; `--game="dossier"` pour lui dire ou,
`--no-mod` pour ne pas l'installer). A la main : copie `dinput8.dll` des Releases dans le dossier du jeu. Il fait
deux choses :
- il dessine un panneau raye avec le nom du Pass manquant en travers de l'entree de chaque zone verrouillee, et
  t'y arrete (voir *Zones verrouillees*) ;
- il permet au client de parler au jeu par une connexion locale au lieu d'ouvrir le processus du jeu de
  l'exterieur : c'est ce qu'il faut sous Linux / Proton.

Sans le mod, tout le reste marche comme avant sous Windows : une zone verrouillee te remet simplement ou tu etais.
Si un autre mod utilise deja `dinput8.dll` dans le dossier du jeu, le lanceur n'y touche pas et le dit.
La connexion n'ecoute que sur ta machine et demande une cle que le mod ecrit dans ton profil a chaque lancement
du jeu. Pour retirer le mod, supprime `dinput8.dll` du dossier du jeu.

**Linux / Proton (non teste par l'auteur)** : mets `dinput8.dll` dans le dossier du jeu et regle les options de
lancement Steam sur `WINEDLLOVERRIDES="dinput8=n,b" %command%`. Lance ensuite le client Archipelago en natif. Le
client cherche la cle du mod dans le prefixe Proton du jeu, sous les dossiers Steam habituels ; si ta bibliotheque
est ailleurs, donne le fichier avec `NIER_AP_MOD_TOKEN_FILE`
(`.../compatdata/524220/pfx/drive_c/users/steamuser/AppData/Local/NierAutomataAP/mod_token`).

## Jouer
1. Lance le jeu et commence une **nouvelle partie** (une par seed).
2. Lance le client et connecte-toi. Les sauvegardes sont copiees dans `%LOCALAPPDATA%\NierAutomataAP\backups`.
3. Garde la fenetre du client ouverte : on y tape les commandes Archipelago (`!hint`, `!remaining`, chat...).

## Checks
Chaque check porte le nom de son lieu : un indice dit donc ou aller.
- **Story A 02-01: Landing at the City Ruins** : un check par chapitre de l'histoire (109 sur les routes A, B
  et C/D).
- **Chest: City Ruins #12** : chaque coffre, nomme d'apres sa zone. Les coffres verrouilles demandent 9S
  (a partir de la route B).
- **AP Item: Desert Zone: Housing Complex #2** : objets "AP Item" poses sur les points de collecte du jeu,
  1 a 8 par zone ; le ramasser affiche ce qu'il contient et pour qui.
- **Access Point: Desert: Camp** : premiere activation de chaque point d'acces.
- **Shop <lieu> #k** : "AP Item" vendus en tete des magasins (Camp de la Resistance, Village de Pascal,
  Chateau de la foret) ; la description dit ce qu'il contient et pour qui.
- **Level n**, **Weapon Found #n** : niveaux atteints, armes trouvees (retirees de l'inventaire).
- **Pod Program Found #n** : programmes de Pod obtenus dans le jeu lui-meme (magasin, quete, ramassage) ;
  comme les armes ils sont repris, on garde ceux envoyes par le multimonde (`pod_program_checks`, 0 = ne
  pas y toucher).
- **Ending A / B / C / D** : chaque fin principale atteinte avant l'objectif (`ending_checks`). La fin qui
  sert d'objectif n'est pas un check ; les fins "gag" ne le sont jamais.
- **Fish: <nom>** (`fish_checks`, desactive par defaut) : la premiere prise de chacune des 41 especes de
  poissons. Ne contient jamais d'objet important.
- **Ending F ... Ending Z** (`gag_ending_checks`, desactive par defaut) : chaque fin gag des routes que tu joues,
  la premiere fois que tu l'obtiens. Ne contient jamais d'objet important. Une fin gag n'ecrit que son propre
  drapeau dans ta sauvegarde ; ta progression n'est pas touchee (verifie octet par octet sur la fin W).
- **Onglet Chapters** (dans le client) : chaque chapitre de ta partie, s'il est atteint, ce qui manque pour
  l'ouvrir (objet de route, cles de chapitre, Pass de zone), si son check est envoye, et les fins gag qu'on peut
  y obtenir avec la marche a suivre. **Go** te ramene a un chapitre deja atteint et non verrouille, comme le menu
  Chapter Select du jeu. Il n'envoie jamais un check que tu n'as pas gagne.
- **Quest: <nom>** : terminer une quete annexe. La plupart se ferment apres le chapitre 7 (verifie en jeu) :
  elles ne contiennent jamais d'objet important ; le jeu donne toujours sa propre recompense.

## En chiffres
Tous les comptes sont ceux des **reglages par defaut**, une colonne par objectif (`goal`). Ils viennent de
`python tools/count_checks.py` (meme calcul que le generateur) et ont ete compares a une vraie partie generee :
484 checks comptes pour `ending_e`, 485 emplacements dans le spoiler, celui en plus etant
l'objectif lui-meme.
La colonne `story_progress` est son reglage par defaut : route A jusqu'au chapitre 4 (`story_route`,
`story_chapter`).

### Combien de checks
| | `story_progress` | `ending_a` | `ending_b` | `ending_cd` | `ending_e` |
|---|---:|---:|---:|---:|---:|
| Chapitres d'histoire | 15 | 37 | 74 | 109 | 109 |
| Coffres | 54 | 136 | 175 | 182 | 182 |
| AP Items | 32 | 63 | 63 | 75 | 75 |
| Points d'acces | 9 | 17 | 17 | 17 | 17 |
| Quetes annexes | 8 | 39 | 50 | 60 | 60 |
| Fins principales | 0 | 0 | 1 | 2 | 4 |
| Niveaux | 9 | 19 | 19 | 19 | 19 |
| Cases de boutique | 2 | 6 | 6 | 6 | 6 |
| Armes trouvees | 8 | 8 | 8 | 8 | 8 |
| Programmes de Pod trouves | 4 | 4 | 4 | 4 | 4 |
| **Total** | **141** | **329** | **417** | **482** | **484** |
| dont jamais d'objet important | 31 | 110 | 128 | 162 | 162 |

- **Jamais d'objet important** : les checks que tu peux rater ou ne jamais trouver (voir *Objectifs et logique*).
  Ils ne recoivent que des soins, des bonus, de l'argent ou des pieges : une seed n'en depend jamais.
- **Niveaux** : un check par niveau de 2 a `max_level_check` (20 par defaut) ; un objectif court s'arrete avant.
- **Cases de boutique** : `shop_checks` (2 par defaut) par boutique presente dans les chapitres que tu joues.
- **Armes trouvees**, **Programmes de Pod trouves** : `weapon_checks` (8) et `pod_program_checks` (4).
- **AP Items** : `ap_items_per_area` (3 par defaut, jusqu'a 8) par zone.

Checks facultatifs, desactives par defaut, tous "jamais importants" :
- `fish_checks` : +41 (un par espece de poisson).
- `gag_ending_checks` : +21 avec `ending_e` (les fins gag F a Z des routes que tu joues).
- `item_checks` : +71 (premier ramassage de chaque materiau).

Avec ces trois-la et `ending_e` : **617 checks**. Avec en plus tous les reglages au plus haut (8 AP Items par
zone, niveaux jusqu'a 50, 30 armes trouvees, 16 programmes de Pod trouves, 3 cases par boutique) : **783 checks**.

### Combien de verrous de progression
Un verrou est un objet qu'il faut recevoir avant que le jeu te laisse continuer.
| | `story_progress` | `ending_a` | `ending_b` | `ending_cd` | `ending_e` |
|---|---:|---:|---:|---:|---:|
| Pass de zone | 2 | 4 | 4 | 4 | 4 |
| Objets de route (Route B Access, Route C/D Access) | 0 | 0 | 1 | 2 | 2 |
| Cles de chapitre (B Chapter Key, C/D Chapter Key) | 0 | 0 | 9 | 15 | 15 |
| Cles de la Tour (Forest, Ocean, Park Access Key) | 0 | 0 | 0 | 3 | 3 |
| **Total** | **2** | **4** | **14** | **24** | **24** |

- **Pass de zone** : un par zone verrouillee que tu joues avant ton objectif. `area_locks: all` ajoute la Ville
  inondee et l'Usine abandonnee : 26 verrous avec `ending_e`. `area_locks: off` : aucun.
- **Objets de route** (`route_locks`) : un pour entrer dans la route B, un pour la route C/D.
- **Cles de chapitre** (`chapter_locks`) : une cle de plus par grand chapitre apres le premier de sa route, 9 sur
  la route B et 6 sur la route C/D. La route A n'en a pas : ses zones sont fermees par les Pass.
- **Cles de la Tour** (`tower_keys`) : les trois cles d'acces que demande la porte de la Tour.
- Chacune des quatre options se desactive separement.

### Combien d'objets
Il y a exactement un objet par check.
| | `story_progress` | `ending_a` | `ending_b` | `ending_cd` | `ending_e` |
|---|---:|---:|---:|---:|---:|
| Armes | 37 | 37 | 37 | 37 | 37 |
| Capacites | 3 | 3 | 3 | 3 | 3 |
| Verrous de progression (tableau ci-dessus) | 2 | 4 | 14 | 24 | 24 |
| Programmes de Pod | 16 | 16 | 16 | 16 | 16 |
| Soins, bonus, argent et pieges | 83 | 269 | 347 | 402 | 404 |
| **Total (un par check)** | **141** | **329** | **417** | **482** | **484** |

- **Armes** : les 37 armes que tu n'as pas au depart. Ce sont des objets de progression : les chapitres suivants
  en attendent davantage.
- **Capacites** : celles de `randomized_abilities` (Double Jump, Air Dash et Ground Evade par defaut). Tu ne peux
  pas t'en servir avant de les recevoir.
- **Programmes de Pod** : les 16 programmes autres que le laser de depart (`pod_programs`).
- **Le reste** : soins, bonus et argent, dont `trap_percentage` (20 par defaut) pour cent remplaces par des
  pieges. Environ un objet sur cinq de cette derniere ligne est donc un piege.

## Objectifs et logique
- `goal` : `story_progress` (finir le chapitre N d'une route, partie courte), `ending_a`, `ending_b`, `ending_cd`,
  `ending_e`. L'objectif fixe la part du jeu qui a des checks.
- Les chapitres sont des regions logiques dans l'ordre de l'histoire. Les armes sont des objets de
  progression : les chapitres avances en demandent plus, donc elles arrivent avant les zones difficiles.
  Les checks de niveau suivent le niveau attendu par le jeu a chaque chapitre.
- Les checks ratables ou que beaucoup de joueurs ne trouvent jamais (Bunker, Village de Pascal, sous-sol
  de l'usine abandonnee, champ petrolifere et bords isoles du desert, zones de fin de route, quetes limitees
  dans le temps) ne contiennent jamais d'objet important.
- `starter_kit` (active par defaut) : quelques soins et un bonus d'attaque et de defense au depart, puis un
  ravitaillement donne une fois a l'entree des deux passages durs sans retour (les boss enchaines de la fin
  de la route A, et le debut de la route C/D).
- `area_locks` (`up_to_forest` par defaut, `all`, `off`) : des zones restent fermees tant que tu n'as pas recu
  leur **Pass** : Desert, Parc d'attractions, Village de Pascal et Foret (avec le chateau) ; avec `all`, aussi la
  Ville inondee et l'Usine abandonnee (ces deux-la se jouent apres le chapitre 7, quand les quetes annexes sont
  fermees : y attendre laisse peu a faire). Y entrer
  sans le Pass te remet quelques metres en arriere, comme un mur invisible (avec le mod : un panneau en travers
  de l'entree nomme le Pass et t'arrete, voir *Installation*), avec "Ferme : Desert Pass" dans le
  journal du jeu. L'histoire passe par ces zones dans l'ordre, donc elle attend le Pass. Seules les zones jouees
  avant ton objectif ont un Pass (deux avec les reglages par defaut : Desert et Parc). Le prologue n'est jamais
  verrouille. La Ville copiee n'a pas de Pass (le jeu t'y place, on n'y entre pas a pied). Avec cette option les
  quetes annexes de la route A ne contiennent jamais d'objet important (certaines envoient dans une zone fermee).
- `route_locks` (active par defaut, ne sert que si ton objectif depasse la fin A) : la route B demande l'objet
  **Route B Access** et la route C/D l'objet **Route C/D Access**. Si tu commences une route sans son objet, le
  client te ramene au debut du chapitre 7 de la route que tu viens de finir (Village de Pascal, monde ouvert,
  quetes annexes encore ouvertes) pour que tu continues tes checks. Quand l'objet arrive, le client t'emmene
  tout seul au debut de la nouvelle route. Les deux deplacements sont des sauts de chapitre, comme le menu
  Chapter Select du jeu.
- `chapter_locks` (active par defaut, routes B et C/D seulement) : chaque grand chapitre apres le premier de la
  route demande une cle de plus (**B Chapter Key**, 9 au plus ; **C/D Chapter Key**, 6 au plus). Sans assez de
  cles, le client te ramene au debut de la derniere partie du chapitre precedent ; quand la cle arrive, il
  t'emmene au debut du chapitre attendu. La route A n'a pas de cle de chapitre : ses zones sont fermees par les
  Pass. Avec la fin E en objectif ca fait 24 verrous par defaut (4 Pass, 2 objets de route, 15 cles de chapitre, 3 cles
  de la Tour), 26 avec `area_locks: all`.
- `tower_keys` (active par defaut, ne sert que si ton objectif atteint la Tour : fin C/D ou E) : les trois cles
  d'acces de la route C/D (**Forest**, **Ocean**, **Park Access Key**) viennent du multimonde. Le client reprend
  celles que le jeu te donne et te les rend quand elles arrivent. Sans les trois cles, la porte de la Tour
  repousse 9S et ne se pirate pas.

## Objets recus
Armes, les 16 programmes de Pod autres que le laser de depart (`pod_programs`), capacites (double saut, dash
aerien, esquive au sol, tir du Pod, attaques...), soins et bonus, argent, et pieges :
- **Damage Trap / Heavy Damage Trap** : `damage_trap_percent` des PV max (5-50, defaut 20), le double pour
  le lourd. Ne tue jamais (1 PV au pire) sauf si `lethal_traps` est active.
- **Money Trap** : perte de 10 % des G.
- **Enemy Trap** : 3 machines d'un type deja present dans la zone apparaissent a cote du joueur, au niveau
  des machines de la zone.
  `enemy_trap_enemies` : `basic` (petites machines seulement) ou `random` (petites machines plus cinq types
  moyens essayes en jeu). Les boss et les grosses machines ne sont jamais copies. Si la zone n'a pas d'ennemi
  adapte, ou en contient deja une quarantaine (au-dela le jeu plantait), des degats a la place.
- **System Failure: Light Attack / Heavy Attack / Pod Fire** : ce systeme ne repond plus pendant 20 secondes.
- **Self-Destruct Trap** (`self_destruct_trap` : `rare` par defaut, `normal`, `off`) : l'autodestruction du jeu, court compte a rebours puis explosion, il reste 1 PV.
- **E-Drug Trap** : l'effet E-Drug du jeu, image et son brouilles pendant 30 secondes.
- **Level Up Trap** : les ennemis autour de toi gagnent 10 niveaux (des degats a la place s'il n'y en a pas).
- **Teleport Trap** : tu es remis la ou tu etais il y a 20 secondes (jamais a plus de 150 m ; attend si tu voles
  ou si tu pirates).
- **System Failure: Evade / Double Jump** : ce mouvement ne repond plus pendant 20 secondes.

Les pieges qui utilisent les effets du jeu attendent tant qu'un menu ou un chargement est a l'ecran. Tous les
pieges sauf le Money Trap attendent la fin d'une cinematique (5 minutes au plus). Les courts mouvements de
camera scriptes qui ne sont pas de vraies cinematiques (une chute vers une nouvelle zone, par exemple) ne
sont pas detectes.

## En jeu
- Notifications : "De Niicotine : X", "Check : Camp Resistance" puis "Pour Niicotine : X".
- Messagerie (Courrier des points d'acces) : mail "Checks Archipelago" (checks restants) et mail
  "Indice de <joueur>" (indices demandes par les autres sur ta partie).
- DeathLink en option : une mort recue d'un autre joueur est une vraie mort dans le jeu (ecran de mort, retour a la derniere sauvegarde).

## Carte
Le client a un onglet **Map** : une carte du monde vue de dessus, construite a partir des collisions du jeu.
Les lieux donnes par un indice sont en jaune, tes checks restants qui ont un lieu precis en gris, et toi en
rouge. Les salles interieures et souterraines (grottes, usine, centre commercial...) sont en orange par-dessus
le monde ouvert. Molette pour zoomer, glisser pour deplacer.

Trois boutons en haut de l'onglet choisissent le niveau affiche : **All** (tout sur une image), **Surface**
(le monde ouvert seul, avec ses checks) et **Indoor / underground** (les cartes separees et les souterrains :
grottes, Ville copiee, sous-sol de l'usine, Tour... avec leurs checks, le monde ouvert assombri en repere).
Sans ca, un check sous terre se confond avec ce qui est en surface au meme endroit.

![Onglet Map](docs/map_tab.png)

## Limites connues
- Uniquement Steam v1.04, c'est-a-dire la version Steam actuelle (mise a jour de novembre 2026, build
  26534214). La version d'avant cette mise a jour n'est pas geree : le client affiche "Unknown NieRAutomata.exe
  version" et ne fait rien.
- Teste en jeu sur les trois routes par sauts de chapitre automatiques et captures d'ecran (`tools/`) :
  checks d'histoire de chaque chapitre, les 182 coffres retrouves a la position prevue (interieurs compris), AP Items poses a
  leur emplacement, achats dans les trois magasins, points d'acces, objectifs des fins A a E, et checks de
  quete (une quete annexe jouee pour de vrai : acceptee, objets livres, ecran de recompense, check parti). Un coffre verrouille a ete ouvert avec 9S par un robot qui joue le mini-jeu de piratage, et son check
  est parti. Les coffres qui n'existent que pendant ou apres une quete annexe ne contiennent jamais d'objet
  important. Le marchand de la foret n'existe qu'apres la
  quete annexe ratable "Camp Development" : ses AP Items ne contiennent jamais d'objet important.
- Les pieges Self-Destruct et E-Drug ont ete essayes a pied avec 2B, en combat de boss (les deux
  marchent), en sequence de vol et pendant un piratage de 9S (l'E-Drug s'y affiche ; le Self-Destruct attend
  le retour a pied, et les objets recus apres lui attendent avec lui).
- Panneaux de zone (mod) : avec une partie generee, un serveur et le vrai client, a chacune des six entrees : le
  panneau est dessine en travers du passage et arrete le personnage pousse a 10 m/s (bien plus vite que la
  course), et celui de l'Usine a disparu quand son Pass est arrive du serveur. Le personnage etait deplace par
  les outils de test, pas a la manette. Le panneau est dessine par-dessus l'image finie : il se voit a travers
  ce qui est devant lui ; il s'efface au-dela de 60 m. Un bond de plus de 6 m en une image le franchit : le mur
  du client reste la pour ce cas. Le mod ne sert qu'un programme a la fois (le client). Linux / Proton : non
  teste par l'auteur.
- Zones verrouillees : essayees en jeu a l'entree de chacune des six zones (le mur tient sur des essais repetes,
  et le Desert s'ouvre des que son Pass arrive du serveur). Si tu te connectes alors que tu es deja dans une zone
  fermee, le client te laisse la. Aucune partie complete n'a encore ete jouee avec les verrous.
- Routes verrouillees : essayees en jeu pour les routes B et C/D (retour en arriere sans l'objet, route lancee
  quand l'objet arrive du serveur, premier check de la route envoye). Le message "Ferme" d'une route n'a pas
  encore ete vu a l'ecran. Essaye en sautant au debut de chaque route, pas en jouant une vraie fin.
- Chaque verrou a ete essaye un par un en jeu avec le vrai client et un serveur (`tools/locktest.py`, resultats
  dans `tools/locktest_report.json`) : les six murs de zone (personnage pousse a travers chaque entree a 25 m/s,
  bien plus vite qu'en courant), les deux verrous de route et les 15 verrous de chapitre (retour en arriere sans
  l'objet, check non envoye pendant le blocage, chapitre lance et check envoye quand l'objet arrive). Ces essais
  sautent aux chapitres ; aucune fin n'a ete jouee pour de vrai.
- Cles de la Tour : essayees en jeu devant la Tour avec le vrai client et un serveur (sans cle la porte refuse ;
  cles reprises quand elles sont dans l'inventaire ; cles envoyees par le serveur : 9S pirate la porte et
  l'histoire continue). Le moment ou le jeu donne lui-meme une cle a ete joue pour les trois : la cle de la
  Foret (fin de son unite de ressources), celle de l'Ocean (apres le boss de l'unite de la Ville inondee, combat
  joue a la main : le jeu affiche "Ocean Access Key x 1" et le client la reprend dans la seconde) et celle du
  Parc (dialogue des Pods au debut du chapitre 17). Le client verifie dix fois par seconde et les cles ne
  reviennent pas. Le jeu remet aussi les cles au chargement d'un chapitre suivant ; le client les reprend des
  que le jeu est jouable.
- Nouveaux pieges (Level Up, Teleport, System Failure: Evade / Double Jump) : chacun envoye par un serveur au
  vrai client et mesure en jeu (niveaux +10, retour de 78 m a la position d'il y a 20 secondes, les deux
  mouvements bloques 20 secondes puis liberes).
- Fins gag : les 21 (F a Z) ont ete atteintes en jeu avec le vrai client et un serveur : le jeu passe sur sa
  phase "Ending_<lettre>", le client la voit et le check part. Elles ont ete atteintes en sautant au bon
  chapitre, pas en jouant une partie entiere jusque-la. Quatre ont demande un humain aux commandes (I, N, Y, Z),
  et pour N et Y l'etat de l'histoire a ete pose a la main avant (disposition du village, quete precedente
  d'Emil, toutes les armes au niveau 4). Non teste : atteindre chacune dans une partie normale depuis une
  sauvegarde neuve.
- Checks de poisson : le check part quand le poisson entre dans l'inventaire (essaye en donnant une carpe avec la
  fonction de don du jeu). Une vraie prise n'a pas ete reussie par le robot de test.
- Titres des mails : ouvrir un point d'acces ~10 s la premiere fois apres chaque lancement du jeu.
- Ne pas charger une autre sauvegarde que celle de la seed.

## Developpement
- Tests : `python -m pytest`
- Build : `python build.py` (apworld) ; mod : `python mod/build_mod.py` (demande `zig`) ; lanceur :
  `python launcher/build_exe.py` (construit et embarque les deux)
- Sources du mod et protocole de sa socket : `mod/nier_ap_mod.c`, `mod/overlay.c` ; cote client :
  `nier_automata/game/modlink.py`
- Outils de retro-ingenierie dans `tools/` (sondes memoire, points d'arret materiels, lecture CPK/BXM/MCD).
