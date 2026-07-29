# vyhodnocení

Samostatné nástroje pro zpracování dat naměřených systémem TRAMONE, doplňkové k
`server/` a `client/` (tj. k software potřebnému pro samotný provoz monitorovací sítě).

## filter_sampling_volume.py

Spočítá dobu odběru a odebraný objem vzdušiny pro jednotlivé filtry (vzorky) na
základě analýzy provozního (systémového) logu serveru:

> Množství odebrané vzdušiny je nutno pro jednotlivé vzorky zjistit analýzou
> systémového logu, který zahrnuje informaci o času výměny filtrů v jednotlivých
> vzorkovačích a provozním stavu vzorkovačů (vyberou se pouze období, ve kterých byl
> konkrétní vzorkovač v době expozice příslušného filtru v chodu a vynásobí se
> konstantním jednotkovým průtokem vzorkovače (v případě použitého Sven Leckel LVS6
> se jednalo o 2,3 m³·h⁻¹).

### Co skript používá z logu

Server (`server/networking.py`) zapisuje do logu mj. tyto typy řádků (pole oddělená
znakem `|`):

```
<UTC timestamp>|<stanice>|filter|<vzorkovač>|REPLACED|OK
    – okamžik výměny filtru na daném vzorkovači (0 nebo 1) dané stanice, např. "3A"

<UTC timestamp>|<stanice>|response|STATE|<stav0><stav1>|OK
    – pravidelné hlášení klientské stanice o provozním stavu obou jejích
      vzorkovačů; <stav0>/<stav1> je '1' (v chodu) nebo '0' (v klidu)
```

Pro každou dvojici (stanice, vzorkovač) skript projde záznamy o výměně filtru a mezi
každými dvěma po sobě jdoucími výměnami (= doba expozice jednoho filtru) sečte
úseky, kdy byl vzorkovač dle hlášeného stavu v chodu. Výslednou dobu vynásobí
zadaným jednotkovým průtokem a určí tak odebraný objem pro daný filtr.

Logika sčítání běhu vychází z funkce `sampling_time()` v `server/networking.py`,
kterou server sám používá k průběžnému hlášení aktuální doby odběru přes MQTT.
Skript byl proti reálnému provoznímu logu ověřen — pro testovaný filtr vyšla stejná
hodnota (na tři desetinná místa), jakou si server sám průběžně publikoval do logu
(řádky `SAMPLING`) těsně před výměnou filtru.

### Použití

```bash
# explicitní seznam log souborů, v chronologickém pořadí
python3 filter_sampling_volume.py log_20260629_021106.txt log.txt

# nebo automatické posbírání a seřazení log_*.txt + log.txt z daného adresáře
python3 filter_sampling_volume.py --logdir /home/pi/TRAMONE

# jednotkový průtok jiného vzorkovače, výstup do CSV
python3 filter_sampling_volume.py --logdir /home/pi/TRAMONE --flow 1.0 --out vysledek.csv

# jen vybrané stanice, s upozorněním na REBOOT v logu
python3 filter_sampling_volume.py --logdir /home/pi/TRAMONE --sites 3A 3B --warn-reboot
```

Výstup (CSV, jeden řádek na filtr):

```
site,sampler,filter_from_utc,filter_to_utc,sampling_hours,sampled_volume_m3
3A,0,2026-06-23 04:09:45,2026-07-03 07:18:26,23.526,54.11
3A,1,2026-06-23 04:08:37,2026-07-03 07:18:28,67.372,154.96
```

`filter_to_utc` u dosud nevyměněného filtru obsahuje `(dosud nevyměněn)` a doba se
počítá do konce dostupných dat v logu.

### Poznámka ke kvalitě dat

Pokud klientská stanice restartuje, objeví se v logu řádek
`...response|STATE|REBOOT|OK` — stavový řetězec pro daný okamžik nelze
interpretovat jako `0`/`1` a skript jej ignoruje (stejně jako živý provozní
skript `networking.py`). Pokud stanice restartuje uprostřed běžícího odběru, může
být doba chodu mírně podhodnocená; s `--warn-reboot` skript takové případy vypíše
na stderr k ruční kontrole.

Log soubory se v provozu pravidelně zálohují do souborů s časovým razítkem v názvu
(`log_YYYYMMDD_HHMMSS.txt`) a průběžně pokračují v `log.txt`. Pro filtr, jehož
expozice přesahuje jednu zálohu, je proto nutné skriptu předat všechny relevantní
soubory najednou (nebo použít `--logdir`).
