/* STM32F407: "hello" on USART2 (PA2, AF7) at 115200 baud from the 16 MHz HSI. */
#include "stm32f4xx.h"

static void putc_(char c)
{
    while (!(USART2->SR & USART_SR_TXE))
        ;
    USART2->DR = c;
}

int main(void)
{
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB1ENR |= RCC_APB1ENR_USART2EN;
    GPIOA->MODER = (GPIOA->MODER & ~GPIO_MODER_MODER2) | GPIO_MODER_MODER2_1;
    GPIOA->AFR[0] = (GPIOA->AFR[0] & ~GPIO_AFRL_AFSEL2) | (7u << GPIO_AFRL_AFSEL2_Pos);
    USART2->BRR = 16000000u / 115200u;
    USART2->CR1 = USART_CR1_TE | USART_CR1_UE;
    for (;;) {
        for (const char *s = "hello\r\n"; *s; s++)
            putc_(*s);
        for (volatile int i = 0; i < 200000; i++)
            ;
    }
}
