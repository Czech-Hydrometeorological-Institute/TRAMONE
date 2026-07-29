#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filter_sampling_volume.py

Výpočet doby odběru a odebraného objemu vzdušiny pro jednotlivé filtry
(vzorky) monitorovacího systému TRAMONE na základě analýzy provozního
(systémového) logu.

Log obsahuje mj. tyto typy záznamů (pole oddělená znakem "|"):

    <UTC timestamp>|<stanice>|filter|<vzorkovač>|REPLACED|OK
        - okamžik výměny filtru na daném vzorkovači (0 nebo 1) dané
          stanice (např. "3A", "4B")

    <UTC timestamp>|<stanice>|response|STATE|<stav0><stav1>|OK
        - pravidelné hlášení klientské stanice o provozním stavu obou
          jejích vzorkovačů; <stav0> a <stav1> je znak '1' (vzorkovač
          v chodu) nebo '0' (v klidu) pro vzorkovač 0, resp. 1

Skript pro každou dvojici (stanice, vzorkovač) projde záznamy o výměně
filtru a mezi každými dvěma po sobě jdoucími výměnami (tj. za dobu
expozice jednoho konkrétního filtru) sečte časové úseky, ve kterých byl
vzorkovač dle hlášeného stavu v chodu. Výsledná doba se vynásobí
konstantním jednotkovým průtokem vzorkovače a určí tak odebraný objem
vzdušiny pro daný filtr. V případě použitého Sven Leckel LVS6 se jednalo
o 2,3 m3.h-1."

Log se v provozu pravidelně zálohuje do souborů s časovým razítkem v
názvu (log_YYYYMMDD_HHMMSS.txt) a průběžně pokračuje v log.txt. Skript
je proto potřeba spustit nad všemi soubory patřícími k dané stanici v
chronologickém pořadí (viz --logdir níže).

Poznámka ke kvalitě dat: pokud klientská stanice restartuje (v logu se
objeví řádek "...response|STATE|REBOOT|OK"), stavový řetězec pro daný
okamžik nelze interpretovat jako '0'/'1' a je skriptem ignorován -
stejně jako v provozním skriptu networking.py, ze kterého tento nástroj
logiku přebírá (funkce sampling_time()). Pokud stanice restartuje
uprostřed běžícího odběru, může být přerušovaná doba chodu podhodnocena;
pro kontrolu doporučujeme případy s REBOOT v daném intervalu ručně
zkontrolovat (skript je do výstupu volitelně vypisuje, viz --warn-reboot).

Použití:
    python3 filter_sampling_volume.py log1.txt log2.txt ... [--flow 2.3] [--out vysledek.csv]
    python3 filter_sampling_volume.py --logdir /cesta/k/TRAMONE [--flow 2.3] [--out vysledek.csv]

