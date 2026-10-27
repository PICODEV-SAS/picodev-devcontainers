cmake_minimum_required(VERSION 3.20)
project(starter C ASM)

# Board (CMakePresets.json): series, device, CPU flags.
set(BOARD nucleo-f446re CACHE STRING "nucleo-f446re or nucleo-g071rb")
if(BOARD STREQUAL nucleo-f446re)
  set(SERIES f4)
  set(DEVICE STM32F446xx)
  set(CPU -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard)
elseif(BOARD STREQUAL nucleo-g071rb)
  set(SERIES g0)
  set(DEVICE STM32G071xx)
  set(CPU -mcpu=cortex-m0plus -mthumb -mfloat-abi=soft)
else()
  message(FATAL_ERROR "unknown BOARD ${BOARD}")
endif()
string(TOLOWER ${DEVICE} device)

# CMSIS and STM32Cube from the image (STM32CUBE_PATH, CMSIS_PATH), or from your own copies.
set(STM32CUBE_PATH $ENV{STM32CUBE_PATH} CACHE PATH "Directory with <series>/cmsis-device and <series>/hal")
set(CMSIS_PATH $ENV{CMSIS_PATH} CACHE PATH "CMSIS 6 (CMSIS/Core)")
set(DEV ${STM32CUBE_PATH}/${SERIES}/cmsis-device)
set(HAL ${STM32CUBE_PATH}/${SERIES}/hal)

set(HAL_MODULES hal hal_cortex hal_rcc hal_gpio hal_uart hal_dma hal_pwr hal_flash)
list(TRANSFORM HAL_MODULES PREPEND ${HAL}/Src/stm32${SERIES}xx_)
list(TRANSFORM HAL_MODULES APPEND .c)

add_executable(starter
  src/main.c
  ${DEV}/Source/Templates/system_stm32${SERIES}xx.c
  ${DEV}/Source/Templates/gcc/startup_${device}.s
  ${HAL_MODULES}
)
target_include_directories(starter PRIVATE
  boards/${BOARD} ${HAL}/Inc ${DEV}/Include ${CMSIS_PATH}/CMSIS/Core/Include)
target_compile_definitions(starter PRIVATE ${DEVICE} USE_HAL_DRIVER)
target_compile_options(starter PRIVATE ${CPU} -Og -g3 -Wall -ffunction-sections -fdata-sections)
target_link_options(starter PRIVATE ${CPU} -specs=nano.specs
  -L${CMAKE_SOURCE_DIR}/cmake -T${CMAKE_SOURCE_DIR}/boards/${BOARD}/board.ld
  -Wl,--gc-sections -Wl,--no-warn-rwx-segments -Wl,-Map=starter.map -Wl,--print-memory-usage)
set_target_properties(starter PROPERTIES SUFFIX .elf)
add_custom_command(TARGET starter POST_BUILD
  COMMAND ${CMAKE_OBJCOPY} -O ihex starter.elf starter.hex
  COMMAND ${CMAKE_OBJCOPY} -O binary starter.elf starter.bin)
