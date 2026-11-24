# Ouvrir un magasin et acheter sans voir l'ecran (NieR:Automata v1.04 Steam)

Analyse **statique** uniquement (`NieRAutomata.exe` + scripts mruby des .dat ; jeu jamais attache, rien ecrit).
Adresses = RVA (base 0x140000000). Outils : `tools/xref.py`, capstone, `tools/mruby.py`, `tools/cpk.py`.
**Rien n'a ete verifie en execution** : la section 8 liste les controles a faire.

Confiance : **haute** = lu dans le desassemblage et recoupe par un second chemin ; **moyenne** = lu dans le
desassemblage seul ; **faible** = deduit.

## Resume

| Besoin | Solution | Confiance |
|---|---|---|
| Ouvrir un magasin par son nom | `remote_call(base+0x81C870, ptr nom)` : copie le nom en `0x13FD658` et pose le bit `0x1000` de `u32 [0x1251558]` ; la boucle de jeu l'ouvre a l'image suivante | haute (code), non teste |
| Savoir qu'il est ouvert | `u32 [0x13FD7B8] == 0xE` (c'est exactement `shop_open?`) puis `u32 [0x1410E00+0x12FC] == 1` | haute |
| Aller a la liste d'achat | A (0x10) sur le 1er choix -> `[+0x12FC] == 2` | moyenne |
| Acheter le 1er objet (MaxNum 1) | A -> dialogue Oui/Non **curseur sur Non** -> croix gauche (1) -> A | moyenne |
| Achat direct | `0x898EE0(obj magasin, id objet)` (magasin ouvert, etat 2) ou bas niveau `0x7CA0B0` + `0x7CB410` | moyenne, risque de fil |
| Parler au PNJ | non recommande : condition d'entree du joueur non resolue | faible |

## 1. Ouverture par script

### 1.1 Scripts mruby

`st1/r140.dat:r140_82d2caac_scp.bin`, methode `pv_sp_ON_TALK_ev0` (meme forme dans les 4 autres scripts du village
et dans `st1/r160.dat:r160_441c44e3_scp.bin` `fc_m1_ON_TALK_ev0/ev1`, `fc_m1_ON_TALK_2_ev3`) :

```
mess_ex([...], [{xti: 'robotoolshop'}, ...])     # dialogue
shop('shop_PV_Grocery')                           # <- ouverture
wait_signal('END_PV_GROCERY', global)             # attend la fermeture
mess_ex(...)
set_trigger_state('ev1')
```

Foret : `shop('shop_FC_Grocery')` puis `wait_signal('END_FC_GROCERY', global)`.
Declencheurs (methode `update`) : `event_trigger('pv_sp_ON_TALK/ev0', 'pv_sp', 'ON_TALK')`,
`event_trigger('fc_m1_ON_TALK/ev0', 'fc_m1', 'ON_TALK', 'Collapse_BK')`.

### 1.2 Natif - confiance haute

Enregistrement (0x34B891..0x34B8CB, `mrb_define_method` 0x295300) : `shop` -> 0x3362F0, `shop_open?` -> 0x336530.

0x3362F0 convertit l'argument en chaine C puis appelle **0x81C870(rcx = const char* nom)** (seul appelant : 0x336494) :

```
0081c870  sub rsp, 0x28
0081c874  cmp dword ptr [0x102a368], 1        ; etat de scene == 1, sinon rien
0081c87b  jne 0x81c8a2
0081c87d  mov r8, rcx                         ; nom (utilise comme FORMAT : pas de '%')
0081c880  mov edx, 0x20
0081c885  lea rcx, [0x13fd658]                ; tampon du nom, 0x20 octets
0081c88c  call 0x138820                       ; vsnprintf(dst, taille, fmt, ...)
0081c891  or dword ptr [0x1251558], 0x1000    ; demande "ouvrir le magasin"
0081c89b  mov byte ptr [0x13fd677], 0         ; NUL final
```

`shop_open?` (0x336530) = `cmp dword ptr [0x13fd7b8], 0xe`.

### 1.3 Consommation de la demande - confiance haute

