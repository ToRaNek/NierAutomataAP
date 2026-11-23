# NieR:Automata - web reference for the Archipelago randomizer

Compiled 2026-11-23 from public sources only (no game access). Main sources:
- **FX** = Fextralife wiki (nierautomata.wiki.fextralife.com)
- **FD** = NieR Fandom wiki (nier.fandom.com). The HTML is paywalled (HTTP 402), so the wikitext was read through the MediaWiki API (`api.php?action=parse&prop=wikitext`).
- **GP** = GamePressure guide (gamepressure.com/nier-automata)
- **PT** = PocketTactics endings article

Conventions:
- `(?)` means uncertain, a single weak source, or my own inference.
- "Ch XX-YY" is the in-game chapter/subchapter number shown on the save and in Chapter Select.
- Route A has 10 chapters, Route B has 10 (same numbering) and Route C/D covers Ch 11-17. The FX Route C page talks about a Ch 18 (final) (?); FD puts the C/D endings at 17-09.

---

## 1. ROUTES

### Overview

| Route | Character(s) | Chapters | Starts | Ends | How it starts |
|---|---|---|---|---|---|
| A | 2B (9S is the AI partner) | 01-10 | Prologue: flight unit, Abandoned Factory | Ch10: Eve fight, Ending A (10-05) | New game |
| B | 9S (2B is the AI partner) | 01-10 | Prologue replayed from 9S's side (hacking) | Ch10, Ending B (10-05) | "Continue" from an Ending A clear save |
| C/D | 2B (opening), then A2 and 9S alternating | 11-17 | Ch11: Bunker, full-scale attack | Ch17 Tower; final choice gives Ending C (A2) or D (9S) | Continue from an Ending B clear save |
| E | Pod 042 / Pod 153 (credits shmup) | none | After the credits of the second of C/D | Ending E | Answer "Yes" to Pod 153 after you have both C and D |

### Route A (2B), ordered main story

The chapter titles come from FX Walkthrough. The main quest names come from FX Quests; mapping them to chapters is partly my inference (?).

| Ch | Title | Areas | Main quests (FX) | Mandatory boss / set piece |
|---|---|---|---|---|
| 01 | Prologue | Flight unit over sea, Abandoned Factory, then Bunker | Reboot | Flight-unit shmup, Buzzsaw mini-boss, Goliath (Marx/Engels) in 2 phases |
| 02 | Resistance Camp | City Ruins, Resistance Camp, Desert Zone | Gathering Intel, The Machine Surge | (The Weapon Dealer's and Supply Trader's Requests are story-gated, see sec. 3) |
| 03 | Adam and Eve | Desert Zone, Desert Housing Complex | MIA | Adam (Desert) |
| 04 | Mad Songstress | Sewers, Amusement Park | (MIA continued) | Goliath Tank (optional), Simone ("Opera Singer", 2 phases) |
| 05 | Excavated Land | Pascal's (Machine) Village, City Ruins, alien ship under the crater | Machine Recon, Machine Request, Machine Trade, Assault | Engels (City Ruins Goliath), Adam & Eve (alien ship). This unearths the "Deep Cave" (big side-quest unlock) and Jackass's access point (fast travel) |
| 06 | King of the Forest | Bunker, Pascal's Village, Forest Zone, Forest Castle | The Forest Kingdom, Report on A2 | Goliath at the castle bridge, A2 (Forest Castle) |
| 07 | Lost Child | City Ruins, Resistance Camp, Flooded City, sea flight section | Flooded City Recon, Alien Report, Resupply, **Missile Supply Mission**, 9S MIA | Goliath Flyer mini-boss, Grün (sea) |
| 08 | Copied City | Flooded City, Copied City (below the crater) | Redheads (gives A170 Scanner), MIA, 9S MIA part 2, 9S Captured | Adam (Copied City, 3 phases) |
| 09 | Deranged Religion | Abandoned Factory (with Pascal) | Olive Branch, Twisted Religion | Kierkegaard / cult (?), Mechanical Spider boss |
| 10 | Loss | Resistance Camp (under attack), Pascal's Village, City Ruins crater | Weird Machines, Threat Disposal | Spider mini-boss at the camp, Eve (3 phases). Ending A |

### Route B (9S)
- Same 10 chapters and areas as A. The scenes are seen from 9S's side, with hacking mini-games in place of heavy attacks. 9S can only use the Fast weapon slot (FX).
- Route-B-only content: the prologue as 9S, Ch01 Bunker hack, Ch05 alien-ship differences, Ch09 hacking network inside the Factory, and a Ch10 Bunker/Eve variant.
- FX Quests says Route B has the same quest sequence minus the 2B-only quests (Redheads, the 2B-led MIA, 9S Captured, Olive Branch).
- Unlocks 9S-only content: hack-locked chests (Phoenix Sword, Cruel Blood Oath, Beastcurse, Type-4O Fists), 9S side quests (sec. 5), and Pod Program A100 (?).
- Ends with Ending B.

### Route C/D (third playthrough), ordered
Sources: FX Route C walkthrough and the FX/GP chapter lists. After Ch11 you can choose between A2 and 9S chapters. FX says each character's chapters can be played out of sequence, but **all A2 and 9S chapters must be done before Ch17**.

| Ch | Title | Character | Areas | Key events / items |
|---|---|---|---|---|
| 11 | Full-Scale Attack | 2B, then 9S, then 2B, then A2 | Bunker (flight suit), City Ruins (6 hack sites), City Ruins/Abandoned Factory bridge, Flooded City emergency landing, Shopping Center (Commercial Facility) | Logic virus. **The Bunker is destroyed** and cannot be entered from Ch12 on (FD) |
| 12 | Memories of Sand | A2 | Desert Zone | Goliaths, Hegel boss, virtual-world hacking |
| 13 | Meat Box | 9S | Forest Zone: Resource Recovery Unit "Meat Box" | **Forest Access Key** |
| 14 | Pascal's Despair | A2 (and Pascal in a Goliath) | Forest Zone (Rigid Tree Bark), then Pascal (**Fuel Filter**), Pascal's Village defence, Abandoned Factory | Vanquish the Bad Bot (mandatory), Engels boss. **Pascal's Village is wiped out.** End-of-chapter choice: wipe Pascal's memory or kill him |
| 15 | Soul Box | 9S | Flooded City: Resource Recovery Unit "Soul Box" | **Ocean Access Key**. FX says 9S returns to camp "with some abilities lost" (?) |
| 16 | God Box | A2, then 9S | Amusement Park: Resource Recovery Unit "God Box" | Operator 21O and Auguste fights, **Park Access Key** |
| 17 | The Tower | 9S and A2 alternating | City Ruins: Tower (needs the 3 keys), library, Ko-Shi & Ro-Shi, final | Final choice: A2 gives Ending C, 9S gives Ending D. 17-09 is the Chapter Select point for C, D and E |

