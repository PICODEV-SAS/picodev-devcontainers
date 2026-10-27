/* Zephyr: a connectable BLE peripheral that accepts pairing (SMP). */
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/sys/printk.h>

static const struct bt_data ad[] = {
    BT_DATA_BYTES(BT_DATA_FLAGS, BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR),
    BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

static void security_changed(struct bt_conn *conn, bt_security_t level, enum bt_security_err err)
{
    printk("security level %d, err %d\n", level, err);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
    .security_changed = security_changed,
};

int main(void)
{
    if (bt_enable(NULL) || bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad), NULL, 0)) {
        printk("no bluetooth\n");
        return 0;
    }
    printk("advertising as %s\n", CONFIG_BT_DEVICE_NAME);
    return 0;
}
