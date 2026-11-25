# TRAMONE

Software for an air-mass-trajectory-driven paired sampling network for atmospheric aerosol
source apportionment. Developed within the TAČR project SS07010003 "Monitorovací síť řízená
trajektoriemi částic" (Český hydrometeorologický ústav).

Instead of relying on wind direction measured locally at the monitoring stations, the system
computes forward trajectories of virtual air-mass particles across the whole of the Czech
Republic (from a 3D-interpolated wind field) and switches on a pair of samplers — one upwind,
one downwind of a source area — only while a trajectory actually connects both stations through
the source. This removes the need for continuous sampling and, unlike conventional monitoring,
makes the paired concentration difference independent of dispersion conditions (mixing layer
height, ventilation index, wind speed).

## Repository layout

```
server/                     Raspberry Pi control system (runs continuously)
  tramone_main.sh              main control loop: wind-field gridding and trajectory
                                computation in GRASS GIS, sampler on/off decisions, map
                                snapshots, filter/volume bookkeeping
  networking.py                background service: downloads current wind observations over
                                FTP (via the GSM modem's AT+FTP commands), converts them with
                                wind_preparation.R, and handles MQTT communication with the
                                client stations
  wind_preparation.R           reformats/transforms downloaded wind observations (polar ->
                                vector components) for gridding by tramone_main.sh
  tramone.cfg                  runtime configuration (GRASS/mapset names, serial port, MQTT
                                broker, FTP sources) — see "Configuration" below
  systemd/
    tramone_main.service         user service unit for tramone_main.sh
    tramone_networking.service   user service unit for networking.py (depends on
                                  tramone_main.service)
  meteo_sites.txt               example climatological-station coordinate table used for wind
                                 gridding
  sampling_sites.txt            example paired-station coordinate table (JTSK)
  sampling_sites_jtsk.txt       example paired-station coordinate table (JTSK, alternate format)

client/
  SIM800L13_4A/
    SIM800L13_4A.ino          Arduino Nano firmware for a client station: GSM/MQTT link to the
                              server, sampler control (Sven Leckel LVS6, via button-press
                              emulation), station heating control, diagnostics reporting

data/                        example result tables (elemental/ionic concentrations)

docs/                        methodology (PDF, Czech original and English translation)

vyhodnocení/                 standalone data-processing tools (Czech), e.g. computing
                              per-filter sampling duration/volume from the server log
                              — see vyhodnocení/README.md

LICENSE                      GNU GPLv3
```

Both server scripts and the client firmware are the three pieces required to run the system;
everything else (GRASS GIS project, wind grids, sampling logs, images) is runtime state
generated on the device and is intentionally not versioned here.

## Server setup

Requirements: Raspberry Pi (4B+ for a single region; Pi 5 recommended for country-wide
gridding), Debian/Raspberry Pi OS with a desktop session (for trajectory visualization), GRASS
GIS, R, Python 3, a GSM HAT (tested with SIM7070G) on `/dev/ttyAMA0`.

1. Copy `server/` to `/home/pi/TRAMONE` on the device.
2. Set up the GRASS GIS location/mapset referenced by `tramone.cfg` (`grassdb`, `loc_jtsk`,
   `mapset`) with the base map, DEM and sampling-site vector layers for your deployment.
3. Edit `tramone.cfg` (see below) with the real FTP and MQTT connection details for your
   deployment.
4. Install the service units:
   ```bash
   mkdir -p ~/.config/systemd/user
   cp server/systemd/*.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now tramone_main.service tramone_networking.service
   ```
   `tramone_main.service` must come up first; `tramone_networking.service` depends on it.

## Client setup

Flash `client/SIM800L13_4A/SIM800L13_4A.ino` to the Arduino Nano of each client station via the
Arduino IDE. Each station needs its own build with its own MQTT topic/station identifier (see
the `#define`s at the top of the sketch) and the mobile APN of the SIM card in use.

## Configuration

`server/tramone.cfg` is committed with **placeholder** values only:

```
FTP_SERV="ftp.example.org"
FTP_USER="tramone_user"
FTP_PASS="changeme"

FTP_AIM_SERV="aim.example.org"
FTP_AIM_USER="tramone_aim_user"
FTP_AIM_PASS="changeme"
```

Replace these (and `MQTT_BROKER`/`MQTT_PORT` if not using the public default broker) with your
actual credentials before deployment. Do not commit real credentials back to this repository —
`networking.py` reads all of them from this file at startup, none are hard-coded in the scripts.

`meteo_sites.txt`, `sampling_sites.txt` and `sampling_sites_jtsk.txt` are examples from one
project region; regenerate them for each new deployment (station/site coordinates are
region-specific).

## Methodology

The methodology (TAČR SS07010003 result type NmetS) describes the concept, system operation,
installation, station siting, campaign design, data evaluation and the verification of the
method in four test deployments (2024–2026):

- [Metodika monitoringu atmosférického aerosolu řízeného trajektoriemi částic (CZ, PDF)](docs/TRAMONE_metodika_CZ.pdf) – original
- [Methodology for Trajectory-Driven Monitoring of Atmospheric Aerosol (EN, PDF)](docs/TRAMONE_methodology_EN.pdf) – English translation; the Czech original is authoritative

## Background

Method, validation and results from four test deployments (2024–2026) are described in the
methodology above and in detail in the project's final report (Souhrnná výzkumná zpráva
z monitoringu atmosférického aerosolu řízeného trajektoriemi částic, ČHMÚ, TAČR SS07010003).
