NieR:Automata for Archipelago - Linux / Proton TEST package (v0.3.2)

STATUS: UNTESTED. The author has no Linux machine. This package exists so that Linux players can try it
and report back. Nothing here changes your game files or your save.

Why a special package: the client reads and writes the running game's memory with Windows functions, so it
must run inside the same Proton container as the game. A native Linux Archipelago, or a separate Wine
prefix (protontricks-launch), cannot see the game's memory.

Steps
1. Steam > NieR:Automata > Properties > Launch Options, put exactly:
       STEAM_COMPAT_LAUNCHER_SERVICE=proton %command%
2. Start NieR:Automata and leave it running (window mode is easier).
3. In a terminal, in this folder (no sudo):
       chmod +x nier-ap-linux-test.sh
       ./nier-ap-linux-test.sh diag
   It must end with "OK: the running game is visible".
4. Once: download "Setup.Archipelago.x.y.z.exe" (Windows installer, 0.6.8 or newer) from the Archipelago
   releases, then:
       ./nier-ap-linux-test.sh install /path/to/Setup.Archipelago.x.y.z.exe
   Keep the default install folder.
5. Start the client:
       ./nier-ap-linux-test.sh run
   or with your room:  ./nier-ap-linux-test.sh run archipelago://YourName@host:port

What to report (please send the file nier-ap-linux-test.log)
- your distribution, and whether Steam is native, Flatpak or a Steam Deck
- the Proton version used for the game
- does the client window open? does it show "Game detected (v1.04)"?
- after connecting: do you receive an item in game, and does a check get sent?

Known risks: Flatpak Steam and Steam Deck are reported as problematic for this method.
