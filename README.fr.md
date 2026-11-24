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
- **Quest: <nom>** : quetes annexes (experimental, desactive par defaut).

## Objectifs et logique
- `goal` : `story_progress` (atteindre N chapitres, partie courte), `ending_a`, `ending_b`, `ending_cd`,
  `ending_e`. L'objectif fixe la part du jeu qui a des checks.
- Les chapitres sont des regions logiques dans l'ordre de l'histoire. Les armes sont des objets de
  progression : les chapitres avances en demandent plus, donc elles arrivent avant les zones difficiles.
  Les checks de niveau suivent le niveau attendu par le jeu a chaque chapitre.
- Les checks ratables (Bunker, Village de Pascal, zones de fin de route, quetes limitees dans le temps) ne
  contiennent jamais d'objet important.

## Objets recus
Armes, capacites (double saut, dash aerien, esquive au sol, tir du Pod, attaques...), soins, argent, pieges
(degats 5/10 %, perte de 10 % des G, ennemis qui apparaissent).

## En jeu
- Notifications : "De Niicotine : X", "Check : Camp Resistance" puis "Pour Niicotine : X".
- Messagerie (Courrier des points d'acces) : mail "Checks Archipelago" (checks restants) et mail
  "Indice de <joueur>" (indices demandes par les autres sur ta partie).
- DeathLink en option.

## Carte
Le client a un onglet **Map** : une carte du monde vue de dessus, construite a partir des collisions du jeu.
Les lieux donnes par un indice sont en jaune, tes checks restants qui ont un lieu precis en gris, et toi en
rouge. Molette pour zoomer, glisser pour deplacer.

![Onglet Map](docs/map_tab.png)

## Limites connues
- Uniquement Steam v1.04.
- Teste en jeu sur les trois routes par sauts de chapitre automatiques (`tools/campaign.py`) : checks
  d'histoire de chaque chapitre, 129 coffres sur 187 retrouves a la position prevue, AP Items poses a leur
  emplacement. Les coffres non confirmes (surtout dans les interieurs charges a part) ne contiennent jamais
  d'objet important. Pas encore teste en jeu : magasins du Village de Pascal et du Chateau, quetes, fins.
- Titres des mails : ouvrir un point d'acces ~10 s la premiere fois apres chaque lancement du jeu.
- Ne pas charger une autre sauvegarde que celle de la seed.

## Developpement
- Tests : `python -m pytest`
- Build : `python build.py` (apworld) ; lanceur : `python launcher/build_exe.py`
- Outils de retro-ingenierie dans `tools/` (sondes memoire, points d'arret materiels, lecture CPK/BXM/MCD).
