/* Bare metal with CMSIS only: blink the user LED of each board. tc adds the
 * startup file, SystemInit and a linker script for the board. */
#if defined(STM32F407xx)
#include "stm32f4xx.h"
#define LED_PORT GPIOD
#define LED_PIN 12
static void clock_on(void) { RCC->AHB1ENR |= RCC_AHB1ENR_GPIODEN; }
#elif defined(STM32G071xx)
#include "stm32g0xx.h"
#define LED_PORT GPIOA
#define LED_PIN 5
static void clock_on(void) { RCC->IOPENR |= RCC_IOPENR_GPIOAEN; }
#elif defined(STM32L552xx)
#include "stm32l5xx.h"
#define LED_PORT GPIOC
#define LED_PIN 7
static void clock_on(void) { RCC->AHB2ENR |= RCC_AHB2ENR_GPIOCEN; }
#else
#error "unknown device"
#endif

int main(void)
{
    clock_on();
    LED_PORT->MODER = (LED_PORT->MODER & ~(3u << (2 * LED_PIN))) | (1u << (2 * LED_PIN));
    for (;;) {
        LED_PORT->ODR ^= 1u << LED_PIN;
        for (volatile int i = 0; i < 100000; i++)
            ;
    }
}
