"""Objets du jeu (tableur nierhook, onglet Items)."""

# Objets donnes par AP : uniquement soins/cures, jamais un materiau (les materiaux sont des checks).
FILLER_ITEMS: dict[str, int] = {
    "Small Recovery": 0,
    "Medium Recovery": 1,
    "Large Recovery": 2,
    "Full Recovery": 3,
    "Visual Cure": 60,
    "Aural Cure": 70,
    "Cure All Status": 80,
    "Melee Attack Up (L)": 102,       # degats des armes doubles pendant 30 s
    "Melee Defense Up (L)": 122,      # degats de melee recus -50 % pendant 30 s
}

# Kit de depart (objets donnes des la connexion) : le debut du jeu est le plus dur et le premier mur est le
# boss du parc d'attractions (avis d'un joueur experimente) ; un joueur ne doit pas y arriver sans rien.
STARTER_KIT: list[str] = ["Medium Recovery", "Medium Recovery", "Large Recovery",
                          "Melee Attack Up (L)", "Melee Defense Up (L)"]

# Programmes de Pod (identifiants du jeu, docs/research/pod_programs.json). Le laser R010 est celui de depart.
# Ecrits dans la table des programmes possedes, sans le message bloquant du jeu (la notification du client
# annonce l'objet).
POD_PROGRAMS: dict[str, int] = {
    "R020: Mirage": 2002, "R030: Hammer": 2003, "R040: Blade": 2004, "R050: Spear": 2005,
    "R070: M Shield": 2006, "A060: P Shield": 2007, "A080: Wave": 2008, "A090: Wire": 2009,
    "A100: Decoy": 2010, "A110: Slow": 2011, "A120: Repair": 2012, "A130: Bomb": 2015,
    "A140: Gravity": 2019, "A150: Volt": 2021, "A160: Missile": 2022, "A170: Scanner": 2024,
}

# Argent recu (ajoute aux fonds, adresse "funds").
FUNDS_ITEMS: dict[str, int] = {"500 G": 500, "1000 G": 1000, "2000 G": 2000}

# Pieges : (type, pourcentage).
SELF_DESTRUCT_TRAP = "Self-Destruct Trap"


def trap_weights(self_destruct: int) -> dict[str, int]:
    """Poids de tirage de chaque piege. self_destruct : 0 = jamais, 1 = rare (4 fois moins que les autres), 2 = normal.
    Avis du testeur : 1 PV restant, c'est la mort au moindre coup recu en meme temps."""
    w = {name: 4 for name in TRAP_ITEMS}
    w[SELF_DESTRUCT_TRAP] = {0: 0, 1: 1}.get(self_destruct, 4)
    return {k: v for k, v in w.items() if v}


TRAP_ITEMS: dict[str, tuple[str, int]] = {
    # degats : 1 x ou 2 x l'option damage_trap_percent (% des PV max), jamais mortel
    "Damage Trap": ("damage", 1),
    "Heavy Damage Trap": ("damage", 2),
    "Money Trap": ("money", 10),
    "Enemy Trap": ("spawn", 3),
    # panne de systeme (comme les effets EMP du jeu) : la capacite ne repond plus pendant N secondes
    "System Failure: Light Attack": ("jam:Light Attack", 20),
    "System Failure: Heavy Attack": ("jam:Heavy Attack", 20),
    "System Failure: Pod Fire": ("jam:Pod Fire", 20),
    # effets du jeu lui-meme, declenches par ses propres fonctions (verifie en jeu)
    "Self-Destruct Trap": ("selfdestruct", 0),   # alarme, compte a rebours ~2 s, explosion : il reste 1 PV
    "E-Drug Trap": ("edrug", 0),                 # image et son brouilles 30 s + effets aleatoires
    # ajoutes en 0.5.0 (toujours a la fin : les codes des objets suivent cet ordre)
    "Level Up Trap": ("levelup", 10),            # les ennemis presents gagnent 10 niveaux
    "Teleport Trap": ("teleport", 20),           # retour a la position d'il y a 20 secondes
    "System Failure: Evade": ("jam:Evade", 20),
    "System Failure: Double Jump": ("jam:Double Jump", 20),
}

# Ravitaillement donne une fois par le client a l'entree des deux passages durs sans retour possible (avis d'un
# joueur experimente) : les 4 boss enchaines de la fin de la route A, et la premiere sequence de la route C/D.
SUPPLY_DROPS: dict[str, list[str]] = {
    "A10": ["Large Recovery", "Large Recovery", "Full Recovery", "Melee Attack Up (L)", "Melee Defense Up (L)"],
    "C11": ["Large Recovery", "Large Recovery", "Full Recovery", "Full Recovery", "Melee Attack Up (L)",
            "Melee Defense Up (L)", "Melee Defense Up (L)", "Melee Defense Up (L)"],
}

