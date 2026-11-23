# Disponibilite des quetes (QuestChapterData.qch)

Genere par `tools/resolve_quests.py`. Une ligne de la qch = `u16 quete` + 128 octets, octet i = entree i de `ChapterData.cha` (point de selection de chapitre). 0 = quete absente de ce chapitre.

| valeur | sens |
|---|---|
| 1 | quete jouable avec **2B** uniquement |
| 2 | quete jouable avec **9S** uniquement |
| 3 | quete jouable avec **A2** uniquement |
| 4 | jouable avec tout personnage |

Preuve : 59/60 quetes : valeurs conformes a la colonne Route de web_reference.md (Sh/All3/A2+9S -> 4, 2B -> 1, 9S -> 2, A2 -> 3).
Ecarts : q590 (web All3, qch [2, 4]).

Les fenetres sont celles de la selection de chapitre (chapitres ou la quete existe), pas les prerequis : ex. q170/q171 (06-02..09-01 dans la qch) ne sont faisables qu'apres q162 (web : 07-01..07-03).
Valeur entre crochets = personnage requis (rien = tout personnage). Routes : A, B, A+B (chapitres communs 2B/9S), C/D.

| quete | nom | personnage | fenetres |
|---|---|---|---|
| q020 | Sartre's Melancholy | 2B, tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 ; hors table (indice 119): 2B |
| q031 | Machine Examination 1 | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q032 | Machine Examination 2 | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q040 | Family Squabble | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q071 | Animal Care | tout personnage | A+B: 06-03/04/05, 07-01/02/03 |
| q072 | Turf War | tout personnage | A+B: 06-03/04/05, 07-01/02/03 |
| q100 | Robo Dojo—White Belt | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q101 | Robo Dojo—Brown Belt | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q102 | Robo Dojo—Black Belt | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q103 | Robo Dojo—Red and White Belt | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q104 | Robo Dojo—Red Belt | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q110 | Lost Girl | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q120 | The Supply Trader's Request | tout personnage | A+B: 02-01/02, 03-01/02/03/04, 04-01/02/03/04, 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q121 | The Manager's Request | tout personnage | A+B: 04-01/02/03/04, 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q122 | Camp Development | tout personnage | A+B: 06-05, 07-01/02/03 |
| q123 | Anemone's Past | tout personnage | A+B: 06-05, 07-01/02/03 |
| q130 | Amnesia | 9S | A+B: 05-03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q140 | Resistance Disappearance | tout personnage | A+B: 04-01/02/03/04, 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q150 | Jackass's Research | 2B | A+B: 04-01[2B]/02[2B]/03[2B]/04[2B], 05-01[2B]/02[2B]/03[2B]/04[2B], 06-01[2B]/02[2B]/03[2B]/04[2B]/05[2B], 07-01[2B]/02[2B]/03[2B]/04[2B], 10-02[2B]/03[2B]/04[2B] ; A: 08-01[2B], 09-01[2B]/02[2B]/03[2B], 10-01[2B] ; B: 08-01[2B], 09-01[2B]/02[2B]/03[2B], 10-01[2B] |
| q160 | Improving Communications | tout personnage | A+B: 02-02, 03-01/02/03/04, 04-01/02/03/04, 05-01/02 |
| q162 | Investigating Communications | tout personnage | A+B: 06-01/02/03/04/05, 07-01/02/03 |
| q170 | Terminal Repairs | 2B | A+B: 06-02[2B]/03[2B]/04[2B]/05[2B], 07-01[2B]/02[2B]/03[2B]/04[2B] ; A: 08-01[2B], 09-01[2B] ; B: 09-01[2B] |
| q171 | Find a Present | 2B | A+B: 06-02[2B]/03[2B]/04[2B]/05[2B], 07-01[2B]/02[2B]/03[2B]/04[2B] ; A: 08-01[2B], 09-01[2B] ; B: 09-01[2B] |
| q180 | Data Analysis Freak | 9S | A+B: 03-01[9S]/02[9S]/03[9S]/04[9S], 04-01[9S]/02[9S]/03[9S]/04[9S], 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q181 | Data Analysis Freak 2 | 9S | A+B: 04-01[9S]/02[9S]/03[9S]/04[9S], 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q210 | Lord of the Valley | tout personnage | A+B: 06-03/04/05, 07-01/02/03 |
| q220 | Vanquish the Bad Bot | A2 | C/D: 14-01[A2]/02[A2]/03[A2] |
| q221 | Play with Us! | A2 | C/D: 14-01[A2]/02[A2]/03[A2] |
| q222 | Storage Element | A2 | C/D: 14-01[A2]/02[A2]/03[A2] |
| q240 | Half-wit Inventor | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 ; C/D: 12-01/02, 13-01/02/03/04, 14-01 |
| q250 | Idiot Savant | 9S | A+B: 05-03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q290 | Game Dev Machine Lv.1 | 9S | A+B: 04-04[9S], 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S]/04[9S], 10-02[9S]/03[9S]/04[9S] ; B: 08-01[9S], 09-01[9S]/02[9S]/03[9S], 10-01[9S] ; C/D: 13-01[9S]/02[9S]/03[9S]/04[9S] |
| q291 | Game Dev Machine Lv.2 | 9S | A+B: 04-04[9S], 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S]/04[9S], 10-02[9S]/03[9S]/04[9S] ; B: 08-01[9S], 09-01[9S]/02[9S]/03[9S], 10-01[9S] ; C/D: 13-01[9S]/02[9S]/03[9S]/04[9S] |
| q292 | Game Dev Machine Lv.3 | 9S | A+B: 04-04[9S], 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S]/04[9S], 10-02[9S]/03[9S]/04[9S] ; B: 08-01[9S], 09-01[9S]/02[9S]/03[9S], 10-01[9S] ; C/D: 13-01[9S]/02[9S]/03[9S]/04[9S] |
| q300 | Speed Star | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q330 | Emil's Memories | tout personnage | A+B: 06-03/04/05, 07-01/02/03 |
| q340 | Photographs | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q410 | 11B's Memento | 2B | A+B: 02-02[2B], 03-01[2B]/02[2B]/03[2B]/04[2B], 04-01[2B]/02[2B]/03[2B]/04[2B], 05-01[2B]/02[2B]/03[2B]/04[2B], 06-01[2B]/02[2B]/03[2B]/04[2B]/05[2B], 07-01[2B]/02[2B]/03[2B]/04[2B], 10-02[2B]/03[2B]/04[2B] ; A: 08-01[2B], 09-01[2B]/02[2B]/03[2B], 10-01[2B] ; B: 09-01[2B] |
| q440 | Treasure Hunt at the Castle | tout personnage | A+B: 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 ; C/D: 12-01/02, 13-01/02/03/04, 14-01 |
| q500 | The Wandering Couple | tout personnage | A+B: 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q520 | Data on the Old World | 9S | A+B: 05-03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q532 | Culinary Researcher | tout personnage | A+B: 06-05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 ; C/D: 12-01/02, 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
| q540 | YoRHa Betrayers | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q550 | Reconnaissance Squad | 9S | C/D: 13-03[9S]/04[9S], 15-01[9S]/02[9S]/03[9S]/04[9S], 16-01[9S]/02[9S]/03[9S], 17-01[9S]/02[9S] |
| q560 | Devola's Request | tout personnage | C/D: 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
| q561 | Popola's Errand | tout personnage | C/D: 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
| q562 | The Twins' Request | tout personnage | C/D: 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
| q590 | Heritage of the Past | 9S, tout personnage | A+B: 03-01[9S]/02[9S]/03[9S]/04[9S], 04-01[9S]/02[9S]/03[9S]/04[9S], 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S]/04[9S], 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q640 | Retrieve the Confidential Intel | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q650 | Sorting Trouble | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03 |
| q651 | Sorting Trouble 2 | tout personnage | C/D: 12-01/02, 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
| q652 | Sorting Trouble 3 | tout personnage | C/D: 12-01/02, 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
| q660 | Stamp Collecting | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q680 | Parade Escort | tout personnage | A+B: 05-03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q720 | Gathering Keepsakes | 9S | C/D: 13-01[9S]/02[9S]/03[9S]/04[9S], 15-01[9S]/02[9S]/03[9S]/04[9S], 16-01[9S]/02[9S]/03[9S], 17-01[9S]/02[9S] |
| q770 | The Weapon Dealer's Request | tout personnage | A+B: 02-01/02, 03-01/02/03/04, 04-01/02/03/04, 05-01/02/03/04, 06-01/02/03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 |
| q800 | The Recluse | 9S | A+B: 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q801 | The Recluse Stays Home | 9S | A+B: 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q802 | The Permanent Recluse | 9S | A+B: 05-01[9S]/02[9S]/03[9S]/04[9S], 06-01[9S]/02[9S]/03[9S]/04[9S]/05[9S], 07-01[9S]/02[9S]/03[9S] |
| q900 | Emil's Determination | tout personnage | A+B: 06-03/04/05, 07-01/02/03/04, 10-02/03/04 ; A: 08-01, 09-01/02/03, 10-01 ; B: 08-01, 09-01/02/03, 10-01 ; C/D: 12-01/02, 13-01/02/03/04, 14-01/02/03/04/05, 15-01/02/03/04, 16-01/02/03, 17-01/02/03/04 |