### Route E
- There is no new gameplay route. After both Ending C and Ending D, answer "Yes" to Pod 153 when the credits start. The credits then become a shmup minigame (Ending E, 17-09 or 17-11).
- Online help adds 6 turrets after 4 deaths; offline it is much harder.
- After E the game offers to **delete all save data** to help other players. This is optional and is asked again every time (FD/FX).

### Carry-over between routes

| Data | A to B | B to C | Notes |
|---|---|---|---|
| Character level | Yes (9S starts at 2B's level) | Yes | GP. Route C enemies start at about Lv50 (Steam/GameRevolution) (?) |
| Inventory (items, consumables, materials) | Yes | Yes (?) | GP |
| Money (G) | Yes | Yes (?) | GP |
| Weapons (incl. upgrade levels) | Yes, but the active weapon must be re-equipped | Yes | GP |
| Plug-in chips | Yes (?) (Steam user) | Yes (?) | GP does not mention chips |
| Pods and pod programs | Yes, programs must be re-equipped | Yes | GP |
| Intel: unit data, archives | Yes | Yes | GP |
| Endings already seen | Yes | Yes | GP |
| Discovered access points | Stay discovered. Fast travel stays locked until Ch5/Ch6 (sources disagree, see sec. 6) | n/a | GP |
| Side quests | **Unfinished ones reset.** Completed ones can be redone for rewards again on the new route | Same | GP. Exceptions that persist: Half-wit Inventor, DLC arena quests (GP), Reconnaissance Squad (does not reset under Chapter Select, FD) |
| Main chapters | Replayed | n/a | |

**Chapter Select** unlocks after the first Route C/D ending (end of the 3rd playthrough). It allows revisiting any subchapter to redo missed quests and endings. FD says the slide from "Play with Us!" persists across Chapter Select.

Sources: https://nierautomata.wiki.fextralife.com/Walkthrough , https://nierautomata.wiki.fextralife.com/Subcontent:Walkthrough_2_NieR_Automata_Route_C , https://nierautomata.wiki.fextralife.com/Quests , https://nierautomata.wiki.fextralife.com/Game+Progress+Route , https://gamepressure.com/nier-automata/list-of-all-routes-and-chapters/z0eae5 , https://www.gamepressure.com/nier-automata/route-b-what-can-be-transferred/z2ea93 , https://nier.fandom.com/wiki/NieR:Automata/Endings , https://nier.fandom.com/wiki/Bunker

---

## 2. POINTS OF NO RETURN

Everything below is recoverable through Chapter Select after Route C/D, except where noted. For a randomizer, assume a location is lost once its window passes, unless you plan on Chapter Select.

### Route A / Route B

| When | What becomes unavailable | Source |
|---|---|---|
| Before **Ch05-02** | **Improving Communications** (Bunker, Commander). Window 02-02 to 05-01. Easily missed; can leave you stuck at 98% quests | FX |
| Before Grün / **Missile Supply Mission (Ch07)** | **Emil's Memories** (window 06-03 to 07-03) and **The Wandering Couple**: their progress is erased if the mission starts first. Most other side quests are also disabled until the next route or Chapter Select | FX Side Quests, FD Emil's Memories ("must be done before 2B or 9S battle with Grün"), FX Emil's Determination |
| Ch07-01 to 07-03 only | **Terminal Repairs**, **Find a Present** (2B, Route A) | FX |
| Windows 05-03/04, 06-01 to 06-05, 07-01 to 07-03 | **Machine Examination 2**, **Data on the Old World** (9S) | FX |
| Route A only | Jackass's Research, Terminal Repairs, Find a Present, 11B's Memento (2B quests) | FX |
| Route B only | Amnesia, Data Analysis Freak 1/2, Idiot Savant, Game Dev Lv1-3, Data on the Old World, The Recluse x3 (9S quests) | FX |
| Ch08 Copied City, Ch05 alien ship | Story-only areas. Revisiting them is not described (?) | inference |
| **Ch10 (Eve's attack)** | The Pascal's Village access point is no longer usable for fast travel | FD Pascal's Village |
| Lost Girl not done in first half | The Big Sister later tells A2 her sister died (dialogue change, quest lost) | FD |

### Route C/D

| When | What becomes unavailable | Source |
|---|---|---|
| Ch11, before the rendezvous with 2B | Bonus materials on 21O's desk, only if 9S lowers the anti-air signal to 0% | FD Bunker |
| **Ch11 end / Ch12+** | **The Bunker** is destroyed: its shops, quests and harvest points are gone, and death becomes "reload save" (no more body backup) | FD Bunker |
| **Ch14** | **Pascal's Village destroyed.** Villager quests end (Treasure Hunt at the Castle is available only until then as A2; 9S cannot do it in Route C). Pascal's shop changes; **Machine Heads** can only be bought (Ch15+) if Pascal's memory was wiped | FD Treasure Hunt, GP weapons, FX Route C |
| Ch15 Soul Box | The Soul Box tower can be visited only once. The **Faith** weapon is there | GP weapons |
| Ch16 (9S goes after the Park Access Key) | The Amusement Park **Theater** can no longer be entered (it ends up on the bridge) | FD Amusement Park |
| Windows 13-03/04, 15-01 to 15-04, 16-01/03/04, 17-01/02 | **Reconnaissance Squad** (9S, 4S at Forest Castle) and **Gathering Keepsakes** (13-01..) | FX |
| Completing **Emil's Determination** | **Ending Y is lost permanently**, even via Chapter Select (the quest cannot be replayed) | FD Head(Y) battle, FX Emil's Determination |
| Ending E | Optional save deletion: it is permanent if accepted | FD/FX |

Sources: https://nierautomata.wiki.fextralife.com/Side+Quests , https://nierautomata.wiki.fextralife.com/Emil's+Determination , https://nier.fandom.com/wiki/Head(Y)_battle , https://nier.fandom.com/wiki/Bunker , https://nier.fandom.com/wiki/Pascal's_Village , https://nier.fandom.com/wiki/Amusement_Park , https://www.gamepressure.com/nier-automata/list-of-weapons/z5eaf9 , https://nierautomata.wiki.fextralife.com/Trophy+&+Achievement+Guide

---

## 3. MANDATORY / BLOCKING

### Side quests required by the story
FD: "The only quests that have to be completed to progress the story are..."

| Quest | When | Gates |
|---|---|---|
| The Supply Trader's Request | Route A Ch02, Resistance Camp | Story progress, and the Supply Trader shop (incl. plug-in chips) |
| The Weapon Dealer's Request | Route A Ch02, Resistance Camp | Story progress, and the Weapon Shop (Lv1-3 upgrades) |
| Vanquish the Bad Bot | Route C Ch14 (A2), Pascal | Story progress. Refusing it stalls the main quest. Also unlocks "Play with Us!" |

### Key items that gate progression

| Item | Obtained | Needed for |
|---|---|---|
| Fuel Filter | From Pascal, twice: Ch05 (2B/9S, village deliveries) and Ch14 (A2, after Hegel; needs **Rigid Tree Bark**) | Ch05 and Ch14 story. Ch14 also starts Devola's Request |
| Rigid Tree Bark | Forest Zone harvest point, north ruins, guarded by a Goliath Biped (Ch14) | Fuel Filter (Ch14) |
| Forest Access Key | Top of the Meat Box, 9S (Ch13) | Tower entry (Ch17) |
| Ocean Access Key | Top of the Soul Box, 9S (Ch15) | Tower entry |
| Park Access Key | After Auguste, God Box (Ch16) | Tower entry |
| Elevator Key | During Emil's Memories (optional) | Emil's hideout / Lunar Tear trophy, Emil boss, Emil Heads, Ending Y chain |
| A170: Scanner | Main quest "Redheads" (Route A ~Ch08) | Hidden harvest points, buried weapons (Iron Will, Phoenix Lance) |

### Area unlock order (story-gated)

| Area | First access | Notes |
|---|---|---|
| Abandoned Factory | Ch01 prologue | Revisited Ch09 and Ch14 |
| Bunker | After the prologue | Reachable only via the Resistance Camp transporter until Ch06. Gone from Ch12 |
| City Ruins, Resistance Camp | Ch02 | Hub |
| Desert Zone (+ Housing Complex, Oasis, Oil Field) | Ch02/03 via the Border Area | Desert Camp |
| Amusement Park | Ch04 via the City Ruins sewers | |
| Pascal's (Machine) Village | Ch04/05, after Simone, via a bridge behind the park | City Ruins shortcut box opens later |
| City Ruins Deep Cave / alien ship | Ch05 (Engels, Adam & Eve) | "Deep Cave unearthed" unlocks many side quests |
| Forest Zone / Forest Kingdom | Ch06 ("The Forest Kingdom") | The Forest Castle gate from the village stays shut until after A2's first appearance |
| Flooded City | Ch07 | |
| Copied City | Ch08 (below the crater) | Story area |
| Emil's Residence | Via the hidden elevator in the crater caves, after Emil's Memories | |
| Meat / Soul / God Box | Ch13 / 15 / 16 | Route C/D |
| Tower | Ch17 | Needs the 3 keys |

### Forced mechanics / fights
- Flight-unit shmup sections in the prologue, Ch07 (Grün), Ch11 and in places in Route C. The Ending W death is possible there.
- 9S hacking mini-games: forced in Route B and C (Ch09 factory network, Ch11 hack sites, Ch12 virtual world).
- The bosses in the sec. 1 tables are all mandatory.
- Timed hack in Ch01-03 (Route B): letting the timer expire gives Ending F.
- Fast travel is unavailable before Ch05/06 (sec. 6).

Sources: https://nier.fandom.com/wiki/Quests_(Automata) , https://nier.fandom.com/wiki/Fuel_Filter , https://nier.fandom.com/wiki/Forest_Access_Key , https://nier.fandom.com/wiki/Pascal's_Village , https://nierautomata.wiki.fextralife.com/Subcontent:Walkthrough_2_NieR_Automata_Route_C , https://nierautomata.wiki.fextralife.com/Game+Progress+Route , https://nierautomata.wiki.fextralife.com/Pod+Programs

---

## 4. ENDINGS A to Z (+ DLC)

There are 26 lettered endings plus a DLC ending ◬. A-E are the main endings and F-Z are joke/hidden endings (FD).
- Chapter = FD infobox value.
- "Accidental?" = whether a normal player can trigger it by mistake (my judgement).
- A joke ending returns you to the last save.

| L | Title (FD) | Chapter | Trigger | Joke? | Accidental? |
|---|---|---|---|---|---|
| A | flowers for m[A]chines | 10-05 | Beat Route A | Main | n/a |
| B | or not to [B]e | 10-05 | Beat Route B (from an A save) | Main | n/a |
| C | meaningless [C]ode | 17-09 | Route C/D final: choose **A2** | Main | n/a |
| D | chil[D]hood's end | 17-09 | Route C/D final: choose **9S** | Main | n/a |
| E | the [E]nd of YoRHa | 17-09 / 17-11 | After C and D, answer "Yes" to Pod 153 and clear the credits shmup | Main | n/a |
| F | mission [F]ailed | 01-03 (B) | As 9S, let the system-restore/hack timer run out after Engels knocks him down | Joke | Yes (slow players) |
| G | hun[G]ry for knowledge | 01-01 (B) | As 9S at the start of Route B, walk along a crane | Joke | Possible |
| H | a mountain too [H]igh | 05-02 | Ignore the Goliath intercept order and go to the Amusement Park | Joke | Possible |
| I | no [I] in team | 08-01 (A) | After Adam in the Copied City, walk away from 9S | Joke | Possible |
| J | bad [J]udgement | 09-01 (A) | Kill a machine at the Abandoned Factory entrance while escorting Pascal | Joke | **Yes** (easy to swing at "enemies") |
| K | aji wo [K]utta | 06-01 | Eat the Mackerel received from Jackass | Joke | Possible (curious players) |
| L | [L]one wolf | 10-01/02/03 | Abandon the Resistance Camp during the attack, flee the Spherical Machine fight, or skip helping Pascal's Village | Joke | Possible |
| M | break ti[M]e | 14-03 | As A2, don't go to help Pascal's Village under attack | Joke | Possible |
| N | [N]o man's village | 05-01 (FD) / 07-01 (GP) | Kill every friendly machine in Pascal's Village | Joke | Unlikely |
| O | just y[O]u and me | 11-03/04 | As 2B, skip helping the YoRHa units in the City Ruins (go to the Factory), or as 9S abandon 2B after the EMP | Joke | Possible |
| P | corru[P]tion | 11-06 | Let infected 2B reach 100% infection (it jumps to 90% at the Shopping Center bridge) | Joke | **Yes** (time pressure) |
| Q | [Q]uestionable actions | 11-07 | As 9S, don't go to the Commercial Building to help 2B | Joke | Possible |
| R | mave[R]ick | 14-05 | As A2, attack a peaceful machine sheltering in the Abandoned Factory | Joke | **Yes** |
| S | city e[S]cape | 17-01 | Abandon Devola & Popola while they protect 9S's Tower hack | Joke | Possible |
| T | fa[T]al error | Any | Remove the **OS Chip** (Plug-in Chip menu; PT wrongly says Pod Programs) | Joke | Possible (curiosity) |
| U | deb[U]nked | Any (from 01-05) | Self-destruct in the Bunker as 2B/9S | Joke | Possible |
| V | reckless bra[V]ery | 17-01 | Keep fighting next to Devola & Popola (or idle) instead of hacking the Tower until they fall | Joke | **Yes** |
| W | broken [W]ings | 01-01 (A) | Die during the prologue (e.g. flight unit hit by the giant laser) | Joke | **Yes** (most common) |
| X | time to rela[X] | 11-06 | As A2, run away from infected 2B at the Commercial Building | Joke | Possible |
| Y | head[Y] battle | Any | During **Emil's Determination**, let the final Emil (clones/head) **self-destruct** instead of killing it | Hidden | **Missable** |
| Z | over[Z]ealous | 14-01 | As A2, kill Pascal outside the Resistance Camp after rescuing him (dialogue choice) | Joke | Possible |
| ◬ | 3C3C1D119440927 | DLC | Complete the DLC quest "Mysterious Invitation" (after Mysterious Letter and the 3 arenas) | DLC | No |

### Ending Y details (only missable ending)
1. Complete Emil's Memories. It is time-limited in Route A/B; do it before the Ch07 Missile Supply Mission / Grün.
2. Get **all weapons**, including Emil Heads. Emil Heads come from beating Lv99 Emil at Emil's Residence, reached via the crater elevator (FX also describes a mask theft from his house that triggers the fight).
3. Upgrade **every weapon to Lv4**. Masamune is needed for Lv4.
4. Emil then appears at the Shopping Center and gives the quest.
5. The boss is fought in the Desert Zone. In the final self-destruct phase, letting it blow up gives Ending Y; killing the vulnerable Emil completes the quest **without Y**.
6. The completed quest can never be replayed, even through Chapter Select. Save at the Desert access point beforehand.

Disagreements:
- GameSkinny/GameRevolution label the Emil self-destruct ending as "O"; FD, PT and GP say Y.
- N chapter: FD says 05-01, GP says 07-01.
- FX availability: Route A/B ideally start of Ch07, A2 Ch14/16. Emil does not appear in Ch12.

Sources: https://nier.fandom.com/wiki/NieR:Automata/Endings (and each ending page via the API), https://nier.fandom.com/wiki/Head(Y)_battle , https://www.gamepressure.com/nier-automata/endings-list/z0eafd , https://www.pockettactics.com/nier-automata/endings , https://nierautomata.wiki.fextralife.com/Endings_Guide , https://nierautomata.wiki.fextralife.com/Emil's+Determination

---

## 5. SIDE QUESTS

**Count:** FX lists **60** base-game side quests. FD's category lists **65**, which is the same 60 plus 5 DLC quests (Underground Colosseum, Gambler's Colosseum, Trial of Sand, Mysterious Letter, Mysterious Invitation). All 60 + 5 are below.

How to read the table:
- Route column (FX): Sh = shared (any of 2B/9S/A2 while available); 2B, 9S, A2 = exclusive; A2+9S = Route C/D.
- "Deep Cave" = after the Ch05 alien ship (Engels / Adam & Eve).
- Windows (Ch numbers) are from FX where it gives them; activation text is from FD.

| # | Quest | Giver / location | Route | Earliest / prerequisite | Window / missable | Notable reward |
|---|---|---|---|---|---|---|
| 1 | Jean-Paul's Melancholy (FX: Sartre's Melancholy) | Jean-Paul, Pascal's Village | Sh | First village visit (Ch05) | - | EXP Gain Up +3 |
| 2 | Machine Examination 1 | 9S, in front of the Goliath in City Ruins | Sh | After Deep Cave | Up to 07-03 | Engels Record 0005 |
| 3 | Machine Examination 2 | 9S, City Ruins | Sh | After #2 | 05-03/04, 06-01..05, 07-01..03 | Fast Cooldown +6, Max HP Up +6 |
| 4 | Family Squabble | Mother Machine, outside Pascal's Village (FX: Machine Village) | Sh | After the City Ruins Goliath attack | - | Deadly Heal +3, Impact Bracer (L) |
| 5 | Animal Care | Animal-loving Machine, Forest Zone | Sh | Forest access (Ch06) | - | Quality Sachet |
| 6 | Turf War | same | Sh | After #5 | - | Auto-Heal +5, Record of a Bestial Machine |
| 7-11 | Robo Dojo: White / Brown / Black / Red&White / Red Belt | Father Servo, City Ruins | Sh | Chain | - | Melee Def +1, Ranged Atk +2, Ranged Def +3, Powerup Part S |
| 12 | Lost Girl | Big Sister Machine, bottom of Pascal's Village | Sh | Village (Ch05) | Do it in the 1st half or the sister "dies" (A2 dialogue) | Pink & Blue Ribbon (cosmetic) |
| 13 | The Supply Trader's Request | Supply Trader, Resistance Camp | Sh | Ch02 | **Mandatory** | Opens the chip stock of the Supply Trader |
| 14 | The Manager's Request | Manager, Resistance Camp | Sh | After returning from Pascal's Village | - | Anti Chain Damage +3; **opens the camp storage area** (unlocks 18, 50, 15) |
| 15 | Camp Development | Anemone | Sh | After the A2 fight at Forest Castle (Ch06) + #14 | - | Down-Attack Up +3 |
| 16 | Anemone's Past | Anemone | Sh | After #15 | - | Data Chips A-E, Powerup Part S |
| 17 | Amnesia | Resistance member, west camp building | 9S | After Deep Cave | - | **A090: Wire**, Offensive Heal +3 |
| 18 | Resistance Disappearance | Resistance member by the beds | Sh | After #14 | - | Max HP Up +3 |
| 19 | Jackass's Research | Jackass, Border Area / Desert Camp | 2B | After the first village visit | Per round | E-Drug x5 |
| 20 | Improving Communications | Commander, Bunker | Sh | After Desert access, 02-02 | **Must finish before 05-02** | 3,000G (often missed, blocks 100%) |
| 21 | Investigating Communications | Operator 6O (call) | Sh | After Adam & Eve (alien ship) | - | 320 EXP |
| 22 | Terminal Repairs | 6O, City Ruins (run toward the crater instead of talking to Pascal at 07-01) | 2B | After #21 | **07-01..07-03** | - |
| 23 | Find a Present | 6O mail "Thanks for your help the other day!" | 2B | After #21-22 | **07-01..07-03** | **Type-4O Sword, A130: Bomb** |
| 24 | Data Analysis Freak | 21O, Bunker command room | 9S | After the Adam & Eve fight | Bunker only (gone in Ch12+) | - |
| 25 | Data Analysis Freak 2 | 21O transmission (FX: Inbox; FD: Resistance Camp) | 9S | After #24 | - | **Type-4O Blade, A110: Slow** |
| 26 | Lord of the Valley | Canyon Machine, Forest ravine | Sh | Forest access | - | Vengeance/Last Stand/Taunt Up +3; **Canyon Machine fuses chips to +8**, Phoenix Dagger (GP) |
| 27 | Vanquish the Bad Bot | Pascal | A2 | Ch14 after the Fuel Filter | **Mandatory** | Unlocks #28 |
| 28 | Play With Us! | Machine children, village playground | A2 | After #27 (+ Medium Quadruped) | Until the village falls (Ch14) | - |
| 29 | Storage Element | Pascal | A2 | Ch14 village requests | Until the village falls | 10,000G |
| 30 | Half-wit Inventor | Scientist Machine, Pascal's Village | All 3 | First village visit | Tiered; persists across routes (GP) | **Alien Mask**, Choice Sachet |
| 31 | Idiot Savant | Weird Machine (FD: via Pascal) | 9S | After Deep Cave | - | Hijack Boost +6 |
| 32-34 | Game Dev Machine Lv1/2/3 | Game Creator Machine, under the park theater | 9S | After Simone (Route B) | Theater closes in Ch16 | Hacking chips +4 |
| 35 | Speed Star | High-speed Machine near Engels, City Ruins | Sh | - | - | Moving Speed Up +3 |
| 36 | Emil's Memories | Emil, City Ruins / Lunar Tear in the Shopping Center | Sh | After the Forest Zone main quest (Ch06) | **06-03..07-03; before Grün / Missile Supply** | **Elevator Key**, Lunar Tear, Memories of War |
| 37 | Photographs | Resistance member at the camp entrance | Sh | After Deep Cave | - | Charge Attack +3 |
| 38 | 11B's Memento | 16D, Bunker hangar | 2B | After Desert access | Bunker only | **YoRHa-issue Blade** (30% shop discount), Melee Def +6 |
| 39 | Treasure Hunt at the Castle | Weird-talking Machine, Pascal's Village (or Forest door) | All 3 | After main quest "Report on A2" (Ch06) | A2: until the village falls (Ch14); 9S cannot do it in Route C | Letter to the Forest King |
| 40 | The Wandering Couple | Resistance members, bottom of the village | Sh | After Simone | **Before Missile Supply Mission** | **A080: Wave**, Overclock +3 |
| 41 | Data on the Old World | Pascal | 9S | After Deep Cave | 05-03/04, 06-01..05, 07-01..03 | Heal Drops Up +6, Stun +6 (Commander) |
| 42 | Culinary Researcher | Resistance trader, far end of the Shopping Center | Sh | After #15-16 | - | Stat items x2 each |
| 43 | YoRHa Betrayers | Mail "Confidential Mission Details" (FX: 6O; FD: Commander) | Sh | After Deep Cave (by 07-02 at the latest) | Breaks if you talk to Anemone while #15-16 are active | **Type-4O Lance** |
| 44 | Reconnaissance Squad | 4S, Forest Castle | 9S | Route C | 13-03/04, 15-01..04, 16-01/03/04, 17-01/02; needs **95% unit data (~172/182)**; does not reset in Chapter Select | Cure All + Heal All, 17,000G |
| 45 | Devola's Request | Devola, Resistance Camp | A2+9S | After the Ch14 Fuel Filter | - | - |
| 46 | Popola's Errand | Devola | A2+9S | After #45 | - | Gold Ore, Meteorite |
| 47 | The Twins' Request | Devola (after asking Anemone) | A2+9S | After #46 | - | Popola's Booze; guaranteed rare Monster Type unit |
| 48 | Heritage of the Past | Resistance Researcher, west of Desert Center | All 3 (GP: Route B) | After saving 9S in the Copied City (Ch08) | - | **Spear of the Usurper**, Gunman unit data, Mysterious Lithograph 2 |
| 49 | Retrieve the Confidential Intel | Resistance member near Engels | Sh | After Deep Cave | - | **A140: Gravity**, Large G Luck+ |
| 50 | Sorting Trouble | Resistance member, back of camp | Sh | After #14 | - | Evade Range Up +3 |
| 51 | Sorting Trouble 2 | same | A2+9S | After #50 | - | Drop Rate Up +3 |
| 52 | Sorting Trouble 3 | same | A2+9S | After #51 | - | **A120: Repair**, Jackass's Bomb Recipe |
| 53 | Stamp Collecting | Machine Receptionist, park gate | Sh | After Deep Cave | - | Precious Earrings, Fast Cooldown +3 |
| 54 | Parade Escort | Active Machine near the park manhole | Sh | - | - | Reset +3 |
| 55 | Gathering Keepsakes | Resistance Gravekeeper near the camp access point | 9S | Needs #36 (Emil's Memories) | 13-01..04, 15-01..04, 16-01/03/04, 17-01/02 | Max HP Up +6 |
| 56 | The Weapon Dealer's Request | Weapons Trader, Resistance Camp | Sh | Ch02 | **Mandatory** | Opens the Weapon Shop |
| 57 | The Recluse | Overprotective Machine, upper village | 9S | After Simone (Route B) | - | Evade Range Up +3 |
| 58 | The Recluse Stays Home | same | 9S | After #57 + Deep Cave | - | Resilience +3 |
| 59 | The Permanent Recluse | same | 9S | After #58 | - | Damage Absorb +3 |
| 60 | Emil's Determination | Emil, Shopping Center | All 3 | All weapons at Lv4 (incl. Emil Heads) | **One-shot; Ending Y** | Ending Y (optional) |
| D1 | Mysterious Letter | Mail from unknown (Plato 1728) | DLC | After Deep Cave | - | Unlocks the 3 arenas |
| D2 | Underground Colosseum | Forest Zone secret arena | DLC | After D1 | - | Young Man's Outfit, Masamune Mask (special trial) |
| D3 | Gambler's Colosseum | Flooded City secret arena | DLC | After D1 | - | Revealing Outfit, hair dyes, Record: CEO |
| D4 | Trial of Sand | Desert Zone secret arena | DLC | After D1 | - | Destroyer Outfit, Sand Mask, Proof of Oath |
| D5 | Mysterious Invitation | Mail after D1-D4 | DLC | - | - | Ending ◬, Record: 3C3C1D119440927 |

