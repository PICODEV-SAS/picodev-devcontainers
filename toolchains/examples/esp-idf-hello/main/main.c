/* ESP-IDF: hello on the console and a blinking GPIO. */
#include <stdio.h>
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define LED GPIO_NUM_2

void app_main(void)
{
    gpio_reset_pin(LED);
    gpio_set_direction(LED, GPIO_MODE_OUTPUT);
    for (int level = 0;; level = !level) {
        printf("hello %d\n", level);
        gpio_set_level(LED, level);
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
