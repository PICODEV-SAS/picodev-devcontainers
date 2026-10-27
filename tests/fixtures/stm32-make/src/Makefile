# A challenge's own Makefile in src/ (kind make), laid out as the CTF's project.zip does:
# picodev sets CROSS_COMPILE, the image sets CMSIS_PATH, STM32CUBE_PATH and TC_ARM_LD.
CC = $(CROSS_COMPILE)gcc
DEV = $(STM32CUBE_PATH)/g0/cmsis-device

build/firmware.elf: main.c
	mkdir -p build
	printf 'MEMORY {\n FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 128K\n RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 36K\n}\nINCLUDE cortex-m.ld\n' > build/board.ld
	$(CC) -mcpu=cortex-m0plus -mfloat-abi=soft -mthumb -Os -DSTM32G071xx -I$(CMSIS_PATH)/CMSIS/Core/Include -I$(DEV)/Include \
	  main.c $(DEV)/Source/Templates/system_stm32g0xx.c $(DEV)/Source/Templates/gcc/startup_stm32g071xx.s \
	  -T build/board.ld -L$(TC_ARM_LD) --specs=nano.specs --specs=nosys.specs -Wl,--gc-sections -o $@
