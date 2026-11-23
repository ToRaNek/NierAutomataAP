# NieR:Automata pour Archipelago

Apworld + client qui relient NieR:Automata (PC Steam) a un multiworld Archipelago.

## Prerequis
- NieR:Automata **Steam v1.04** (le client refuse toute autre version).
- Archipelago **0.6.8** ou plus recent.

## Installation
1. Copier `dist/nier_automata.apworld` dans le dossier `custom_worlds` d'Archipelago
   (`C:\ProgramData\Archipelago\custom_worlds`), ou bouton "Install APWorld" du launcher.
2. La personne qui genere la partie doit aussi installer cet apworld.
3. Remplir `dist/NieR Automata.yaml` (pseudo) et l'envoyer a l'hote.

## Jouer
1. Lancer NieR:Automata et commencer une **nouvelle partie** (une par seed).
2. Launcher Archipelago -> **NieR:Automata Client** -> se connecter au serveur.
3. Le client copie les sauvegardes dans `%LOCALAPPDATA%\NierAutomataAP\backups` au debut de chaque session.

## Checks
- **Story Progress #1..#N** : chaque nouvelle sequence de l'histoire (option `story_checks`, 12 par defaut).
- **Weapon Found #1..#N** : chaque arme trouvee (coffre, quete, boutique) est retiree de l'inventaire
  et envoie un check (option `weapon_checks`, 8 par defaut).
- **Objectif** : terminer la route A.

## Objets recus
Armes (ajoutees dans l'inventaire), soins et materiaux.

## Limites connues (v0.1)
- La detection de la fin A est provisoire (phase `58_AB_BossArea_Fall`) : a confirmer sur une vraie fin A.
- Pas de checks de coffres/quetes individuels pour l'instant.
- Si une ancienne sauvegarde est rechargee : les armes recues reviennent, pas les soins/materiaux.
- Ne pas charger une autre sauvegarde que celle de la seed.

## Developpement
- Tests : `python -m pytest`
- Sonde memoire : `python tools/probe.py` (log des phases dans `tools/phases_seen.log`)
- Build : `python build.py`
