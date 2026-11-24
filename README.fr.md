# NieR:Automata pour Archipelago

Monde Archipelago (`.apworld`) et client pour **NieR:Automata (PC Steam, v1.04)**, route A.
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
- **Story: <lieu>** : chaque etape nommee de la route A (Camp Resistance, Village de Pascal, Boss Simone...).
- **Weapon Found #n** : chaque arme trouvee (retiree de l'inventaire).
- **Chest #n**, **Level n** : coffres ouverts, niveaux atteints.
- **AP Item: <lieu> #k** : objets "AP Item" poses au sol sur ton trajet, 1 a 3 par etape.
- **Shop <lieu> #k** : "AP Item" vendus en tete des magasins (Camp de la Resistance, Village de Pascal,
  Chateau de la foret) ; la description dit ce qu'il contient et pour qui.
- A plusieurs, tes checks contiennent uniquement des objets pour les autres joueurs.

## Objets recus
Armes, capacites (double saut, dash aerien, esquive au sol, tir du Pod, attaques...), soins, argent, pieges
(degats 5/10 %, perte de 10 % des G, ennemis qui apparaissent).

## En jeu
- Notifications : "De Niicotine : X", "Check : Camp Resistance" puis "Pour Niicotine : X".
- Messagerie (Courrier des points d'acces) : mail "Checks Archipelago" (checks restants) et mail
  "Indice de <joueur>" (indices demandes par les autres sur ta partie).
- DeathLink en option.

## Limites connues
- Uniquement Steam v1.04, route A.
- Titres des mails : ouvrir un point d'acces ~10 s la premiere fois apres chaque lancement du jeu.
- Ne pas charger une autre sauvegarde que celle de la seed.

## Developpement
- Tests : `python -m pytest`
- Build : `python build.py` (apworld) ; lanceur : `python launcher/build_exe.py`
- Outils de retro-ingenierie dans `tools/` (sondes memoire, points d'arret materiels, lecture CPK/BXM/MCD).