# Quantite donnee par objet recu.
FILLER_QUANTITY: dict[str, int] = {"Small Recovery": 3, "Medium Recovery": 2}

# Materiaux : le premier ramassage de chacun est un check "Item: <nom>".
MATERIALS: dict[str, int] = {
    "Amber": 633,
    "Ancient Mask": 682,
    "Beast Hide": 510,
    "Black Pearl": 639,
    "Boar Meat": 517,
    "Broken Battery": 545,
    "Broken Circuit": 646,
    "Broken Key": 540,
    "Copper Ore": 600,
    "Clean Nut": 560,
    "Complex Gadget": 582,
    "Crushed Nut": 636,
    "Crystal": 680,
    "Drab Bracelet": 641,
    "Dented Plate": 610,
    "Dented Socket": 645,
    "Dye": 631,
    "Eagle Eggs": 638,
    "Elaborate Gadget": 581,
    "Filler Metal": 630,
    "Giant Egg": 637,
    "Gold Ore": 603,
    "Iron Ore": 601,
    "Large Battery": 546,
    "Large Gear": 526,
    "Lovely Choker": 681,
    "Machine Arm": 570,
    "Machine Core": 690,
    "Machine Head": 573,
    "Machine Leg": 571,
    "Machine Oil": 628,
    "Machine Torso": 572,
    "Memory Alloy": 715,
    "Meteorite": 688,
    "Meteorite Shard": 531,
    "Moldavite": 687,
    "Moose Meat": 518,
    "Mushroom": 626,
    "Natural Rubber": 634,
    "New Bolt": 555,
    "Pearl": 686,
    "Plant Seed": 621,
    "Popola's Booze": 170,
    "Powerup Part L": 585,
    "Powerup Part M": 584,
    "Powerup Part S": 583,
    "Precious Earrings": 683,
    "Pristine Cable": 551,
    "Pristine Screw": 521,
    "Pure Water": 623,
    "Pyrite": 632,
    "Rusted Clump": 530,
    "Rusty Bolt": 635,
    "Severed Cable": 550,
    "Shattered Earrings": 640,
    "Silver Ore": 602,
    "Simple Gadget": 580,
    "Small Gear": 525,
    "Stretched Coil": 644,
    "Stripped Screw": 520,
    "Sturdy Socket": 642,
    "Tanning Agent": 629,
    "Tech Manual": 684,
    "Thick Dictionary": 685,
    "Titanium Alloy": 535,
    "Torn Book": 627,
    "Tree Sap": 622,
    "Tree Seed": 624,
    "Viscous Oil": 852,
    "Volt-Proof Salve": 50,
    "Warped Wire": 643,
}


# Poissons (option fish_checks) : la premiere prise de chaque espece est un check "Fish: <nom>". Identifiants
# d'objet lus dans core/core.dat:FishParam.csv (docs/research/logic_gaps_resolved.json, section fishing).
FISH: dict[str, int] = {
    "Arowana": 8001, "Twinfish": 8002, "Killifish": 8003, "Carp": 8004, "Bloat Fish": 8005, "Koi Carp": 8006,
    "Fur Carp": 8007, "Freshwater Ray": 8008, "Arapaima": 8009, "Oil Sardine": 8010, "Water Flea": 8011,
    "Twoface": 8012, "Coelacanth": 8013, "Blowfish": 8014, "Swordfish": 8015, "Mackerel": 8016,
    "Horseshoe Crab": 8017, "Beetle Fish": 8018, "Starfish": 8019, "Bream": 8020, "Basking Shark": 8021,
    "Killifish Machine": 8022, "Koi Carp Machine": 8023, "Arapaima Machine": 8024, "Carp Machine": 8025,
    "Bloat Fish Machine": 8026, "Blowfish Machine": 8027, "Swordfish Machine": 8028, "Starfish Machine": 8029,
    "Bream Machine": 8030, "Coelacanth Machine": 8031, "Mackerel Machine": 8032, "Horseshoe Crab Machine": 8033,
    "Arowana Machine": 8034, "Basking Shark Machine": 8035, "Freshwater Ray Machine": 8036,
    "Machine Lifeform Head": 8037, "Tire": 8038, "Gas Cylinder": 8039, "Battery": 8040, "Broken Firearm": 8041,
}
