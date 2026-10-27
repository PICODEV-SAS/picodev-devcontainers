/* Zephyr: hello on the console and led0 blinking. */
#include <zephyr/kernel.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>

static const struct gpio_dt_spec led = GPIO_DT_SPEC_GET(DT_ALIAS(led0), gpios);

int main(void)
{
    if (!gpio_is_ready_dt(&led) || gpio_pin_configure_dt(&led, GPIO_OUTPUT_INACTIVE) < 0) {
        printk("no led\n");
        return 0;
    }
    for (;;) {
        printk("hello from %s\n", CONFIG_BOARD);
        gpio_pin_toggle_dt(&led);
        k_msleep(500);
    }
    return 0;
}
