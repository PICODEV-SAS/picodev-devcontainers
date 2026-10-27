# picodev-starter-stm32

Projet de départ Picodev CTF pour STM32 avec la HAL de ST et CMake : il fait clignoter la LED utilisateur et dit bonjour sur le port COM virtuel du ST-LINK (115200 bauds). Cartes : **Nucleo-F446RE** et **Nucleo-G071RB**.

## Ouvrir

Docker et VS Code avec l'extension **Dev Containers** ; « Reopen in Container ». Image : `ghcr.io/picodev-sas/dev-stm32:2026.2` (0,6 Go). Extensions : STM32CubeIDE for VS Code, Cortex-Debug, clangd, Serial Monitor, Picodev Lab.

## Compiler

```sh
cmake --preset nucleo-f446re && cmake --build --preset nucleo-f446re
cmake --preset nucleo-g071rb && cmake --build --preset nucleo-g071rb
```

Sorties : `build/<carte>/starter.elf`, `.hex`, `.bin`. CMSIS et la HAL viennent de l'image (`STM32CUBE_PATH`, `CMSIS_PATH`) ; `boards/<carte>/` contient la configuration de la HAL, le script de liens et les broches.

## Envoyer au banc du CTF

Les bancs STM32 du CTF simulent la **Nucleo-G071RB** (console : USART2, 115200 bauds, comme ici). Ouvrez le défi avec « utiliser ma machine » : la page donne une commande `picodev login <code>` (8 caractères, valable 15 minutes, une seule fois). Lancez-la dans le terminal du conteneur, puis tâche **Picodev: send to the bench**, ou :

```sh
picodev send
```

`picodev` compile le preset `nucleo-g071rb` (ou lance `make` dans `src/` quand `src/` a son `Makefile`, comme les projets HAL des défis), puis envoie `build/nucleo-g071rb/starter.hex` et les sources de `src/` à la page du défi par l'agent de la partie. Staging : `export PICODEV_SITE_AUTH=utilisateur:motdepasse` avant. Dans un dossier vide, `picodev login` y dépose aussi le projet du défi (`PICODEV_LANG=en` pour l'anglais). La partie est gardée dans `~/.config/picodev/game`, hors du projet et lisible par vous seul, puis effacée quand elle se termine. Le bloc `export PICODEV_SESSION=… PICODEV_AGENT_TOKEN=…` de « Autre méthode » marche aussi.

## Déboguer

`.vscode/launch.json` (Cortex-Debug), pour chaque carte :

- **OpenOCD (USB)** et **pyOCD (USB)** : la sonde ST-LINK passée au conteneur (Linux : `--device=/dev/bus/usb` dans `runArgs`, et la règle udev de ST sur l'hôte) ;
- **GDB server on the host** : OpenOCD tourne sur l'hôte (`openocd -f board/st_nucleo_f4.cfg -c "bindto 0.0.0.0"`), le conteneur s'y connecte sur le port 3333. C'est le mode pour Windows et macOS.

Les vues des registres utilisent les SVD des packs CMSIS de ST, dans l'image.

## STM32CubeCLT

Les outils en ligne de commande de ST ne sont pas dans l'image (licence SLA0048, téléchargement après connexion sur st.com, Linux x86_64 seulement). Pour les installer : téléchargez l'installeur Linux, décompressez-le dans le dossier du projet, puis `picodev-install-stm32cubeclt st-stm32cubeclt_*.sh`.

Licence : MIT (`LICENSE`) ; les fichiers de configuration de la HAL (`boards/*/stm32*_hal_conf.h`) sont les modèles de ST, sous BSD-3-Clause (`boards/LICENSE-ST.md`).
