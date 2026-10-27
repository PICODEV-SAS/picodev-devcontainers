# A project with its own Makefile, the way STM32CubeMX generates them. tc sets
# CROSS_COMPILE, and the image sets CMSIS_PATH, STM32CUBE_PATH and TC_ARM_LD.
CC = $(CROSS_COMPILE)gcc
DEV = $(STM32CUBE_PATH)/f4/cmsis-device
CFLAGS = -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard -Os -g \
         -DSTM32F407xx -I$(CMSIS_PATH)/CMSIS/Core/Include -I$(DEV)/Include
SRCS = main.c $(DEV)/Source/Templates/system_stm32f4xx.c $(DEV)/Source/Templates/gcc/startup_stm32f407xx.s

build/uart.elf: $(SRCS) stm32f407vg.ld
	mkdir -p build
	$(CC) $(CFLAGS) $(SRCS) -T stm32f407vg.ld -L$(TC_ARM_LD) --specs=nano.specs --specs=nosys.specs \
	  -Wl,--gc-sections -Wl,-Map=build/uart.map -o $@
