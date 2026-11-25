# NieR:Automata pour Archipelago

Monde Archipelago (`.apworld`) et client pour **NieR:Automata (PC Steam, v1.04)**, toutes les routes.
Le client lit et modifie la memoire du jeu en cours (aucun fichier du jeu n'est modifie).

## Installation
**Avec le lanceur** : telecharge `NierAutomataAP.exe` dans les Releases et lance-le. Il trouve Archipelago,
installe/met a jour le `.apworld` dans `custom_worlds`, puis ouvre le client NieR:Automata.
Un lien `archipelago://pseudo@serveur:port` peut lui etre passe (ou associe aux liens archipelago://).

**A la main** : copie `nier_automata.apworld` dans `<Archipelago>/custom_worlds`, puis
Launcher Archipelago -> *NieR:Automata Client*.

Prerequis : NieR:Automata **Steam v1.04**, Archipelago **0.6.8+**. Celui qui genere la partie doit aussi
avoir le `.apworld`. Modele de reglages : `NieR Automata.yaml`.

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
- **Quest: <nom>** : terminer une quete annexe. La plupart se ferment apres le chapitre 7 (verifie en jeu) :
  elles ne contiennent jamais d'objet important ; le jeu donne toujours sa propre recompense.

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

## Objets recus
Armes, les 16 programmes de Pod autres que le laser de depart (`pod_programs`), capacites (double saut, dash
aerien, esquive au sol, tir du Pod, attaques...), soins et bonus, argent, et pieges :
- **Damage Trap / Heavy Damage Trap** : `damage_trap_percent` des PV max (5-50, defaut 20), le double pour
  le lourd. Ne tue jamais sauf si `lethal_traps` est active.
- **Money Trap** : perte de 10 % des G.
- **Enemy Trap** : 3 ennemis apparaissent a cote du joueur (`enemy_trap_enemies` : `basic` petites machines
  ou `random`).
- **System Failure: Light Attack / Heavy Attack / Pod Fire** : ce systeme ne repond plus pendant 20 secondes.
- **Self-Destruct Trap** : l'autodestruction du jeu, court compte a rebours puis explosion, il reste 1 PV.
- **E-Drug Trap** : l'effet E-Drug du jeu, image et son brouilles pendant 30 secondes.

Les pieges qui utilisent les effets du jeu attendent tant qu'un menu, un chargement ou une cinematique est
a l'ecran.

## En jeu
- Notifications : "De Niicotine : X", "Check : Camp Resistance" puis "Pour Niicotine : X".
- Messagerie (Courrier des points d'acces) : mail "Checks Archipelago" (checks restants) et mail
  "Indice de <joueur>" (indices demandes par les autres sur ta partie).
- DeathLink en option.

## Carte
Le client a un onglet **Map** : une carte du monde vue de dessus, construite a partir des collisions du jeu.
Les lieux donnes par un indice sont en jaune, tes checks restants qui ont un lieu precis en gris, et toi en
rouge. Les salles interieures et souterraines (grottes, usine, centre commercial...) sont en orange par-dessus
le monde ouvert. Molette pour zoomer, glisser pour deplacer.

![Onglet Map](docs/map_tab.png)

## Limites connues
- Uniquement Steam v1.04.
- Teste en jeu sur les trois routes par sauts de chapitre automatiques et captures d'ecran (`tools/`) :
  checks d'histoire de chaque chapitre, les 182 coffres retrouves a la position prevue (interieurs compris), AP Items poses a
  leur emplacement, achats dans les trois magasins, points d'acces, objectifs des fins A a E, et checks de
  quete (une quete annexe jouee pour de vrai : acceptee, objets livres, ecran de recompense, check parti). Un coffre verrouille a ete ouvert avec 9S par un robot qui joue le mini-jeu de piratage, et son check
  est parti. Les coffres qui n'existent que pendant ou apres une quete annexe ne contiennent jamais d'objet
  important. Le marchand de la foret n'existe qu'apres la
  quete annexe ratable "Camp Development" : ses AP Items ne contiennent jamais d'objet important.
- Les pieges Self-Destruct et E-Drug ont ete essayes a pied avec 2B, en combat de boss (les deux
  marchent), en sequence de vol et pendant un piratage de 9S (l'E-Drug s'y affiche ; le Self-Destruct attend
  le retour a pied, et les objets recus apres lui attendent avec lui). `lethal_traps` et le mode `random` du piege a ennemis ne sont
  couverts que par les tests automatiques.
- Titres des mails : ouvrir un point d'acces ~10 s la premiere fois apres chaque lancement du jeu.
- Ne pas charger une autre sauvegarde que celle de la seed.

## Developpement
- Tests : `python -m pytest`
- Build : `python build.py` (apworld) ; lanceur : `python launcher/build_exe.py`
- Outils de retro-ingenierie dans `tools/` (sondes memoire, points d'arret materiels, lecture CPK/BXM/MCD).
