# NieR:Automata Archipelago v0.2 - Design

Date : 2026-11-23
Statut : brouillon, a valider par ToRaNek
Base : v0.1 (`2026-11-23-nier-automata-archipelago-design.md`) fonctionnelle et testee en jeu.

## Intention

ToRaNek veut que NieR soit un vrai jeu Archipelago :
1. **Des objets AP qui "droppent"** : les vrais coffres du jeu et les objets ramasses envoient des checks.
2. **Des choses bloquees** que les autres joueurs debloquent : puces, Pods et programmes de Pod,
   capacites de 2B, zones / teleportation (les 4 choisies par ToRaNek).

## Approche : trois paliers, du plus sur au plus risque

### Palier A - adresses deja connues (rapide)
- **Premier ramassage de chaque objet = check** ("Item: Amber", "Item: Beast Hide"...) : le client
  compare l'inventaire, chaque type d'objet vu pour la premiere fois envoie son check. Liste des objets :
  onglet Items du tableur nierhook (~180 objets), filtres aux objets obtenables en route A.
- **Puces bloquees** : table des puces connue (`chipTableStart = 0x148E780`, AutomataSpeedrunMod
  `ChipManager`). Au debut d'une seed le client retire les puces non-OS ; chaque puce trouvee dans le jeu
  est retiree et envoie un check "Chip Found #n" ; les puces recues via AP sont ajoutees.
  Exception : la puce OS (la retirer tue 2B).

### Palier B - recherche memoire avec le jeu (sessions avec ToRaNek)
Outil "diff memoire" : photo de la memoire du jeu, ToRaNek fait une action, nouvelle photo, comparaison.
- **Vrais coffres** : trouver ou le jeu note "coffre ouvert". Chaque coffre = location nommee
  ("Chest: City Ruins #3"). Le contenu d'origine du coffre est retire de l'inventaire.
- **Pods et programmes** : trouver la table des Pods / programmes, puis meme principe que les puces.
- **Points d'acces (teleportation)** : trouver les flags des points d'acces debloques ; le client les
  remet a "verrouille" tant que l'objet "Access Point: X" n'est pas recu.
- **Zones** : bloquer une zone = si le joueur entre dans une zone non debloquee (detectee via
  `playerLocation` / phase), le client le renvoie au dernier point autorise. Les coffres d'une zone
  exigent l'objet de la zone dans la logique AP.

### Palier C - capacites de 2B (modifier le code du jeu)
Esquive, double saut, sprint... : il faut patcher des instructions du jeu (nierhook le fait deja pour
"double saut infini" : preuve que c'est possible). Risque de crash, a faire en dernier.

## Conditions de victoire (demande ToRaNek : le jeu complet est trop long)

Option YAML `goal` avec plusieurs choix :
- **Story Progress** (disponible tout de suite) : atteindre N sequences d'histoire (N = `story_checks`).
- **Boss** : battre un boss precis de la route A (ex. Colosse, Adam & Eve, Pascal, Simone, Hegel...,
  liste a etablir) : necessite les noms de phases, collectes avec `tools/phases_seen.log` pendant une
  partie.
- **Fin A** : terminer la route A (jeu complet de la premiere route).
- Plus tard : Fin B/C/D/E si les routes suivantes sont supportees.
Le goal choisi ne doit pas exiger de locations au-dela du point d'arret (les checks d'histoire
apres le boss choisi ne sont pas crees).

## Logique AP
- Palier A : pas de verrou de logique (les puces changent la difficulte, pas l'acces).
- Palier B : les locations d'une zone exigent "Zone: X" ; les coffres exigeant un Pod (ex. hauteur)
  exigeront le programme correspondant si identifie.
- Le goal reste la fin A.

## Non-objectifs v0.2
- Routes B/C, A2, 9S.
- Multijoueur dans le meme monde NieR.

## Anti-objectifs
- Bloquer definitivement une partie (zone verrouillee sans moyen d'obtenir l'objet) : la logique AP
  doit toujours garantir l'acces.
- Retirer la puce OS ou casser une sauvegarde (backup deja automatique).

## Ordre propose
1. Palier A (objets + puces).
2. Outil diff memoire, puis coffres (demande principale), puis points d'acces / zones, puis Pods.
3. Palier C.
Chaque etape livre une version jouable.