Autor: doplněno jako samostatný nástroj pro zpracování dat k projektu
TAČR SS701003 (TRAMONE) na základě algoritmu z networking.py.
"""

import argparse
import csv
import glob
import os
import sys
from datetime import datetime, timezone

TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_timestamp(ts_str):
    return datetime.strptime(ts_str.strip(), TS_FORMAT).replace(tzinfo=timezone.utc)


def collect_log_files(logdir):
    """Vrátí soubory log_YYYYMMDD_HHMMSS.txt seřazené chronologicky podle
    jména a na konci aktuální log.txt (pokud existuje)."""
    rotated = sorted(glob.glob(os.path.join(logdir, "log_*.txt")))
    current = os.path.join(logdir, "log.txt")
    files = list(rotated)
    if os.path.isfile(current):
        files.append(current)
    return files


def read_lines(paths):
    lines = []
    for path in paths:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines.extend(f.readlines())
    return lines


def list_sites(lines):
    sites = set()
    for line in lines:
        if "|filter|" in line and "|REPLACED|OK" in line:
            parts = line.rstrip("\n").split("|")
            if len(parts) >= 2:
                sites.add(parts[1])
    return sorted(sites)


def filter_replacement_times(lines, site, sampler):
    """Časy výměn filtru (REPLACED) pro danou stanici a vzorkovač, vzestupně."""
    marker = f"|{site}|filter|{sampler}|REPLACED|OK"
    times = []
    for line in lines:
        if marker in line:
            try:
                times.append(parse_timestamp(line.split("|", 1)[0]))
            except ValueError:
                continue
    times.sort()
    return times


def running_seconds(lines, site, sampler, t_start, t_end, warn_reboot=False):
    """Součet doby (s), kdy byl vzorkovač 'sampler' na stanici 'site' dle
    hlášení STATE v chodu, v intervalu <t_start, t_end). t_end=None značí
    interval do konce dostupných dat (filtr dosud nebyl vyměněn)."""
    marker = f"|{site}|response|STATE|"
    total = 0.0
    running_since = None
    reboots_in_interval = 0
    last_ts = t_start

    for line in lines:
        if marker not in line:
            continue
        try:
            ts_str, rest = line.rstrip("\n").split("|", 1)
            ts = parse_timestamp(ts_str)
        except ValueError:
            continue
        if ts < t_start:
            continue
        if t_end is not None and ts >= t_end:
            break

        state_field = rest.split("STATE|", 1)[1]
        state_str = state_field.split("|", 1)[0]
        last_ts = ts

        if state_str == "REBOOT":
            reboots_in_interval += 1
            continue
        if len(state_str) <= sampler:
            continue

        state_char = state_str[sampler]
        if state_char == "1" and running_since is None:
            running_since = ts
        elif state_char == "0" and running_since is not None:
            total += (ts - running_since).total_seconds()
            running_since = None

    if running_since is not None:
        end_ts = t_end if t_end is not None else last_ts
        total += (end_ts - running_since).total_seconds()

    if warn_reboot and reboots_in_interval:
        print(
            f"  POZOR: {reboots_in_interval}x REBOOT stanice {site} v intervalu "
            f"{t_start.strftime(TS_FORMAT)} - "
            f"{t_end.strftime(TS_FORMAT) if t_end else '(dosud)'}; "
            f"doba chodu může být podhodnocena.",
            file=sys.stderr,
        )

    return total


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("logs", nargs="*", help="Cesta k log souborům TRAMONE v chronologickém pořadí")
    ap.add_argument("--logdir", default=None,
                     help="Alternativně: adresář TRAMONE, ze kterého se automaticky "
                          "seberou a chronologicky seřadí log_*.txt a log.txt")
    ap.add_argument("--sites", nargs="*", default=None,
                     help="Omezit na konkrétní stanice, např. 3A 3B 4A 4B "
                          "(výchozí: zjistit automaticky ze souboru)")
    ap.add_argument("--flow", type=float, default=2.3,
                     help="Jednotkový průtok vzorkovače v m3/h (výchozí 2,3 - Sven Leckel LVS6)")
    ap.add_argument("--out", default=None,
                     help="Výstupní CSV soubor (výchozí: výpis na stdout)")
    ap.add_argument("--warn-reboot", action="store_true",
                     help="Vypisovat upozornění na REBOOT v log souboru zasahující do intervalu odběru")
    args = ap.parse_args()

    if args.logdir:
        paths = collect_log_files(args.logdir)
        if not paths:
            sys.exit(f"V adresáři {args.logdir} nebyly nalezeny žádné log_*.txt ani log.txt.")
    elif args.logs:
        paths = args.logs
    else:
        ap.error("je nutné zadat buď seznam log souborů, nebo --logdir")

    lines = read_lines(paths)
    sites = args.sites if args.sites else list_sites(lines)
    if not sites:
        sys.exit("V logu nebyl nalezen žádný záznam o výměně filtru (REPLACED).")

    rows = []
    for site in sites:
        for sampler in (0, 1):
            replacements = filter_replacement_times(lines, site, sampler)
            if not replacements:
                continue
            for i, t_start in enumerate(replacements):
                t_end = replacements[i + 1] if i + 1 < len(replacements) else None
                seconds = running_seconds(lines, site, sampler, t_start, t_end, args.warn_reboot)
                hours = seconds / 3600.0
                volume_m3 = hours * args.flow
                rows.append({
                    "site": site,
                    "sampler": sampler,
                    "filter_from_utc": t_start.strftime(TS_FORMAT),
                    "filter_to_utc": t_end.strftime(TS_FORMAT) if t_end else "(dosud nevyměněn)",
                    "sampling_hours": round(hours, 3),
                    "sampled_volume_m3": round(volume_m3, 2),
                })

    fieldnames = ["site", "sampler", "filter_from_utc", "filter_to_utc",
                  "sampling_hours", "sampled_volume_m3"]

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"Uloženo {len(rows)} záznamů (po jednom na filtr) do {args.out}")
    else:
        w = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
