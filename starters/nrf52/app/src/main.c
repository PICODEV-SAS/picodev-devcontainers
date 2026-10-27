// Minimal BLE central for the nRF52840 DK: scans (passive) and writes every advertisement
// it hears on the console UART (uart0, 115200 baud): address, RSSI, name, raw AD data.
// Starting point of the "Balise" challenge: find the beacon, then read what it says.

#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#define NAME_MAX 29 /* the most a legacy advertisement can carry */

static bool find_name(struct bt_data *data, void *user_data)
{
    char *name = user_data;

    if (data->type != BT_DATA_NAME_COMPLETE && data->type != BT_DATA_NAME_SHORTENED) {
        return true; /* keep parsing */
    }
    size_t len = MIN(data->data_len, NAME_MAX);
    for (size_t i = 0; i < len; i++) {
        char c = data->data[i];
        name[i] = (c >= 0x20 && c < 0x7f) ? c : '.'; /* the UART gets printable text only */
    }
    name[len] = '\0';
    return false;
}

static void device_found(const bt_addr_le_t *addr, int8_t rssi, uint8_t adv_type,
                         struct net_buf_simple *ad)
{
    char addr_str[BT_ADDR_LE_STR_LEN];
    char name[NAME_MAX + 1] = "";
    char data[2 * BT_GAP_ADV_MAX_ADV_DATA_LEN + 1];

    bt_addr_le_to_str(addr, addr_str, sizeof(addr_str));
    bin2hex(ad->data, MIN(ad->len, BT_GAP_ADV_MAX_ADV_DATA_LEN), data, sizeof(data));
    bt_data_parse(ad, find_name, name); /* after bin2hex: parsing consumes the buffer */
    printk("adv %s rssi %d type %u name \"%s\" data %s\n", addr_str, rssi, adv_type, name, data);
}

int main(void)
{
    struct bt_le_scan_param scan = {
        .type = BT_LE_SCAN_TYPE_PASSIVE,
        .options = BT_LE_SCAN_OPT_NONE,
        .interval = BT_GAP_SCAN_FAST_INTERVAL,
        .window = BT_GAP_SCAN_FAST_WINDOW,
    };
    int err = bt_enable(NULL);

    if (err) {
        printk("bt_enable failed (%d)\n", err);
        return 0;
    }
    err = bt_le_scan_start(&scan, device_found);
    if (err) {
        printk("scan failed (%d)\n", err);
        return 0;
    }
    printk("Picodev BLE central on %s: scanning\n", CONFIG_BOARD_TARGET);
    return 0;
}
