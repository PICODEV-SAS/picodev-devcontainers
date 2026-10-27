// Nucleo-F446RE: user LED LD2 on PA5, ST-LINK virtual COM port on USART2 (PA2, PA3, AF7).
#pragma once
#include "stm32f4xx_hal.h"

#define LED_PORT GPIOA
#define LED_PIN GPIO_PIN_5
#define UART_INSTANCE USART2
#define UART_PINS (GPIO_PIN_2 | GPIO_PIN_3)
#define UART_AF GPIO_AF7_USART2
#define BOARD_NAME "Nucleo-F446RE"

static inline void board_clocks_enable(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_USART2_CLK_ENABLE();
}
