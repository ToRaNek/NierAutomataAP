# Pilotage du jeu sans focus (NieR:Automata v1.04 Steam)

Analyse **statique** de `NieRAutomata.exe` uniquement (jeu jamais attache, rien ecrit). Toutes les adresses sont des
RVA (base 0x140000000). Outils : `tools/xref.py` + capstone. **Rien de ce document n'a ete verifie en execution** :
voir la section 6 pour la liste des controles a faire avant de s'y fier.

Niveaux de confiance : **haute** = lu dans le desassemblage et recoupe par un second chemin de code ou une table de
l'exe ; **moyenne** = lu dans le desassemblage seul ; **faible** = deduit (semantique supposee).

## Resume pour le client

| Besoin | Solution proposee | Confiance |
|---|---|---|
| Pas de pause quand la fenetre perd le focus | ecrire `u32 1` a `0x1495A8C` (drapeau d'option), ou 2 patchs de code de 1 octet (0x9C6280 `02`->`00`, 0x86C5DC `05`->`03`) | moyenne |
| Manette lue sans focus | deja le cas : la lecture XInput n'est coupee que si minimise/overlay (masque 0x24), mais l'etat est remis a zero plus haut si inactif ET `[0x1495A8C]==0` | moyenne |
| Injection d'entrees | detour de l'appel `0x277438` (`call 0x278D10`, lecture XInput du pad) vers une cave qui OR un etat pilote par le client | moyenne |
| Bouton interagir / ramasser | action 2 = bouton B = masque `0x20` (preset A par defaut) ; table vivante `0x1495B18` | moyenne (table), faible (libelle "interagir") |
| Valider un menu | masque `u32 [0xF72990]` = `0x10` (A) ; annuler `u32 [0xF72994]` = `0x20` (B) | haute |
| Stick gauche | `raw+4` = X, `raw+8` = Y, flottants -1..1, **Y inverse (haut = negatif)** | haute |
| Fonction "ramasser / ouvrir le coffre" | **non identifiee** | - |

## 1. Fenetre et drapeaux de focus

### Procedure de fenetre - confiance haute

- Classe enregistree en 0x26E141 (`RegisterClassExA`), WndProc = 0x26DD80. L'objet fenetre est statique :
  `0xF83030` (passe en `lpParam` de `CreateWindowExA` en 0x26E20B, range dans `GWLP_USERDATA`), `HWND` en `0xF83038`.
- 0x26DD80 appelle le gestionnaire 0x26D2D0(obj, hwnd, msg, wParam, lParam), qui commence par 0x285040 (saisie de
  texte, `GetKeyState`) puis aiguille sur le message (tables 0x26DC5C pour 1..8, 0x26DC94/0x26DC7C pour 0x24..0x10F) :

| Message | Code | Effet |
|---|---|---|
| WM_ACTIVATE (6) | 0x26D33E | `[obj+0x30] = (wParam == 0)` -> **inactif** = `u32 [0xF83060]` |
| WM_SIZE (5) | 0x26D34E | `[obj+0x34] = (wParam == SIZE_MINIMIZED)` -> **minimise** = `u32 [0xF83064]` |
| WM_CLOSE (0x10) | 0x26D64B | `[obj+0x38] = 1` -> `u32 [0xF83068]` |
| 0x8001 (WM_APP+1) | 0x26DA78 | `[obj+0x2C] = (wParam == 1)` -> `u32 [0xF8305C]` (emetteur non cherche ; overlay Steam suppose) |
| WM_KILLFOCUS (8) | 0x26D3CE | seulement si `u8 [0x176E2F7] != 0` (plein ecran exclusif suppose) : change de mode puis `ShowWindow(hwnd, SW_MINIMIZE)` |
| WM_SETFOCUS (7) | 0x26D51B | restaure le plein ecran |
| WM_ENTERSIZEMOVE / EXITSIZEMOVE | 0x26DBEB / 0x26DA89 | `[obj+0x20]` = 1 / 0 |

  Pas de traitement de WM_ACTIVATEAPP. Aucun sondage `GetForegroundWindow` pour le focus (le seul appel, 0xB07414,
  remplit une structure d'init - audio suppose).

```
0026d33e  33db            xor ebx, ebx
0026d340  4885f6          test rsi, rsi          ; wParam
0026d343  0f94c3          sete bl
0026d346  895f30          mov dword ptr [rdi + 0x30], ebx
```

### Mot d'etat global `u32 [0x177F528]` - confiance haute

Reconstruit a chaque image par la pompe de messages (0x26E483, appelee depuis 0x26CC7D) :

```
0026e525  8b0dfd0f5101    mov ecx, [0x177f528]
0026e52d  83c802          or eax, 2              ; bit 1 (0x02) = inactif   <- [0xF83060]
0026e530  83e1fd          and ecx, 0xfffffffd
0026e533  392d274bd100    cmp [0xf83060], ebp
0026e539  0f45c8          cmovne ecx, eax
0026e541  83c804          or eax, 4              ; bit 2 (0x04) = minimise  <- [0xF83064]
0026e544  392d1a4bd100    cmp [0xf83064], ebp
0026e55b  83c901          or ecx, 1              ; bit 0 (0x01) = fermeture <- [0xF83068]
```

Le bit 5 (0x20) vient de `[0xF8305C]` (0x26CCBA). Accesseur : `0x26CE80(masque)` = `[0x177F528] & masque`
(34 appelants).

## 2. Ce que fait la perte de focus

Le jeu **ne fige pas sa boucle principale** : il ouvre le menu pause et coupe les entrees.

### 2.1 Pause automatique - confiance moyenne

Predicat 0x9C6250 (renvoie 1 = "il faut mettre en pause") :

```
009c6254  mov ecx, 0x20 ; call 0x26ce80 ; jne -> 1       ; overlay
009c6262  390524f8ac00   cmp [0x1495a8c], eax(0)
009c6268  7520           jne 0x9c628a                    ; drapeau != 0 -> renvoie 0
009c626a  lea ecx,[rax+4]; call 0x26ce80 ; jne -> 1      ; minimise
009c6276  390510f8ac00   cmp [0x1495a8c], eax
009c627c  750c           jne 0x9c628a
009c627e  8d4802         lea ecx, [rax + 2]              ; inactif
009c6281  call 0x26ce80
009c6288  7507           jne 0x9c6291                    ; -> 1
```

Trois appelants : 0x8395FD et 0x93C2F4 le combinent avec `0x7F7EB0(0x13EADC0, 0xE)` (action 0xE = bouton
pause/START, voir 4.3) pour ouvrir le menu pause ; 0x828F29 abandonne son traitement tant que le predicat est vrai.
Le libelle "ouvre le menu pause" est deduit de ce couplage avec l'action 0xE (faible) ; le fait que le predicat
depende du focus est lu (moyenne).

### 2.2 Entrees coupees

| Site | Masque | Effet si le bit est mis |
|---|---|---|
| 0x277CF2 (`test byte [0x177F528], 0x26`) | inactif, minimise, overlay | clavier DirectInput non lu (0x277CD0) |
| 0x277EB2 (`and ebx, 0x26`) | idem | etat clavier/souris remis a zero (0x277FBE), souris appelee avec `actif = 0` (0x278FB0) |
| 0x2773F9 (`and ebp, 0x24`) | minimise, overlay | **XInput non lu** (0x2773B0) ; le bit inactif n'est PAS dans ce masque |
| 0x86C5DD (`0x26CE80(6)`) | inactif, minimise | les 4 structures pad du jeu (0x13FCEA0) remises a zero, **sauf si `[0x1495A8C] != 0`** (test en 0x86C549) |
| 0x86CA2D, 0x86CB10 (`0x26CE80(0x26)`) | les trois | curseur souris / appel 0x278290 (role non etabli) |
| 0x86A1E2 (`0x26CE80(6)`) | inactif, minimise | `[0x1774430] = 1` si `[0x13F88F8] != 0` (role non etabli ; coupure du son supposee, non verifiee) |
| 0x946142 (`0x26CE80(2)`) | inactif | `[0xF5CB58+0xC] = 0` (machine a etats non identifiee) |
| 0x24A2AE (`test byte [0x177F528], 4`) | minimise | saute un bloc de 0x24A250 (rendu suppose) |

Donc, fenetre non minimisee et sans focus : la manette est toujours lue par XInput, mais son etat est efface en
0x86C638 et le menu pause s'ouvre. Clavier et souris sont ignores.

### 2.3 Le drapeau `u32 [0x1495A8C]`

- C'est une **option utilisateur** : ecrite par l'applicateur de reglages (cas en 0x985E99 :
  `[0x1495A8C] = (menu[+0x28] == 0)`), relue par le menu (0x8AA2A6), et copiee dans le bloc de sauvegarde des
  reglages 0x1495A60..0x1495A94 -> 0x1495AE4.. (0x920BF5). Le libelle de l'option dans le menu n'a pas ete identifie.
- `!= 0` : pas de pause automatique sur inactif/minimise, et pas de remise a zero des pads.
- Lecteurs : 0x86C549, 0x86CB19, 0x9C6262, 0x9C6276, 0x8AA2A6. Section sans donnees dans le fichier (valeur initiale
  inconnue statiquement).

## 3. Patchs proposes (reversibles)

### Option A - donnee, la plus petite (recommandee pour un test)

| Adresse | Original | Nouveau |
|---|---|---|
| `u32 [0x1495A8C]` | valeur lue au moment du patch (a sauvegarder) | `01 00 00 00` |

Risques : le jeu peut la reecrire (passage par le menu des reglages) -> la reaffirmer periodiquement ; elle fait
partie du bloc de reglages, donc **elle peut etre persistee dans la sauvegarde systeme** si le jeu enregistre ses
reglages pendant le test. Restaurer la valeur d'origine en fin de session.

### Option B - code, sans toucher a l'option (2 octets)

| RVA | Instruction | Original | Nouveau | Effet |
|---|---|---|---|---|
| 0x9C6280 | `lea ecx, [rax+2]` (8D 48 **02**) | `02` | `00` | le predicat de pause ignore "inactif" (masque 0 -> jamais vrai) |
| 0x86C5DC | `lea ecx, [rbp+5]` (8D 4D **05**), rbp = 1 | `05` | `03` | masque 6 -> 4 : les pads ne sont effaces que si minimise |

Ne modifie ni le clavier ni la souris (toujours coupes sans focus, ce qui evite que la frappe de l'utilisateur dans
une autre fenetre parte dans le jeu).

### A eviter

Forcer le bit inactif a 0 a la source (0x26E52F `02`->`00`) reactiverait aussi clavier et souris sans focus : le
clavier DirectInput semble cree en `DISCL_BACKGROUND | DISCL_NONEXCLUSIVE` (`lea r8d, [rdi+0xa]` avant
`SetCooperativeLevel` en 0x277B84 ; valeur de rdi non verifiee), et le chemin souris appelle `ClipCursor` /
`SetCursorPos` (0x278F51, 0x279227, 0x2784F0) : l'utilisateur perdrait son curseur.

### Limites

- **Minimise** reste bloquant : XInput n'est plus lu (0x2773F9) et les pads sont effaces. En plein ecran exclusif,
  WM_KILLFOCUS minimise la fenetre (0x26D506). Utiliser le mode fenetre ou sans bordure.
- Overlay (bit 0x20) : toujours bloquant.

## 4. Lecture des entrees

### 4.1 Peripheriques - confiance haute

| API | Site | Usage |
|---|---|---|
| `XInputGetState` (XINPUT1_4 ordinal 2, IAT 0xC1B700) | 0x278D2F, **un seul appel** | manettes |
| `XInputSetState` (ordinal 3, IAT 0xC1B6F8) | 0x2775F0 | vibrations |
| `DirectInput8Create` (IAT 0xC1B000) | 0x277ADE | clavier : `GetDeviceState(0x100)` en 0x277D6F, table scancode -> indice de touche en 0xF815A0 (0xB9 entrees de 0xC octets) |
| `GetAsyncKeyState` (IAT 0xC1B5D0) | 0x277E09 | touches supplementaires (liste chainee `[0x179D878]`) |
| `GetKeyState` | 0x285040 | saisie de texte seulement (WM_KEYDOWN) |

Pas de Raw Input. Chaine par image : `0x86C310` (agregation) -> `0x277CD0` (clavier/souris) -> `0x2773B0` (pads).

### 4.2 Structures pad - confiance haute

**Brute (pile de 0x2773B0, 4 x 0x20 octets, remplie par 0x278D10(rcx = &indice XInput, rdx = sortie))** :

| Offset | Contenu |
|---|---|
| +0x00 | u32 connecte (1 si `XInputGetState` renvoie 0) |
| +0x04 / +0x08 | f32 stick gauche X / Y = `sThumb * 1/32768` ; **Y multiplie par -1/32768** (constantes 0xDBA6E0, 0xDBAA80) |
| +0x0C / +0x10 | f32 stick droit X / Y (meme convention) |
| +0x14 / +0x18 | f32 gachette gauche / droite = octet / 255 |
| +0x1C | u32 boutons, disposition du jeu (ci-dessous) |

Bits de boutons (lus en 0x278D48..0x278DDB ; bits de sticks/gachettes ajoutes par 0x276C80) :

| Bit | Source | Bit | Source |
|---|---|---|---|
| 0x0001 | croix gauche | 0x0100 | START |
| 0x0002 | croix droite | 0x0200 | BACK |
| 0x0004 | croix bas | 0x0400 | LB |
| 0x0008 | croix haut | 0x0800 | LT (seuil, 0x276F15) |
| 0x0010 | A | 0x1000 | L3 |
| 0x0020 | B | 0x2000 | RB |
| 0x0040 | X | 0x4000 | RT (seuil, 0x276F2F) |
| 0x0080 | Y | 0x8000 | R3 |
| 0x10000 / 0x20000 | stick G gauche / droite | 0x40000 / 0x80000 | stick G haut / bas |
| 0x100000..0x800000 | stick D (meme ordre) | | |

**Peripherique `0x177FD80 + i*0x80` (i = 0..3)**, mis a jour en 0x2774C3..0x277537 : +0x04 connecte, +0x08..+0x1C
six flottants (apres zone morte), +0x20 maintenu, +0x24 appuye (front), +0x28 relache, +0x2C appuye avec
repetition, +0x30 compteur de repetition. Si `brut.connecte == 0` ou masque 0x24 : tout est remis a zero.

**Jeu `0x13FCEA0 + pad*0x38`**, copie par 0x2780D0(dest, pad) depuis le peripherique designe par la table de
correspondance `[[0x17733D8] + 0xB8 + pad*4]` :

| Offset | Contenu |
|---|---|
| +0x00 / +0x04 / +0x08 / +0x0C | maintenu / appuye / relache / repetition |
| +0x10 / +0x14 / +0x18 / +0x1C | stick G X, Y, stick D X, Y |
| +0x20 / +0x24 | gachettes G, D |
| +0x28 | connecte |

0x86C310 recopie ce bloc vers `0x13FCF80` (meme disposition ; c'est **celui que lit le jeu**), puis vers `0x13FD060`
qui est efface si `[0x1029B10] & 0x200000` ou `[0x1029B14] & 0x20000000`.

Lecteurs recoupes de `0x13FCF80` (pad 0) : le controleur du joueur 0x523866 copie les 0x38 octets dans
`[ctrl+0x40..+0x78]` (ou les efface si les entrees sont bloquees : `[0x1029B80] & 0x80000000`, `[0x1029B10] &
0x200000`, `[0x1029B14] & 0x20000000`) ; les menus lisent `0x13FCF80/84/8C` via la classe 0x9BAxxx-0x9BCxxx.

Clavier cote jeu : jeux de bits a `0x13FD140` (maintenu) et suivants, 0xB9 touches, bit = `0x80000000 >> (i & 31)`
du mot `i >> 5`. Souris : `0x13FD2C8` (boutons maintenu/appuye/relache/repetition, position, molette).

### 4.3 Actions de jeu et bouton "interagir"

Gestionnaire d'actions `0x13EADC0` : quatre tableaux de 17 `u32` indexes par action - +0x00 maintenu (0x7F6EA0),
+0x44 appuye (0x7F7DE0), +0x88 (0x7F7DF0), +0xCC (0x7F7EB0). **La fonction qui les remplit n'a pas ete trouvee.**

Configuration manette (confiance moyenne) :

- `0xF55B60` : 18 masques de bouton par emplacement (statique) :
  `0x800, 0x400, 8, 1, 2, 4, 0x1000, 0x200, 0, 0x100, 0, 0x4000, 0x2000, 0x80, 0x40, 0x20, 0x10, 0x8000`.
- `0x1495B18` : 18 `u32` = action affectee a chaque emplacement (**table vivante**, lue par 0x7DB480 qui renvoie le
  masque d'une action).
- `0xF55BD0` : 3 presets de 18 actions (0x7E1310, 0x7EFF10). Preset 0 :
  `4, 5, 0xA, 0xC, 0xB, 0xD, 0x10, 0xF, 0xE, 0xE, 9, 6, 7, 0, 1, 2, 3, 8`.

Preset 0 croise avec les masques :

| Action | Bouton | Role suppose (disposition par defaut connue du jeu) |
|---|---|---|
| 0 | Y (0x80) | attaque lourde |
| 1 | X (0x40) | attaque legere |
| **2** | **B (0x20)** | **interagir / ramasser / ouvrir** |
| 3 | A (0x10) | saut |
| 4 | LT (0x800) | verrouillage |
| 5 | LB (0x400) | programme du Pod |
| 6 | RT (0x4000) | esquive |
| 7 | RB (0x2000) | tir du Pod |
| 8 | R3 (0x8000) | - |
| 0xA / 0xB / 0xC / 0xD | croix haut / droite / gauche / bas | raccourcis |
| 0xE | START (0x100) | pause - **recoupe** : c'est l'action testee par le code de pause (2.1) |
| 0xF | BACK (0x200) | - |
| 0x10 | L3 (0x1000) | - |

Seule l'action 0xE est recoupee par le code. Les autres libelles viennent de la disposition par defaut du jeu, pas
du desassemblage : **"action 2 = interagir" est une deduction** (aucun code de ramassage n'a ete relie a l'action 2).
Le preset actif du joueur n'est pas connu statiquement : lire `0x1495B18`.

Clavier : `0x7DB6C0(_, n)` (n = 0..0x17) = `0xF55680[ [0x1495B60 + 4*n] ]` = indice de touche. Les touches par
defaut (F / Entree) n'ont pas ete decodees.

### 4.4 Menus : valider / annuler - confiance haute

Objet `0xF72990`, initialise par 0x9BC760 :

```
009bc769  call 0x278080            ; -> jmp 0x11d240 = xor eax,eax ; ret  (toujours 0)
009bc772  lea ecx, [rax + 0x20]    ; ecx = 0x20
009bc775  lea eax, [rcx - 0x10]    ; eax = 0x10
009bc784  mov [rbx], eax           ; +0 masque VALIDER = 0x10 (A)
009bc78b  mov [rbx + 4], ecx       ; +4 masque ANNULER = 0x20 (B)
```

- Valider (0x9BAFF0, son `core_main_disicion`) : `[0x13FCF84 + pad*0x38] & [0xF72990]`, ou touches clavier fixes
  (`[0x13FD170] & 0x200000`, `[0x13FD184] & 0x400`), ou clic gauche (`[0xF72990+0x30] & 1`).
- Annuler (0x9BAE40, son `core_main_cancel`) : `... & [0xF72994]`, ou `[0x13FD180] & 0x4000`, ou clic droit.
- Navigation (0x9BB640) : masques `0x40008` haut, `0x80004` bas, `0x10001` gauche, `0x20002` droite (croix ou stick
  gauche), testes sur le maintenu `0x13FCF80`.

Attention : valider en menu (A, 0x10) et interagir en jeu (B, 0x20 suppose) sont **deux boutons differents**.

Piste non exploree : si `[0x1029B04] & 0x200`, ces fonctions lisent `[0xF72990+0x68]` (maintenu) et `+0x6C`
(appuye) a la place des vraies entrees (ecrits par 0x828F20). Origine du bit 0x200 non cherchee.

## 5. Conception du detour d'injection

### Site principal : 0x277438 (dans 0x2773B0)

```
00277432  488bd7          mov rdx, rdi          ; sortie brute du pad courant (0x20 octets, deja a zero)
00277435  488bcb          mov rcx, rbx          ; &indice XInput (table 0xF830CC)
00277438  e8d3180000      call 0x278d10         ; <- remplacer le rel32
0027743d  4883c720        add rdi, 0x20
00277445  4883ee01        sub rsi, 1            ; esi = 4 pour le pad 0, puis 3, 2, 1
```

Original : `E8 D3 18 00 00`. Nouveau : `E8 <rel32 vers la cave>` (cave a moins de 2 Go du module). Meme convention
d'appel, donc aucun octet a rejouer. rdi et esi sont non volatils et non modifies par 0x278D10 (qui n'empile que
rbx).

Bloc de controle ecrit par le client (dans la page de la cave) :
`+0x00 u32 enable`, `+0x04 u32 boutons`, `+0x08 u32 override_axes`, `+0x0C f32 LX, LY, RX, RY, LT, RT`.

```
cave:
    sub  rsp, 0x28
    mov  rax, 0x140278D10
    call rax                          ; lecture XInput d'origine (rdx = rdi)
    cmp  esi, 4                       ; pad 0 seulement
    jne  done
    lea  rax, [rip + ctl]
    cmp  dword [rax], 0               ; enable
    je   done
    mov  dword [rdi], 1               ; force "connecte" (sinon le peripherique est efface en 0x277557)
    mov  ecx, [rax + 4]
    or   [rdi + 0x1C], ecx            ; boutons : 0x20 = B, 0x10 = A, 1/2/4/8 = croix
    cmp  dword [rax + 8], 0
    je   done
    movups xmm0, [rax + 0x0C]         ; LX, LY, RX, RY
    movups [rdi + 4], xmm0
    mov  rcx, [rax + 0x1C]            ; LT, RT
    mov  [rdi + 0x14], rcx
done:
    add  rsp, 0x28
    ret
```

Avantages de ce niveau : 0x276C80 puis 0x2774D1..0x277525 calculent ensuite eux-memes zones mortes, bits de stick
(0x10000..), fronts appuye/relache et repetition. Un appui = mettre le bit pendant quelques images puis l'enlever
(le front "appuye" ne dure qu'une image ; le client ne peut pas se synchroniser a l'image pres, donc tenir ~100 ms).
Avancer : `LY = -1.0`.

Conditions pour que l'etat arrive au jeu sans focus : fenetre non minimisee (masque 0x24 en 0x2773F9), et pads non
effaces en 0x86C638 (patch de la section 3). Si l'on veut aussi tolerer le minimise : 0x2773FB `24` -> `20`
(`83 E5 24` -> `83 E5 20`) et 0x86C5DC `05` -> `01` (masque 0), non recommande sans essai.

### Site de repli : 0x86C345

Si la table de correspondance `[0x17733D8]` n'est pas valide sans manette physique, 0x2780D0 renvoie 0 sans rien
copier. Repli : detourner `0086c345 e886bda0ff call 0x2780d0` (rcx = 0x13FCEA0, edx = 0 ; eax ignore au retour) et
ecrire directement la structure jeu du pad 0. La cave doit alors calculer elle-meme appuye / relache / repetition a
partir du maintenu precedent, et poser les bits de stick.

## 6. A verifier en execution

1. `u32 [0x177F528]` : bit 0x02 passe bien a 1 a la perte de focus, 0x04 quand minimise ; `u32 [0xF83060]` idem.
2. `u32 [0x1495A8C]` : valeur par defaut, quelle option du menu la change, et si l'ecriture a 1 supprime la pause
   (sinon passer a l'option B). Verifier qu'elle n'est pas enregistree dans la sauvegarde systeme.
3. Le jeu continue-t-il vraiment a simuler sans focus une fois la pause evitee (aucun gel de boucle n'a ete vu
   statiquement, mais ce n'est pas une preuve) ; le son.
4. `[0x17733D8]` non nul et correspondance du pad 0 valide **sans manette branchee** (sinon site de repli).
   Table 0xF830CC (indices XInput) : `0, 0, 0, 0` dans le fichier, valeurs reelles a lire.
5. `u32 [0xF72990]` == 0x10 et `[0xF72994]` == 0x20.
6. `0x1495B18` : emplacement dont l'action vaut 2, et confirmer en jeu que ce bouton (B attendu) ramasse / ouvre.
7. Octets d'origine des sites avant tout patch (`E8 D3 18 00 00` en 0x277438, `8D 48 02` en 0x9C627E,
   `8D 4D 05` en 0x86C5DA), pour detecter une autre version ou un autre outil deja accroche.
8. Bascule automatique des invites clavier/manette quand un pad "apparait" : effet de bord possible, non etudie.
9. Thread : 0x2773B0 tourne dans le fil de la boucle de jeu ; ecrire le rel32 du `call` (4 octets) n'est pas atomique
   vis-a-vis de ce fil -> ecrire la cave d'abord, puis le rel32 en une seule ecriture, idealement jeu en pause.

## 7. Non trouve

- La fonction "ramasser l'objet au sol / ouvrir le coffre a portee" : pas identifiee, aucune piste sure.
- Le remplissage des tableaux d'actions de `0x13EADC0` (donc le lien exact masque de bouton -> action en jeu).
- Les touches clavier par defaut d'interaction.