Disagreements are given inline as FX vs FD. FX's "dates" column is the most precise source for windows; FD gives the triggers.

Sources: https://nierautomata.wiki.fextralife.com/Side+Quests , https://nier.fandom.com/wiki/Quests_(Automata) and each linked quest page (via the API)

---

## 6. ACCESS POINTS

FD gives **18 access points** (they are save, transport and Inbox points; you respawn at them).
- Fast travel: only Bunker <-> Resistance Camp at first.
- FD says the network opens at the end of **Ch05** (after Engels and Adam & Eve, when Jackass introduces the City Ruins Deep Cave access point). FX Game Progress and GP say "Ch06". These are consistent if it opens at the 05/06 boundary (?).
- The Bunker becomes reachable from every ground access point in Ch06 (FD).
- Many access points are guarded by weak machines that must be killed before you can use them.

| Area | Access points | Becomes available (my mapping to area access, ?) |
|---|---|---|
| Bunker | Bunker | After the prologue (Ch01); gone from Ch12 |
| City Ruins | Near Abandoned Factory, Center, Near the Tower, Deep Cave (+ Resistance Camp transporter, see note) | Ch02; Deep Cave at the end of Ch05; "Near the Tower" Route C (?) |
| Desert Zone | Camp, Center, Oil Field, Housing Complex | Ch02/03 |
| Amusement Park | Attraction Square | Ch04 |
| Pascal's Village | Pascal's Village | Ch05; **unusable for fast travel after Ch10** (Eve) |
| Forest Zone | Center | Ch06 |
| Forest Castle | Front, Royal Chamber | Ch06 |
| Abandoned Factory | Entrance, Hangar, Furnace | Entrance Ch09 (?), others during Ch09/Ch14 (?) |
| Flooded City | Coast | Ch07 |

