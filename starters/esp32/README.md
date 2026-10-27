# picodev-starter-esp32

Projet de départ Picodev CTF pour ESP-IDF 5.5 : il dit bonjour avec le nom de la puce, puis compte les secondes. Cibles : `esp32`, `esp32s3`, `esp32c3`.

## Ouvrir

Docker et VS Code avec l'extension **Dev Containers** ; « Reopen in Container ». Image : `ghcr.io/picodev-sas/dev-esp32:2026.2` (2,2 Go). Extensions : ESP-IDF, clangd, Serial Monitor, Picodev Lab. L'extension ESP-IDF trouve ESP-IDF par `IDF_PATH` et `IDF_TOOLS_PATH` de l'image : rien à installer.

## Compiler, essayer dans QEMU

```sh
idf.py set-target esp32 build     # ou esp32s3, esp32c3
idf.py qemu monitor               # le firmware tourne dans le QEMU d'Espressif (Ctrl+] pour sortir)
```

## Envoyer au banc du CTF

Les bancs ESP32 du CTF simulent l'**ESP32-DevKitC** (puce `esp32`) avec le QEMU d'Espressif. Ouvrez le défi avec « utiliser ma machine » : la page donne une commande `picodev login <code>` (8 caractères, valable 15 minutes, une seule fois). Lancez-la dans le terminal du conteneur, puis tâche **Picodev: send to the bench**, ou :

```sh
picodev send
```

`picodev` compile pour `esp32` dans `build/`, fusionne bootloader, table des partitions et application en une image flash au format Intel HEX (`build/merged.hex`, `idf.py merge-bin -f hex`), puis l'envoie avec les sources à la page du défi par l'agent de la partie. Staging : `export PICODEV_SITE_AUTH=utilisateur:motdepasse` avant. Dans un dossier vide, `picodev login` y dépose aussi le projet du défi (`PICODEV_LANG=en` pour l'anglais). La partie est gardée dans `~/.config/picodev/game`, hors du projet et lisible par vous seul, puis effacée quand elle se termine. Le bloc `export PICODEV_SESSION=… PICODEV_AGENT_TOKEN=…` de « Autre méthode » marche aussi.

## Flasher une vraie carte : RFC2217

Le conteneur ne voit pas l'USB sous Windows et macOS : le port série passe par le réseau. Sur l'**hôte**, avec Python :

```sh
pipx install esptool==4.12.0
esp_rfc2217_server.py -p 4000 /dev/ttyUSB0      # Windows : COM3 ; macOS : /dev/cu.usbserial-…
```

Dans le **conteneur** (tâche « Flash and monitor ») :

```sh
idf.py -p 'rfc2217://host.docker.internal:4000?ign_set_control' flash monitor
```

`esp_rfc2217_server` écoute sur toutes les interfaces, sans authentification : à lancer sur un réseau de confiance seulement, et à arrêter après usage. Sous Linux, un pare-feu peut bloquer le conteneur vers l'hôte ; plus simple alors : passer la carte au conteneur (`"runArgs": ["--add-host=host.docker.internal:host-gateway", "--device=/dev/ttyUSB0"]`) et `idf.py -p /dev/ttyUSB0 flash monitor`.

Licence : MIT (`LICENSE`).
