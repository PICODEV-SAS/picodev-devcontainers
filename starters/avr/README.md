# picodev-starter-avr

Projet de départ Picodev CTF pour l'Arduino Nano et l'Uno : un sketch qui fait clignoter la LED et dit bonjour sur le port série (115200 bauds).

## Ouvrir

Il faut Docker et VS Code avec l'extension **Dev Containers**. Ouvrez ce dossier, puis « Reopen in Container » : VS Code télécharge l'image `ghcr.io/picodev-sas/dev-avr:2026.2` (0,4 Go) et installe les extensions (clangd, Serial Monitor, Picodev Lab).

Sans Dev Containers, en Remote-SSH : voir le `README.adoc` de https://github.com/PICODEV-SAS/picodev-devcontainers.

## Compiler

Tâche **Build** (Ctrl+Maj+B), ou dans le terminal :

```sh
arduino-cli compile --build-path build blink                         # Nano
arduino-cli compile --build-path build --fqbn arduino:avr:uno blink  # Uno
```

Le programme est dans `build/blink.ino.hex`. `picodev build blink` fait la même chose.

## Envoyer au banc du CTF

Ouvrez le défi avec « utiliser ma machine » : la page donne une commande `picodev login <code>` (8 caractères, valable 15 minutes, une seule fois). Lancez-la dans le terminal du conteneur, puis tâche **Picodev: send to the bench**, ou :

```sh
picodev send blink
```

`picodev` compile, puis envoie le HEX et le sketch à la page du défi par l'agent de la partie (MCP). La page le charge et, pendant un tour sur un banc, le banc le reçoit. Le site de staging est fermé par un mot de passe : `export PICODEV_SITE_AUTH=utilisateur:motdepasse` avant. Dans un dossier vide, `picodev login` y dépose aussi le projet du défi (`PICODEV_LANG=en` pour l'anglais). La partie est gardée dans `~/.config/picodev/game`, hors du projet et lisible par vous seul, puis effacée quand elle se termine. Le bloc `export PICODEV_SESSION=… PICODEV_AGENT_TOKEN=…` de « Autre méthode » marche aussi. Le mot de passe du site reste dans l'environnement. Autre site : `PICODEV_URL`.

## Flasher une vraie carte

- **Linux** : décommentez `runArgs` dans `.devcontainer/devcontainer.json` avec le port de la carte (`/dev/ttyUSB0` ou `/dev/ttyACM0`), reconstruisez le conteneur, puis tâche **Upload (USB)**.
- **Windows, macOS** : le conteneur ne voit pas l'USB. Compilez dans le conteneur, puis flashez depuis l'hôte avec `arduino-cli upload --input-dir build -p COM3 blink` (arduino-cli installé sur l'hôte), ou envoyez au banc.

Licence : MIT (`LICENSE`).