FD's named list (1+4+4+1+1+1+2+3+1) already adds up to the 18, without the Resistance Camp transporter. So the camp transporter is either not counted or is a separate "transporter" (?).

Sources: https://nier.fandom.com/wiki/Access_Point , https://nierautomata.wiki.fextralife.com/Locations , https://nierautomata.wiki.fextralife.com/Game+Progress+Route , https://www.gamepressure.com/nier-automata/route-b-what-can-be-transferred/z2ea93

---

## 7. SHOPS / MERCHANTS

FX lists 17 merchants. Chips bought from any merchant always have the maximum storage cost for their level (FD).

| Merchant | Location | Sells / services | Available |
|---|---|---|---|
| Supply Trader | Resistance Camp | Recovery items, basic chips (HUD, Auto chips, Item Scan), Sachet (1,000G), Sound Data 2-5 | After "The Supply Trader's Request" (Ch02). Stock grows each route: Sound Data 2 after A, 3 after B, 4 after the first A2/9S ending, 5 after C/D |
| Weapons Trader | Resistance Camp | Beastbane, Ancient Overlord, Beastlord; weapon upgrades to **Lv3** | After "The Weapon Dealer's Request" (Ch02) |
| Maintenance Shop Owner | Resistance Camp (by the medical bay) | Pod Programs R020-R070 / A060, **chip storage upgrades (max 128)**, Pod upgrades, chip fusion to +6 | Ch02 |
| Bunker Maintenance Shop | Bunker | Same as above (pod programs, storage, pod upgrades) (?) | Ch01-Ch11 |
| Bunker Item Shop + plug-in chip shop (server room) | Bunker | Items, chips | Ch01-Ch11 |
| Devola & Popola's shop | Resistance Camp | Unique chips (Continuous Combo, Auto-Collect Items, Evasive System, Bullet Detonation, Death Rattle), Type-3 Sword, Type-3 Blade | FD: "after 9S ends up in the Copied City" (Route B Ch08?); GP: Type-3 weapons Route C/D (?) |
| Strange Resistance Woman (secret vendor) | Resistance Camp | **Trophies/achievements** for G (e.g. Pod Hunter 50,000G) | After Route C/D is cleared; ask her to "unlock you-know-what" |
| Desert Camp Supply Trader | Desert Zone camp | Items | Ch02/03 (?) |
| YoRHa android trader | Desert Oil Field | E-Drug | (?) |
| Forest Zone Supply Trader | Forest Zone | Items | Ch06 (?) |
| Canyon Machine ("Ravine Supply Trader") | Forest ravine bottom | Items; **chip fusion to +8** after Lord of the Valley | Ch06+ |
| Amusement Park Shopkeeper Machine | Amusement Park | Items | Ch04/05 (?) |
| Pascal's Item Shop | Pascal's Village | Items; Machine Sword / Axe / Spear (GP: "Machine Village shop") | Ch05+. After the Ch14 memory wipe, sells **Machine Heads** (Ch15+) and parts of dead villagers |
| Weapons Trader Machine / Tool Shop Machine | Pascal's Village (?) | Machine weapons / tools (?) | Ch05+ (?) |
| Emil's Shop (mobile) | Drives around the City Ruins. Slow route from the overpass or the desert entrance; fast route outside the Resistance Camp. Can also fail to spawn | Slow: low materials or +3 chips, **Dress Module** (10,000G). Fast: **Type-3 Fists (20,000G), Angel's Folly (25,000G)**, high materials or +6 chips | FD: after the A2 fight at Forest Castle (Ch06); GP: from Ch07. Shoot him to stop him |
| Blacksmith Masamune (hidden) | Forest Castle, Royal Chamber AP: go right toward the bridge, drop down, push the crate | Weapon upgrades to **Lv4**; gives **Cruel Lament** after your first Lv4 | Ch06+ |
| Emil (home) | Emil's Residence (under the crater) | Not a shop; Lv99 Emil fight drops Emil Heads | After Emil's Memories |