0x839390 (gestionnaire par image de l'etat "pas de menu") :

```
00839560  mov eax, [0x1251558] ; shr eax, 0xc ; and eax, 1 ; je ...
0083956e  mov dword ptr [0x11eac2c], 2        ; machine a etats des menus : ouverture
00839578  mov dword ptr [0x11eac48], 0        ; etape 0
00839582  xor r8d,r8d ; xor edx,edx ; lea ecx,[rdx+0xe]
0083958a  call 0x8fd480                       ; [0x13fd7b8] = 0xE (mode de menu = magasin)
0083958f  btr eax, 0xc ; bts eax, 7 ; mov [0x1251558], eax
```

Conditions lues avant ce test (sinon la demande **reste en attente**, bit 0x1000 toujours pose) :
`byte [0x1029B83] & 1 == 0`, `[0x102A368] == 1`, `0x85E3A0()` (= `[0xF64A9C] & ~2 == 0`), pas de phase 0xFxx sans
drapeau, `[0x1029B04] & 0x4000000 == 0`, `[0x1415CC4] == [0x1415620] == [0x14159E0] == [0x11EA248] == 0` (autres
interfaces), joueur (0x7C4F50) : `vfunc[0xE8]() != 0`, `0x49EB50(pl, 0x38) == 0`, `0x49EB50(pl, 0x37) == 0`, et deux
minuteries `float [0x124BD74]`, `[0x124BD78]` a zero. Sens exact de chaque condition non etabli (faible).

Suite (0x83B5C8.., etat 2 de `[0x11EAC2C]`) : `[0xF554AC] = 2` quand le mode vaut 0xE, musique `BGM_Shop_In`
(`BGM_ShopEmil_In` si type 2/3), `[0x1029B00] |= 0x80000000`. L'objet magasin est initialise par
0x8BD710(0x1410E00) (appele en 0x8AF2C2) : cherche l'etat `Shop/7..1` actif, puis
`0x823C40(0x133B890, nom = 0x13FD658, etatName)` (lecture de ShopInfoTable).

Fermeture : 0x89F940(0x1410E00) (appele en 0x8A02C6) emet le signal `END_%s` avec le nom en majuscules sans les 5
premiers caracteres (`shop_PV_Grocery` -> `END_PV_GROCERY`) ; `END_%s_FIRST` pour shop_RC_Smith, `END_EMILE` pour les
types 2/3. Ouvert de l'exterieur, aucun script n'attend ce signal (effet suppose nul, non verifie).

### 1.4 Appel depuis l'exterieur

Chaines deja presentes dans l'exe (pas d'allocation) :

| Magasin | RVA de la chaine |
|---|---|
| `shop_PV_Grocery` | 0xCFC0E8 |
| `shop_FC_Grocery` | 0xCFBFE0 |
| `shop_RC_Grocery` | 0xCFBF98 |

