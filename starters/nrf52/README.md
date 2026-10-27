# picodev-starter-nrf52

Projet de départ Picodev CTF pour Zephyr sur la carte **nRF52840 DK** (`nrf52840dk/nrf52840`) : un central BLE minimal. Il scanne (sans se connecter) et écrit chaque annonce reçue sur l'UART de la console (`uart0`, port COM virtuel du J-Link, 115200 bauds) :

```
adv 12:34:56:78:9A:BC (random) rssi -52 type 0 name "Balise" data 0201060709...
```

Adresse, RSSI, type d'annonce, nom s'il y en a un, données d'annonce brutes en hexadécimal. C'est le point de départ du défi « Balise ». Quatre fichiers : `CMakeLists.txt`, `prj.conf` (BLE central, sans appairage), `src/main.c`, `boards/nrf52840dk_nrf52840.overlay` (l'UART de la console).

## Ouvrir

Docker et VS Code avec l'extension **Dev Containers** ; « Reopen in Container ». Image : `ghcr.io/picodev-sas/dev-nrf52:2026.2` (1,8 Go). Extensions : nRF Connect for VS Code, Cortex-Debug, clangd, Serial Monitor, Picodev Lab.

## Compiler

Avec Zephyr (les mêmes versions que le service de compilation Picodev ; le binaire ne diffère que par le préfixe des noms de fichiers des assertions, `WEST_TOPDIR/zephyr/` au lieu de `ZEPHYR_BASE/`) :

```sh
west build -b nrf52840dk/nrf52840 -d build app
```

Avec le nRF Connect SDK (même Zephyr 4.4.2, plus les bibliothèques de Nordic) :

```sh
. /opt/ncs/activate
west build -b nrf52840dk/nrf52840 -d build-ncs app
```

`picodev build app` fait la même chose que la première commande.

## Envoyer au banc du CTF

Ouvrez le défi avec « utiliser ma machine » : la page donne une commande `picodev login <code>` (8 caractères, valable 15 minutes, une seule fois). Lancez-la dans le terminal du conteneur, puis tâche **Picodev: send to the bench**, ou :

```sh
picodev send app
```

`picodev` compile avec `west build`, puis envoie le HEX (4 Mio au plus pour le banc radio nRF52) et les sources de `app/` à la page du défi par l'agent de la partie. Staging : `export PICODEV_SITE_AUTH=utilisateur:motdepasse` avant. Dans un dossier vide, `picodev login` y dépose aussi le projet du défi (`PICODEV_LANG=en` pour l'anglais). La partie est gardée dans `~/.config/picodev/game`, hors du projet et lisible par vous seul, puis effacée quand elle se termine. Le bloc `export PICODEV_SESSION=… PICODEV_AGENT_TOKEN=…` de « Autre méthode » marche aussi.

## Flasher, déboguer

- **Linux** : passez la carte au conteneur (`--device=/dev/bus/usb`, `--device=/dev/ttyACM0` dans `runArgs`), puis `west flash -d build --runner openocd` (OpenOCD parle au J-Link de la DK, sans logiciel SEGGER). Débogage : « OpenOCD (USB) » dans `launch.json`.
- **Windows, macOS** : copiez `build/zephyr/zephyr.hex` sur le disque `JLINK` que la DK monte sur l'hôte ; pour déboguer, un serveur GDB sur l'hôte (port 3333) et « GDB server on the host ».
- **nrfutil et J-Link** ne sont pas dans l'image (leurs licences interdisent la redistribution) : `picodev-install-nrfutil`, et `picodev-install-jlink <JLink_Linux_….deb>` après téléchargement sur segger.com.

Licence : MIT (`LICENSE`).