Sources: https://nierautomata.wiki.fextralife.com/Merchants , https://nier.fandom.com/wiki/Resistance_Camp , https://nier.fandom.com/wiki/Emil's_Shop , https://nier.fandom.com/wiki/Masamune , https://nier.fandom.com/wiki/Bunker , https://nier.fandom.com/wiki/Sound_Data_2 (-5), https://www.gamepressure.com/nier-automata/list-of-weapons/z5eaf9

---

## 8. COLLECTIBLES

| Category | Count | How / best source |
|---|---|---|
| Weapons | **40** (FX): 13 small swords, 9 large swords, 9 spears, 9 combat bracers | Per-weapon table below. All carry over between routes |
| Pods | **3**: A (Gatling, default), B (Laser), C (Homing missiles) | Pod B: **fishing** in the Flooded City (coast/missile area, random). Pod C: a deactivated machine in the Desert, up a slope NW of the Oil Field AP (quest marker mid-Route A). All 3 are possible in Route A |
| Pod Programs | **17** | R010 Laser (prologue). R020 Mirage, R030 Hammer, R040 Blade, R050 Spear, A060 P Shield, R070 M Shield (Maintenance Shops). A080 Wave (Wandering Couple). A090 Wire (Amnesia). A100 Decoy (City Ruins building where you land, Route C/D). A110 Slow (Data Analysis Freak 2). A120 Repair (Sorting Trouble 3). A130 Bomb (Find a Present). A140 Gravity (Retrieve the Confidential Intel). A150 Volt (dead pod in the Amusement Park, Goliath Tank spot, Route C). A160 Missile (dead pod on a container near the start area, Route C). A170 Scanner (main quest "Redheads") |
| Fish | 37 fish-type (19 fish + 17 machine fish + Machine Lifeform Head) + 4 junk (Tire, Gas Cylinder, Battery, Broken Firearm); trophy needs 20 kinds | Fishing via the Pod near water. Mackerel comes from Jackass (eating it = Ending K). Iron Pipe weapon is fished in the park sewers. Many fish are Flooded City only |
| Unit data (Intel) | ~182 entries (FD); FX category totals ~172 with overlaps | Kill/encounter. Some need quests (Gunman via Heritage of the Past, gold machines as 9S in Route C) or rare spawns (Reverse-jointed Goliath ~1% in the Flooded City). 95% is needed for Reconnaissance Squad |
| Archives | **56** (FX): 10 Pearl Harbor Descent Records, 8 Saved Machine Records, 4 Engels Memories, 6 Data Saved on Server, 28 Old World Information | Chests, quests (Data on the Old World pays per archive), terminals (Anemone novels as A2) |
| Plug-in chips | ~50 types in 5 categories (System, Attack, Defense, Support, Hacking), levels 0-+8 | Drops (random cost, possible "diamond" cost), shops (max cost), quests. Carry limit 99 chips (FD) |
| Records / music | Sound Data 1 (YoRHa soldier at the jukebox), Sound Data 2-5 (Supply Trader after each route), Record: CEO (DLC Gambler's Colosseum), Record: 3C3C1D119440927 (DLC ◬), Engels Records 0005/0010/0020 (Machine Examination), Record of a Bestial Machine (Turf War) | Jukebox at the Resistance Camp |
| Sachets | 3: Sachet (Supply Trader 1,000G), Quality Sachet (Animal Care), Choice Sachet (Half-wit Inventor) | Animal-riding bait (?) |
| Outfits | Dress Module (Emil), Revealing Outfit (Gambler's), Young Man's Outfit (Underground), Destroyer Outfit (Trial of Sand), Heavy Armor A/B (Heavy Armor A from Ending C or D credits), A2 Wig (Ending C), 2P/P2 Body Replicas, YoRHa Uniforms (?) | |
| Accessories / masks | Pink & Blue Ribbon (Lost Girl), Alien Mask (Half-wit Inventor), Adam's Glasses (top of the City Ruins high-rise across from the landing point, Route C), Emil Mask (harvest point at Emil's Residence), Masamune Mask (DLC), Sand Mask (DLC), Lunar Tear (Emil's Memories), hair dyes (DLC), Valve/Matsuda/Sato masks and Fox masks (?) | Game of the YoRHa / Become As Gods edition bonus items (Cardboard/Retro Pods, Grimoire Weiss, Machine Mask, Valve items) are **not** in-world locations |
| Key items | Fuel Filter, Forest/Ocean/Park Access Keys, Elevator Key, Rigid Tree Bark, Stamp/Stamp Card, Data Chips A-E, Commandment Slab, Package, Memory Chip, Broken Toy, and other quest items | Quest-driven |
| Endings | 26 + ◬ | sec. 4 |

### Weapon sources (GP, plus FD where noted)

| Weapon | Type | Source | Earliest |
|---|---|---|---|
| Virtuous Contract | S | 2B start | A |
| Cruel Oath | S | 9S start | B |
| Bare Fists | Bracer | Default (FD) | - |
| Ancient Overlord, Beastbane, Beastlord | S, S, L | Resistance Camp Weapons Trader | A Ch02 |
| Machine Sword, Machine Axe, Machine Spear | S, L, Sp | Pascal's Village shop | A Ch05 |
| Type-3 Sword / Type-3 Blade | S / L | Devola & Popola | C/D (GP) (?) |
| Type-3 Fists, Angel's Folly | Bracer | Emil's Shop (fast pattern) | A Ch06/07 |
| Cypress Stick | S | High shelf, ruins in front of Forest Castle | A Ch06 |
| Engine Blade | S | Chest in the Abandoned Factory | A Ch09 |
| Faith | S | Soul Box tower (one visit) | C Ch15 |
| Iron Pipe | S | Fishing in the Amusement Park sewers | A Ch04 |
| Phoenix Dagger | S | Forest ravine (Lord of the Valley area) | A Ch06 |
| Type-4O Sword | S | Find a Present | A Ch07 (2B) |
| YoRHa-issue Blade | S | 11B's Memento | A (2B) |
| Cruel Blood Oath | L | Desert caves, hack-locked door | B Ch03 |
| Fang of the Twins | L | Chest in Desert Housing | A Ch03 |
| Iron Will | L | Flooded City, Scanner-revealed | after A170 |
| Phoenix Sword | L | City Ruins rooftop hack chest | B Ch02 |
| Type-4O Blade | L | Data Analysis Freak 2 | B |
| Virtuous Treaty | L | Abandoned Factory (first boss area) | A (?) |
| Beastcurse | Sp | Forest Castle library, hack chest | B Ch06 |
| Cruel Arrogance | Sp | Abandoned Factory, hack-locked door | C/D |
| Dragoon Lance | Sp | Chest in the central forest, reached down the river | A Ch06 |
| Phoenix Lance | Sp | Desert, Scanner-revealed, east of the Center AP | B Ch03 (after the Scanner) |
| Spear of the Usurper | Sp | Heritage of the Past | after Ch08 |
| Type-3 Lance | Sp | Flooded City rooftop chest | A Ch07 |
| Type-4O Lance | Sp | YoRHa Betrayers | A/B |
| Virtuous Dignity | Sp | Secret area, Amusement Park sewers | A Ch04 |
| Cruel Lament | Bracer | Masamune, after any Lv4 upgrade | A Ch06+ |
| Demon's Cry | Bracer | Chest in the Amusement Park main building basement | B Ch04 |
| Machine Heads | Bracer | Pascal after the memory wipe | C Ch15 |
| Type-4O Fists | Bracer | Resistance Camp hack chest next to the AP | B Ch02 |
| Virtuous Grief | Bracer | Central forest cliffs, guarded | A Ch06 |
| Emil Heads | Bracer | Defeat Lv99 Emil at his residence | after Emil's Memories |

Sources: https://nierautomata.wiki.fextralife.com/Weapons , https://www.gamepressure.com/nier-automata/list-of-weapons/z5eaf9 , https://nierautomata.wiki.fextralife.com/Pod+Programs , https://nierautomata.wiki.fextralife.com/Pods , https://nier.fandom.com/wiki/Pod_Hunter , https://nierautomata.wiki.fextralife.com/Fishing , https://nierautomata.wiki.fextralife.com/Archives , https://nierautomata.wiki.fextralife.com/Enemies , https://nier.fandom.com/wiki/Items_(Automata) , https://nier.fandom.com/wiki/Reconnaissance_Squad

---

## 9. BALANCE NOTES (for deciding what to lock)

This section mixes wiki facts with community opinion; opinion is marked as such.

- **Chip storage** is the main power limiter. It is bought at the Maintenance Shops (Bunker / Resistance Camp) up to **128**, and chips cost 1-31 each (FD).
  - Suggested lock: storage upgrades as progressive AP items.
- **OS Chip** (cost 2, equipped by default). Removing it means instant death and Ending T. Never randomize it away; keep it forced-equipped.
- **HUD chips** are part of the default loadout. Removing them frees storage, a common tip. They are low-value checks, or filler.
- **Auto chips** (Auto-Attack, Auto-Fire, Auto-Evade, Auto-Program, Auto-Weapon Switch) only work on Easy. You start with them; the Supply Trader also sells them. They can make hacking/arcade trivial (FD).
  - Suggested: leave them as starting items or treat them as an accessibility option.
- **Chip fusion:** +6 at the Maintenance Shop, **+8 only via the Canyon Machine** after Lord of the Valley (Ch06+). Lord of the Valley is a good candidate for a progression lock (?).
- **Chips commonly called strong (community):** Auto-Use Item and Auto-Heal (early), EXP Gain Up, Drop Rate Up (capped at 90%), Overclock (farmable on the Amusement Park rollercoaster), Critical Up, Anti Chain Damage, Offensive Heal / Deadly Heal / Damage Absorb, Weapon Attack Up (scales strongly at +5..+8), Shock Wave, Reset, Counter. Very Hard can be finished without +8 chips (FD).
- **Pod programs:** A170 Scanner is a key item (hidden harvest points, buried weapons). Treat it as progression in any rando that keeps those locations. A140 Gravity / A110 Slow / A120 Repair / A060 P Shield are commonly cited as strong (?).
- **Pods B/C:** missable only in the sense that Pod B is a random fishing roll. They are good AP items.
- **Weapons:** level 4 needs Masamune (hidden). Lv1-3 upgrades come from the Weapons Trader. Weapon levels gate Emil's Determination / Ending Y.
  - Suggested: weapons as items, Masamune access as a progression item (?).
- **Character mechanics:**
  - 9S: Fast slot only; hacking replaces heavy attacks, and the hacking chips (Hijack Boost, Combust, Stun, Heal Drops Up) only matter for him.
  - A2: has Berserk Mode (trophy "The Power of Hate").
  - Route C enemies are roughly Lv50 or more, so level carry-over matters (?).
- **Key progression items to randomize:** Fuel Filter, Rigid Tree Bark, Forest/Ocean/Park Access Keys (the Tower needs all 3), Elevator Key (Emil chain), Scanner. Also gate Weapon Shop / Supply Trader unlocks (they are mandatory quests).
- **Story-mandated:** the 3 mandatory quests (sec. 3). Removing them may need code changes; watch out.
- **Missable-check risks:** Improving Communications (05-02), Emil's Memories / Wandering Couple (before Ch07 Missile Supply), Terminal Repairs / Find a Present (07-01..03), Bunker content (Ch12+), Pascal's Village content (Ch14+), Soul Box Faith, the Park Theater (Ch16), Emil's Determination (one-shot). A randomizer should either exclude these or rely on Chapter Select.

Sources: https://nier.fandom.com/wiki/Plug-in_Chips , https://nier.fandom.com/wiki/OS_Chip , https://nierautomata.wiki.fextralife.com/Plug-in+Chips , https://nier.fandom.com/wiki/Masamune , https://twinfinite.net/ps4/nier-automata-tips-tricks-beginners/4/ , https://www.gamerevolution.com/guides/71797-nier-automata-a-guide-to-all-26-endings-no-spoilers

---

### Coverage gaps
- **Main-quest to subchapter mapping** (e.g. 07-01 = which quest) is not available in a clean list. FX/GP give chapter-level data only. Get it from the game data instead.
- **Access point unlock timings** per point are inferred from area access, not sourced.
- **Shop stock per chapter** (e.g. which Supply Trader items appear when) is only partly documented. FD notes that stock "grows on repeat playthroughs".
- **IGN/GameFAQs/Neoseeker** were not reached: GameFAQs and TrueAchievements returned 403, and BreezeWiki mirrors bot-blocked. The FD API was used instead.
