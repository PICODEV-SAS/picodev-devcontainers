# Corresponding source of the GPL binaries

The images carry GPL-licensed binaries built by their vendors (not Debian packages,
whose sources are in the Debian archive at the versions in `/opt/picodev/versions.json`).
Exact sources, at the versions the images pin:

| Binary | Image | Version | Source |
|---|---|---|---|
| QEMU for Xtensa and RISC-V (GPL-2.0) | dev-esp32 | esp_develop_9.2.2_20260417 | https://github.com/espressif/qemu/tree/esp_develop_9.2.2_20260417 |
| OpenOCD for ESP32 (GPL-2.0) | dev-esp32 | v0.12.0-esp32-20260831 | https://github.com/espressif/openocd-esp32/tree/v0.12.0-esp32-20260831 |
| GDB for ESP chips (GPL-3.0) | dev-esp32 | esp-gdb-v17.1_20260402 | https://github.com/espressif/binutils-gdb/tree/esp-gdb-v17.1_20260402 |
| GCC, binutils for Xtensa and RISC-V (GPL-3.0) | dev-esp32 | esp-14.2.0_20260121 | https://github.com/espressif/crosstool-NG/releases/tag/esp-14.2.0_20260121 |
| esptool (GPL-2.0) | dev-esp32 | 4.12.0 | https://github.com/espressif/esptool/tree/v4.12.0 |
| Arm GNU Toolchain (GPL-3.0) | dev-stm32 | 14.3.rel1 | https://developer.arm.com/downloads/-/arm-gnu-toolchain-downloads (source tarball of 14.3.rel1) |
| Zephyr SDK, arm-zephyr-eabi (GPL-3.0) | dev-nrf52 | 1.0.1 | https://github.com/zephyrproject-rtos/sdk-ng/tree/v1.0.1 |
| avr-gcc (GPL-3.0) | dev-avr | 7.3.0-atmel3.6.1-arduino7 | https://github.com/arduino/toolchain-avr/tree/7.3.0-atmel3.6.1-arduino7 |
| avrdude (GPL-2.0) | dev-avr | 6.3-20190619 | https://github.com/arduino/avrdude-build-script (avrdude 6.3, Arduino patches of 2019-06-19) |

The compilers come from the toolchain images (`toolchains/`, from picodev-lab-workers at
the commit in the `Makefile`); the rest is added here. Written offer for all the GPL and
LGPL binaries of the images, Debian packages included: `base/SOURCES-OFFER`.
