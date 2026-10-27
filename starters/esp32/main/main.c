// Says hello with the chip it runs on, then counts every second.

#include <inttypes.h>
#include <stdio.h>

#include "esp_chip_info.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "starter";

void app_main(void)
{
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    ESP_LOGI(TAG, "Hello from Picodev on %s, %d core(s)", CONFIG_IDF_TARGET, chip.cores);
    for (uint32_t n = 0;; n++) {
        ESP_LOGI(TAG, "tick %" PRIu32, n);
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
