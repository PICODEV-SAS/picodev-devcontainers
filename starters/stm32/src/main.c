// Blinks the user LED and says hello on the ST-LINK virtual COM port (115200 baud),
// with the HAL and the reset clock (HSI).

#include <string.h>

#include "board.h"

static UART_HandleTypeDef uart = {
    .Instance = UART_INSTANCE,
    .Init = {
        .BaudRate = 115200,
        .WordLength = UART_WORDLENGTH_8B,
        .StopBits = UART_STOPBITS_1,
        .Parity = UART_PARITY_NONE,
        .Mode = UART_MODE_TX_RX,
        .HwFlowCtl = UART_HWCONTROL_NONE,
        .OverSampling = UART_OVERSAMPLING_16,
    },
};

void SysTick_Handler(void)
{
    HAL_IncTick();
}

static void say(const char *text)
{
    HAL_UART_Transmit(&uart, (const uint8_t *)text, strlen(text), HAL_MAX_DELAY);
}

int main(void)
{
    HAL_Init();
    board_clocks_enable();

    GPIO_InitTypeDef led = {.Pin = LED_PIN, .Mode = GPIO_MODE_OUTPUT_PP, .Pull = GPIO_NOPULL, .Speed = GPIO_SPEED_FREQ_LOW};
    HAL_GPIO_Init(LED_PORT, &led);
    GPIO_InitTypeDef pins = {.Pin = UART_PINS, .Mode = GPIO_MODE_AF_PP, .Pull = GPIO_NOPULL, .Speed = GPIO_SPEED_FREQ_HIGH, .Alternate = UART_AF};
    HAL_GPIO_Init(GPIOA, &pins);
    HAL_UART_Init(&uart);

    say("Hello from Picodev on " BOARD_NAME "\r\n");
    for (;;) {
        HAL_GPIO_TogglePin(LED_PORT, LED_PIN);
        HAL_Delay(500);
    }
}
