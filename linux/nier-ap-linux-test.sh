#!/usr/bin/env bash
# NieR:Automata Archipelago - Linux / Proton TEST helper.
# UNTESTED by the author (no Linux machine). Please report what happens: send the file nier-ap-linux-test.log.
#
# The client uses Windows memory functions, so it must run INSIDE the Proton container of the running game.
# This script does that with Steam's own "steam-runtime-launch-client".
#
# Before anything else:
#   1. Steam > NieR:Automata > Properties > Launch Options:   STEAM_COMPAT_LAUNCHER_SERVICE=proton %command%
#   2. Start the game and leave it running.
#
# Usage:
#   ./nier-ap-linux-test.sh diag                         show what the script finds (run this first)
#   ./nier-ap-linux-test.sh install Setup.Archipelago.exe   install the Windows Archipelago in the game's container (once)
#   ./nier-ap-linux-test.sh run [archipelago://name@host:port]   start the NieR:Automata client
set -u

APPID=524220
BUS="com.steampowered.App${APPID}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="${HERE}/nier-ap-linux-test.log"
EXE="${HERE}/NierAutomataAP.exe"

say() { printf '%s\n' "$*" | tee -a "$LOG"; }

steam_roots() {
    local r
    for r in "$HOME/.steam/steam" "$HOME/.steam/root" "$HOME/.local/share/Steam" \
             "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam"; do
        [ -d "$r/steamapps" ] && printf '%s\n' "$r"
    done
}

library_dirs() {
    local root vdf
    while IFS= read -r root; do
        printf '%s\n' "$root/steamapps"
        vdf="$root/steamapps/libraryfolders.vdf"
        [ -f "$vdf" ] && sed -n 's/.*"path"[[:space:]]*"\(.*\)".*/\1\/steamapps/p' "$vdf"
    done < <(steam_roots)
}

find_launch_client() {
    local lib rt c
    while IFS= read -r lib; do
        for rt in SteamLinuxRuntime_sniper SteamLinuxRuntime_soldier SteamLinuxRuntime; do
            c="$lib/common/$rt/pressure-vessel/bin/steam-runtime-launch-client"
            [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
        done
    done < <(library_dirs | sort -u)
    return 1
}

find_prefix() {
    local lib
    while IFS= read -r lib; do
        [ -d "$lib/compatdata/$APPID/pfx" ] && { printf '%s\n' "$lib/compatdata/$APPID/pfx"; return 0; }
    done < <(library_dirs | sort -u)
    return 1
}

in_game() {   # run a Windows program inside the game's container
    "$CLIENT" --bus-name="$BUS" -- wine "$@"
}

need_client() {
    CLIENT="$(find_launch_client)" || {
        say "ERROR: steam-runtime-launch-client not found (is the Steam Linux Runtime installed?)."
        exit 2
    }
}

need_game() {
    if ! "$CLIENT" --list 2>>"$LOG" | grep -q "$BUS"; then
        say "ERROR: the running game is not visible ($BUS)."
        say "  - Is NieR:Automata running?"
        say "  - Launch option must be exactly:  STEAM_COMPAT_LAUNCHER_SERVICE=proton %command%"
        say "  - Do not use sudo. Flatpak Steam and Steam Deck are reported as problematic."
        say "Visible containers:"
        "$CLIENT" --list 2>&1 | tee -a "$LOG"
        exit 3
    fi
}

cmd="${1:-diag}"
: > "$LOG"
say "== NieR:Automata AP Linux test - $cmd - $(date -u '+%Y-%m-%d %H:%M:%S UTC') =="
say "system: $(uname -srm)"
[ -r /etc/os-release ] && say "distro: $(. /etc/os-release && printf '%s' "${PRETTY_NAME:-unknown}")"
say "steam roots: $(steam_roots | tr '\n' ' ')"
if steam_roots | grep -q '/.var/app/com.valvesoftware.Steam/'; then
    say "WARNING: Flatpak Steam detected. This method is reported not to work with Flatpak Steam."
fi

case "$cmd" in
diag)
    need_client
    say "launch client: $CLIENT"
    PFX="$(find_prefix)" && say "game prefix: $PFX" || say "game prefix: NOT FOUND (has the game been started once?)"
    if [ -n "${PFX:-}" ]; then
        if [ -f "$PFX/drive_c/ProgramData/Archipelago/ArchipelagoLauncher.exe" ]; then
            say "Archipelago in the prefix: yes (C:\\ProgramData\\Archipelago)"
        else
            say "Archipelago in the prefix: no -> run:  $0 install /path/to/Setup.Archipelago.exe"
        fi
    fi
    [ -f "$EXE" ] && say "NierAutomataAP.exe: found" || say "NierAutomataAP.exe: MISSING next to this script"
    say "visible containers:"
    "$CLIENT" --list 2>&1 | tee -a "$LOG"
    need_game
    say "OK: the running game is visible. Next: install (once), then run."
    ;;
install)
    setup="${2:-}"
    [ -f "$setup" ] || { say "Usage: $0 install /path/to/Setup.Archipelago.exe  (download it from the Archipelago releases)"; exit 1; }
    need_client; need_game
    say "Installing Archipelago in the game's container. Keep the default folder (C:\\ProgramData\\Archipelago)."
    in_game "$(readlink -f "$setup")" 2>&1 | tee -a "$LOG"
    ;;
run)
    [ -f "$EXE" ] || { say "ERROR: NierAutomataAP.exe must be next to this script."; exit 1; }
    need_client; need_game
    shift
    say "Starting the NieR:Automata client in the game's container..."
    say "What to look for in the client window: 'Game detected (v1.04)'."
    in_game "$EXE" "$@" 2>&1 | tee -a "$LOG"
    ;;
*)
    say "Usage: $0 diag | install Setup.Archipelago.exe | run [archipelago://name@host:port]"
    exit 1
    ;;
esac
say "== done. Please send this file back: $LOG =="
