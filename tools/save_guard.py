"""Garde-fou : compare la sauvegarde du joueur a la copie de reference et la restaure si elle a change.
    python tools/save_guard.py [check|restore]"""
import hashlib
import os
import shutil
import sys

D = os.path.expandvars(r"%USERPROFILE%\Documents\My Games\NieR_Automata")
B = os.path.expandvars(r"%LOCALAPPDATA%\NierAutomataAP\backups\manuel_avant_fin_E")
h = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
changed = [f for f in ("SlotData_0.dat", "GameData.dat") if h(os.path.join(D, f)) != h(os.path.join(B, f))]
if changed and (len(sys.argv) < 2 or sys.argv[1] == "restore"):
    for f in changed:
        shutil.copy2(os.path.join(B, f), os.path.join(D, f))
    print("SAUVEGARDE MODIFIEE -> restauree :", changed)
else:
    print("sauvegarde modifiee :" if changed else "sauvegarde intacte", changed or "")
