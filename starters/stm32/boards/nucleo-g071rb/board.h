// Nucleo-G071RB: user LED LD4 on PA5, ST-LINK virtual COM port on USART2 (PA2, PA3, AF1).
#pragma once
#include "stm32g0xx_hal.h"

#define LED_PORT GPIOA
#define LED_PIN GPIO_PIN_5
#define UART_INSTANCE USART2
#define UART_PINS (GPIO_PIN_2 | GPIO_PIN_3)
#define UART_AF GPIO_AF1_USART2
#define BOARD_NAME "Nucleo-G071RB"

static inline void board_clocks_enable(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();
}