**Recommande** : `remote_call(mem, base + 0x81C870, base + 0xCFC0E8)` (1 argument, pas de valeur de retour utile).
La fonction ne touche que des globales (tampon + un `or` d'une instruction) : pas d'appel moteur, pas d'allocation.
Risque de fil : le `or dword [0x1251558]` n'est pas verrouille ; une modification simultanee du meme mot par le fil du
jeu peut perdre un des deux bits (fenetre de quelques nanosecondes). Si le magasin n'est pas ouvert apres ~1 s et que
le bit 0x1000 est a 0, refaire l'appel.

Variante sans appel (ecritures seules) : ecrire le nom ASCII + NUL (31 caracteres max) en `0x13FD658`, `u8 0` en
`0x13FD677`, puis `u8 [0x1251559] |= 0x10` (lire/modifier/ecrire l'octet : la course ne concerne alors que les bits
8..15, mais la fenetre est bien plus longue que pour l'appel). Verifier d'abord `[0x102A368] == 1`.

Le PNJ n'a pas besoin d'exister ni d'etre proche : la demande ne reference que le nom. Le dialogue d'avant/apres
(`mess_ex`) et `set_trigger_state` ne sont pas joues.

## 2. Objet magasin `0x1410E00` - champs

Mise a jour par image : 0x94ABC0(0x1410E00) (seul appelant 0x94132C), table de sauts 0x94B290 sur `[+0x12FC]`.

| Offset | Type | Contenu | Preuve |
|---|---|---|---|
| +0x0 | u32 | 0 a l'ouverture, 1 quand l'ecran est termine | 0x8BD740, 0x94B278 |
| +0x728 | i32[0x2F4] | **ids des objets de la liste courante**, -1 = vide | 0x8DA760, 0x976699 |
| +0x12F8 | i32 | nombre d'objets de la liste | 0x8DA7DA |
| +0x12FC | u32 | **etat** (table ci-dessous) | 0x94ABC6 |
| +0x1300 | u32 | sous-etat de l'etat 9 | 0x94B05F |
| +0x1304 | i32 | **curseur de liste** (indice dans +0x728) | 0x976692 |
| +0x1308 | i32 | **curseur du menu racine** | 0x96B0B5 |
| +0x130C | i32 | defilement de la liste (9 lignes visibles) | 0x898FF2 |
| +0x1310 | i32 | **quantite** | 0x9783EE, 0x898FB6 |
| +0x1318 | u8 | 1 = selection de quantite en cours | 0x8B8DC1, 0x976879 |
| +0x1319 | u8 | 1 = dialogue de confirmation en attente | 0x8B8E32 (`word = 0x100`), 0x976886 |
| +0x131C | u32 | niveau max d'amelioration d'arme (1 ou 2) | 0x94AD6E |
| +0x1330/+0x1332 | u8 | une arme a ete achetee | 0x898F2C |
| +0x134C | u32 | type de magasin (0x8ABFE0) | 0x8EF7CB |
| +0x1F40..+0x1F78 | ptr | widgets ; etat force a 0xB si +0x1F40/+0x1F48 nuls | 0x94ABD4 |
| +0x1F80 | i32 | identifiant du dialogue ouvert, -1 = aucun | 0x8BD777, 0x978029 |
| +0x36F8 | i32 | nombre d'entrees du menu racine | 0x8EFE72 |
| +0x370C | i32 | **pourcentage de prix** (100, ou remise) | 0x8EF8D9 |
| +0x3710 | i32[] | nature de chaque entree du menu racine | 0x8EFE30 |

**Ecart avec `shop.py`** : `SHOP_LIST_OFFSET = 0x748`. Le code remplit et lit la liste a partir de **+0x728**
(`lea rax,[rcx+0x728]` en 0x8DA76D, `mov [rdi+rcx*4+0x728], eax` en 0x8DA7FA, `mov esi,[rcx+rax*4+0x728]` en
0x976699, rcx = 0x1410E00). +0x748 = 9e entree : `displayed_ids()` ignorerait les 8 premiers objets (dont les
porteurs places en tete) et renverrait une liste vide pour un magasin de 8 objets ou moins. A verifier en jeu.

Etats `[+0x12FC]` :

| Etat | Sens | Gestionnaire |
|---|---|---|
| 0 | initialisation (attend la fin du fondu 0x9D43C0) -> 1 (ou 5 pour le type 7) | 0x94AC1D |
| 1 | **menu racine** | 0x96AE80 |
| 2 | **liste Acheter** | 0x976660 |
| 3 | amelioration d'arme (attend 0x7F8240) | 0x976660 |
| 4 | liste Vendre | 0x976660 |
| 5 | magasin de succes (type 7) | 0x976660 |
| 6 / 7 / 8 | amelioration de Pod / achat shop_Upgrade / fusion de puces | 0x976660 |
| 9 | sequence speciale apres achat (sous-etat +0x1300) | 0x94B05F |
| 0xA | attente (fin T) | - |
| 0xB | termine (`[+0] = 1`) | 0x94B278 |

Les libelles 3..8 sont deduits des sons et textes (`core_stepup`, `core_pluginchip_synthesis`, `SHOP_DIALOG_*`).

Type (0x8ABFE0, suffixe du nom apres le dernier `_`) : Grocery 0, Smith 1, Emile 2 (+ chipEmile), rareEmile /
rareChipEmile 3, UniqueShop 4, FoodShop 5, Upgrade 6, Achievement 7, shop_VF_Grocery 8, shop_PC_Grocery_first 0.

Menu racine (0x8EF91E..), type 0 (Grocery) : **2 entrees** = `SHOP_BASE_01` nature 0 (Acheter, etat 2) et
`SHOP_BASE_03` nature 1 (Vendre, etat 4). Smith : 3 entrees (0, 3, 1). `[+0x1308]` vaut 0 a l'ouverture (0x94AD8B).
"Acheter/Vendre" deduit de l'etat atteint et des sons `core_shop_buy` / `core_shop_sell` (moyenne).

Indicateur global : `u8 [0x13FD589]` = 1 au menu racine, 0 quand une liste non vide est ouverte (0x96BDF8) ;
role "B ferme le menu" suppose (faible).

## 3. Deroule des entrees

Valider = A (0x10), annuler = B (0x20), croix : gauche 1, droite 2, bas 4, haut 8 (voir remote_control.md 4.4).

1. **Etat 1, A** (0x9BAFF0 en 0x96B1D4) avec `[+0x3710 + 4*curseur] == 0` : 0x8DA760 reconstruit la liste
   (`0x7EA920(0x133B890, i)` pour i < 0x2F4) ; si `[+0x12F8] > 0` : `[+0x1304] = 0`, `[+0x130C] = 0`,
   `[+0x12FC] = 2` (0x96B5F0). Liste vide : reste en etat 1.
2. **Etat 2, A** sur l'objet `id = [+0x728 + 4*[+0x1304]]` (0x97763B) :
   - 0x8B3F50 = achat possible : possede < max (`0x8AE370` : `0x7E3B90(0xF56120,id) >= 0x7E49D0(0x133B890,id)`
     bloque) et `argent >= prix unitaire`. Puce (3000..3999) : aussi `[0xF5D0EC] < 200`.
   - possible -> 0x8B8D60 : **arme ou max == 1** : pas de quantite, `[+0x1310] = 1`, `[+0x1318] = 0`,
     `[+0x1319] = 1`, dialogue `SHOP_DIALOG_01` ; **sinon** mode quantite `[+0x1318] = 1`, `[+0x1310] = 1`.
   - deja au max -> son `core_menu_error`, rien d'autre.
   - argent insuffisant -> dialogue d'information (0x8E2850, `[+0x1F80] != -1`, `[+0x1319] == 0`) a fermer.
3. **Mode quantite** (0x978317) : haut +1, bas -1, droite +10, gauche -10 (bornes 0x8A71E0), **A** -> 0x8C4260 :
   `[+0x1318] = 0`, `[+0x1319] = 1`, dialogue avec le total ; **B** -> sortie du mode.
4. **Dialogue Oui/Non** (0x2F4940(texte, 0, 0, 1) -> 0x2F5060 -> 0x2F53D0 sur l'objet `0xF04030`) :
   `[0xF04038]` etat (1 ouverture, **2 choix actif**, 4 fermeture, 0 aucun), **`[0xF04068]` curseur : 1 = Oui,
   2 = Non**, `[0xF04070]` resultat (1 Oui, 2 Non), `[0xF04088]` widget (nul une fois ferme).
   Ouverture (0x2F6096) : parametre `[+0x34] == 2` -> **curseur initial 2 = Non**. Gauche (0x9BBD50, masque
   0x10001) : 2 -> 1 ; droite (0x9BBFC0, 0x20002) : 1 -> 2 ; A : resultat = 1 si curseur == 1, sinon 2 ;
   B : ramene le curseur sur Non, puis annule.
5. **Resultat 1** (0x9780D6, `0x2F4810([+0x1F80]) == 1`, renvoye une fois le widget detruit) :
   `0x898EE0(obj, id)` puis `[+0x1319] = 0`, `[+0x1F80] = -1`. Resultat 2 : `[+0x1319] = 0`.
6. **B** en etat 2 -> etat 1 (0x977BFB) ; B au menu racine -> fermeture (chemin generique des menus, non trace).

Pour un porteur (pod skin 950..958, `MaxNum` 1 dans ItemInfoTable) : **A, A, gauche, A** = achete.
Pour un objet empilable : **A, A, A, gauche, A**.

## 4. Fonction d'achat

**0x898EE0(rcx = objet magasin 0x1410E00, edx = id d'objet)**, seul appelant 0x97819A. Branche `[+0x12FC] == 2` :

```
00898f13  lea eax,[rdx-0x3e8] ; cmp eax,0x3e7 ; ja ...      ; 1000..1999 = arme
00898f20  lea rcx,[0xf5e528] ; call 0x7cc270                 ; ajoute l'arme ; [+0x1330] = [+0x1332] = 1
00898f3c  lea eax,[rdx-0xbb8] ; cmp eax,0x3e7 ; ja ...      ; 3000..3999 = puce
00898f61  lea rcx,[0xf5d0d0] ; call 0x7cb9c0                 ; (id, quantite [+0x1310], 0x7E49C0(0x13C9860, id))
00898f6f  mov r8d,[rcx+0x1310] ; lea rcx,[0xf56120]
00898f7d  call 0x7ca0b0                                      ; objet : addItem(0xF56120, id, quantite)
00898f82  mov r8d,-1 ; mov edx,esi ; lea rcx,[0x133b890]
00898f91  call 0x7dc0c0                                      ; prix d'achat de l'etat de route courant
00898f98  imul edx,[rdi+0x370c] ; ... /100                   ; remise (troncature)
00898fb6  mov edx,[rdi+0x1310] ; imul edx,r8d ; neg edx
00898fc2  lea rcx,[0xf56120] ; call 0x7cb410                 ; argent += -total
00898fce  mov rcx,rdi ; call 0x8da760                        ; reconstruit la liste, puis rafraichit les widgets
```

- Argent : `0x7CB410(0xF56120, delta)` = `*[0xF56190] += delta`, borne 0..9 999 999, succes 0x25 a 100 000.
- Prix : `0x7DC0C0(0x133B890, id, -1)` = `[fiche + 0x98 + 8*etat]`, `etat = 0x7E68C0()` = dernier etat de prix actif
  (State_0 Default, State_1 Route/B, State_2 Route/C). **`shop.set_price` n'ecrit que +0x98** : en route B/C le prix
  lu serait +0xA0/+0xA8 (non modifie). A verifier.
- **Aucun compteur "vendu" par magasin** dans ce chemin : la liste est simplement reconstruite (0x8DA760 ->
  0x7EA920, filtre non desassemble).
- Autres branches : etat 4 = vente, 3 = amelioration d'arme, 6 = Pod.

Appel direct possible : `remote_call(base+0x898EE0, base+0x1410E00, id)` **seulement** si le magasin est ouvert en
etat 2 avec `[+0x1310] = 1` : la fin de la fonction manipule les widgets (`[+0x1F48]`) depuis un fil etranger
pendant que le fil du jeu les met a jour -> risque de plantage. Non recommande.

Bas niveau, sans magasin : `remote_call(base+0x7CA0B0, base+0xF56120, id, 1)` puis
`remote_call(base+0x7CB410, base+0xF56120, -prix & 0xFFFFFFFFFFFFFFFF)`. Reproduit "objet + baisse d'argent" mais
ne prouve pas que l'objet est en vente dans le magasin vise ; 0x7CA0B0 est une grosse fonction (popup de gain
possible, non lue en entier), meme reserve de fil.

### Remises (impact sur `PaymentWatch`)

0x8EF780 calcule `[+0x370C]` a chaque ouverture :

- magasins de la table 0xF65130 (11 noms : RC_Grocery, RC_Grocery_small, DP, BK, **FC_Grocery**, DC, DO, RC_Smith,
  FC_FoodShop, Upgrade, CS_Grocery) : **70 %** si l'arme 1080 (YoRHa-issue Blade) est possedee avec un niveau
  stocke >= 2 (`0x7EF820` / `0x7EE4A0` sur 0xF5E528, champ +0x1808) ;
- magasins de la table 0xF65190 (12 noms : PV_UniqueShop, VF, GP, PC, PC_first, AP, PV_Smith, FC_Smith, GP,
  **PV_Grocery**, CF, CD) : **100 - 10 par arme** parmi 1090, 1270, 1480, 1650 (Machine Sword / Axe / Spear /
  Heads) au niveau stocke >= 2 ;
- sinon 100.

Somme debitee = `floor(prix * pct / 100) * quantite`. Avec une remise, la baisse est **inferieure au prix du
porteur** : `PaymentWatch.paid(price)` (baisse >= prix) ne compterait pas l'achat. Lire `[0x1410E00+0x370C]`
magasin ouvert, ou comparer a `price * pct // 100`. Base du niveau (0 ou 1) non etablie.

## 5. Interaction "parler"

- Gestionnaire d'invites 0x82713F : aiguillage sur la nature de l'entree `[entree+8]` (table 0x827FF8 / 0x827F94).
  **Nature 60 -> 0x7CFFB0** (appui simple), **62 -> 0x7D01B0** (appui maintenu : jauge `[mgr+0xB8]` +4 par image
  jusqu'a 100), 61 -> 0x7CF280.
- 0x7CFFB0(mgr, entree) : cible = `0x745F20(entree)`, joueur = `0x3085C0(handle 0x12505DC)`. Invite masquee si
  `[0x1029B04] & 0x400`, ou `vfunc[0x128]` d'un objet global, ou bit de la cible dans `[mgr+0xB0..]`, ou
  `[entite+0xBCC]`. Sinon `0x479E90(joueur, cible, 0)` ; si vrai et `[joueur+0x163FC] <= 0` :
  **`cible->vfunc[0x3E8]()`** (0x7D013B).
- vfunc 0x3E8 par defaut = 0x420210 : emet le signal de hachage **0x28CB0EFB = crc32("ON_TALK")** par
  0x4F6F80 ; le script le recoit par `event_trigger(..., 'ON_TALK')`.
- Condition d'entree dans 0x479E90 : `[joueur+0x10D54] != 0`, `[joueur+0x14A4] != 0` (ou `[+0x12AEC]` et cible
  d'un certain type), `[joueur+0x1767C] <= 0`, et
  `[joueur+0x13CC] == 0 ? [joueur+0x141C] > 0 : [joueur+0x1410] > 0`. **Le lien entre ces champs et un bouton n'est
  pas etabli** (l'action 2 = B reste une deduction de remote_control.md).
- **Portee / orientation : non trouvees.** 0x7CFFB0 ne fait aucun test geometrique ; l'entree d'invite est creee
  ailleurs (code non localise). Les natures 3..6 testent la position de la cible dans le repere du joueur
  (|x| et |y| bornes, 0 <= z <= 5.0 ou 15.0) mais ce ne sont pas les natures de dialogue.

Conclusion : parler au marchand demande de placer le joueur, de l'orienter et d'appuyer sur un bouton non confirme,
puis de passer 1 ou 2 messages. La demande de la section 1 evite tout cela.

## 6. PNJ marchands (source : `world_positions.json`, arbres `*_hap.pak`)

| Magasin | objId | Position (x, y, z) | Rotation Y | Entite | Fichier / hap | Variable, NameTag |
|---|---|---|---|---|---|---|
| shop_PV_Grocery | **em200b** | (468.1226, 10.9758, -46.9025) | -1.6752 | 0xECCE6DD0 | `st1/r140.dat:r140_hap.pak`, hap `通常時_村人配置(2)`, action `オブジェ配置エリア_鍛冶屋/道具屋` | `pv_sp`, `robotoolshop` (Lv 10) |
| shop_FC_Grocery | **pl2040** | (94.7618, 6.8038, -296.7053) | 0.44 | 0x2DF8053B | `st1/r160.dat:r160_d73bbe76_grp.pak`, hap `森の出張キャンプ`, action `オブジェ配置` | `fc_m1`, `resiitem` |

- Village : groupes `通常訪問時＿村人配置` / `村人＿通常訪問時` = present sauf etats `PV_NPCLayout_1`, `_1_2`, `_2`,
  `_3`, `_lost`. Scripts qui ouvrent le magasin : r140_82d2caac (apres l'effondrement), r140_f82d8b66 (avant),
  r140_cd4fd96a (apres la destruction du Bunker), r140_29cb90b (serieux), quest/q221_b113244a.
- Foret : groupe `森の出張レジスタンスキャンプ` (0xD73BBE76, attribut 0x40) = etats `q122/DONE` / `q122_DONE` :
  **le camp de la foret n'existe qu'apres la quete q122**. Declencheur conditionne par `Collapse_BK`. Aussi ouvert
  par quest/q532_65ff89bf.
- Le lien objet -> magasin vient de la methode `<variable>_ON_TALK*` qui contient `shop('...')` (haute).

## 7. Procedure minimale

Prealables : patch anti-pause et injection manette de remote_control.md actifs, joueur en jeu libre (pas de menu,
pas de cinematique, pas de dialogue).

1. Lire `[0x102A368] == 1` et `[0x13FD7B8] != 0xE`.
2. `remote_call(base+0x81C870, base+0xCFC0E8)` (village) ou `base+0xCFBFE0` (foret).
3. Attendre (<= 5 s) `[0x13FD7B8] == 0xE` puis `[0x1410E00+0x12FC] == 1` et `[+0x36F8] == 2`, `[+0x1308] == 0`.
   Echec : si le bit 0x1000 de `[0x1251558]` est encore pose, une condition de 1.3 bloque (la demande partira plus
   tard) ; s'il est a 0 et le mode != 0xE, refaire l'etape 2.
4. A (tenir ~100 ms). Attendre `[+0x12FC] == 2`. Controler `[+0x12F8] > 0`, `[+0x1304] == 0`, et
   `i32 [+0x728]` == id du porteur attendu (sinon arreter : B, B).
5. A. Attendre soit `[+0x1319] == 1` (dialogue de confirmation), soit `[+0x1318] == 1` (quantite : refaire A),
   soit `[+0x1F80] != -1` avec `[+0x1319] == 0` (argent insuffisant : A pour fermer, puis abandon).
6. Attendre `[0xF04038] == 2`. Tant que `[0xF04068] != 1` : croix gauche. Puis A.
7. Succes : `[+0x1319] == 0`, `[+0x1F80] == -1`, argent `*[0xF56190]` diminue de `prix * [+0x370C] / 100`,
   l'objet est dans l'inventaire.
8. B (attendre `[+0x12FC] == 1`), B (attendre `[0x13FD7B8] != 0xE`).

Entre deux appuis, attendre le changement de champ plutot qu'un delai fixe (les etats 0 et 1 attendent la fin des
animations : 0x9D43C0, 0x125C90).

## 8. A verifier en execution

1. L'appel 0x81C870 depuis un fil etranger ouvre bien le magasin hors dialogue (camera, joueur fige, retour au jeu
   correct a la fermeture, signal `END_*` sans auditeur).
2. Liste a +0x728 (et non +0x748) ; `[+0x12F8]` = nombre d'objets affiches.
3. Menu racine d'un Grocery : 2 entrees, curseur initial sur Acheter.
4. Curseur initial du dialogue sur Non (`[0xF04068] == 2`) et gauche -> Oui.
5. Porteur (MaxNum 1) : pas d'etape de quantite ; `0x7E49D0` renvoie bien MaxNum (lu : champ +8 d'une fiche).
6. Valeur de `[+0x370C]` dans les deux magasins et effet sur `PaymentWatch`.
7. Prix lu en route B/C (+0xA0 / +0xA8).
8. Valeur de repos de `[0x11EAC2C]` et sens des conditions de 1.3.
9. B au menu racine ferme le magasin ; `[0x13FD589]`.
10. Champs d'entree du joueur de 0x479E90 (+0x1410 / +0x141C / +0x13CC) si la voie "parler" est un jour necessaire.

## 9. Non trouve

- Creation des entrees d'invite (portee, orientation) et bouton exact de l'interaction.
- Filtre de 0x7EA920 (quels objets de ShopInfoTable apparaissent : etat du magasin, objets uniques deja possedes).
- Chemin exact de fermeture par B au menu racine.
