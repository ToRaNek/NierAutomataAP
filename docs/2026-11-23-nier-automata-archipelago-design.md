# NieR:Automata Archipelago - Design

Date : 2026-11-23
Statut : brouillon, a valider par ToRaNek

## Intention

Un pote de ToRaNek veut jouer a NieR:Automata (PC Steam) dans leur multiworld Archipelago
(avec Minecraft Fabric, League of Legends, Isaac, etc.). Aucun apworld NieR:Automata n'existe
(verifie le 2026-11-23). On le cree, avec detection automatique des checks et injection
automatique des objets recus : pas de systeme a l'honneur (approche "Manual" ecartee).

## Objectifs (v1)

- Un fichier `nier_automata.apworld` installable dans `custom_worlds` d'Archipelago 0.6.8.
- Un client "NieR:Automata Client" lance depuis le launcher Archipelago (comme le LoL Client),
  qui se connecte au serveur AP et au processus `NieRAutomata.exe`.
- Checks detectes automatiquement :
  1. **Progression d'histoire** : franchir certaines phases (boss / chapitres) de la route A.
  2. **Armes obtenues** : quand une arme apparait dans l'inventaire (coffre, quete, boutique, drop),
     le client la retire et envoie le check "Arme X obtenue".
- Objets recus injectes en memoire : armes, consommables (soins), materiaux, argent (G).
- Objectif (goal) : terminer la route A (Fin A), detecte par la phase finale.
- Generation testee en local avec les autres jeux du groupe.

## Non-objectifs (v1)

- Coffres individuels, quetes secondaires, puces (plug-in chips) comme checks :
  aucun flag documente, a faire plus tard si on les trouve.
- Routes B/C/D/E, 9S (hacking), A2.
- Bloquer l'acces aux zones : NieR n'a pas de verrous par objet. La logique AP sera donc
  essentiellement "tout est accessible", les objets recus sont du gain de puissance.
- Version Windows Store, versions v1.01/v1.02.
- Mod DLL injecte dans le jeu.

## Anti-objectifs (echec meme si ca "marche")

- Corrompre ou perdre une sauvegarde : le client doit sauvegarder `SlotData_*.dat` avant
  la premiere ecriture memoire.
- Faire planter le jeu en ecrivant au mauvais endroit : le client verifie la version de
  l'executable (hash SHA-256, comme AutomataSpeedrunMod) et refuse d'ecrire si inconnue.
- Donner deux fois un objet ou perdre un objet recu apres un crash / reconnexion.

## Contraintes

- Version cible : **Steam v1.04** (meme offsets que v1.03 selon AutomataSpeedrunMod,
  commit du 2026-11-09). Les mises a jour du jeu cassent les offsets.
- Test : ToRaNek achete le jeu sur Steam et l'installe sur ce PC. Tests frequents possibles,
  donc developpement par petites iterations (sonde -> lecture -> ecriture -> retrait d'arme).
  Verifier que sa version = celle du pote (hash exe).
- Client en Python pur (ctypes : OpenProcess / ReadProcessMemory / WriteProcessMemory),
  aucune dependance pip, car le launcher Archipelago est une build figee.
- Windows uniquement.

## Approches considerees

1. **Mod DLL C++ base sur AutomataSpeedrunMod** : integration la plus solide (s'execute dans
   le jeu), mais C++ + client AP en C++ ou pont reseau, beaucoup plus long. Ecarte pour la v1.
2. **Client Python externe lisant/ecrivant la memoire** (CHOISI par Claude, ToRaNek a dit
   "ce que tu veux") : tout en Python comme Archipelago, rien a injecter, se lance comme le
   LoL Client. Plus fragile (offsets recopies a la main), acceptable.
3. **Manual randomizer** : jouable tout de suite mais a l'honneur. Ecarte par ToRaNek.

## Connaissances existantes (sources)

- AutomataSpeedrunMod (github.com/jackalstomper/AutomataSpeedrunMod), `DLLMain.cpp` :
  offsets v1.03 : `currentPhase=0xF64B20` (chaine ASCII, ex. `58_AB_BossArea_Fall`),
  `isWorldLoaded=0xF6E3C0`, `isLoading=0x13ECEB8`, `itemTableStart=0x148C834`,
  `chipTableStart=0x148E780`, `unitData=0x1494838`, `playerSetName=0x124E1CC`.
  Hash SHA-256 des exe dans `src/infra/HashCheck.cpp`. Phase "START" = menu titre.
- nierhook (github.com/Asiern/nierhook) : offsets **v1.02** (items_first=0x148C4C4 identique
  au speedrun mod v1.02), `weapons_first=0x148DCC4`, `weapons_last=0x148DFBC`,
  `items_last=0x148CE18`, logique addItem/addWeapon (slots, ID 0xFFFFFFFF = vide).
  Tableur IDs objets/armes : docs.google.com/spreadsheets/d/1zowU8VOamVJcsLZni7T-5OaiT8iZAEM3YYEdtVP1F8k
- Hypothese a verifier : en v1.03 tout le bloc inventaire est decale de +0x370
  (items 0x148C4C4 -> 0x148C834), donc armes ~0x148E034.
- Format d'un slot objet (save + memoire) : ID u32, statut u32, quantite u32, little-endian.

## Ce qui est decide

- Nom du jeu dans AP : `NieR:Automata`.
- Checks v1 = phases de la route A (liste a etablir) + premiere obtention de chaque arme
  disponible en route A.
- Pool d'objets = les armes (une de chaque), puis remplissage avec consommables / materiaux / G.
- Goal = phase de fin de la route A.
- Le client garde un etat local (fichier JSON par seed+slot) : index du dernier objet recu
  applique, checks deja envoyes. Ca evite doublons et pertes.

## Decisions prises par Claude (a relire par ToRaNek)

- **Nouvelle partie obligatoire par seed** : le client lie l'etat JSON au seed + slot AP et au
  slot de sauvegarde choisi au premier lancement. Si une sauvegarde existante a deja des armes
  ou des phases passees, le client refuse et demande une nouvelle partie.
- **Rechargement / crash** : les armes sont reinjectees si absentes a chaque chargement de
  partie (idempotent). Les consommables, materiaux et G ne sont jamais reinjectes : perte
  acceptee apres un rechargement, plutot que des doublons infinis.
- **Checks d'armes par compteur, pas par identite** : les locations sont "Arme trouvee #1..#N".
  Chaque arme apparue dans l'inventaire et non injectee par AP incremente le compteur, puis est
  retiree. N = environ 80 % des armes obtenables en route A, pour qu'une source "perdue"
  (arme deja recue par AP, que le jeu ne redonne pas) ne bloque pas la partie.
  Probleme evite : une arme recue via AP rendrait impossible le check lie a cette meme arme.

## Laisse au builder

- Structure du code de l'apworld et du client, noms internes.
- Liste exacte des phases de la route A retenues comme checks (via un outil "logger de phases"
  lance pendant une partie, cf. plan).
- Liste exacte des armes route A et leurs IDs (tableur nierhook, a verifier en v1.04).
- Strategie precise pour retirer une arme obtenue naturellement sans casser l'etat du jeu.
- Options YAML (ex. inclure/exclure armes de boutique, quantite de G en filler).

## Premiere etape technique (avant le gros du code)

Un petit outil "sonde" Python a lancer pendant une partie (PC du pote ou partage familial) qui :
verifie le hash de l'exe, affiche la phase courante en continu et la logge, dumpe l'inventaire
objets + armes. Ca valide les offsets v1.04 et produit la liste des phases.
