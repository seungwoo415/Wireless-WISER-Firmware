/**
 * @file ble.c
 * @author Archie Lee
 * @brief Handles patch BLE logic. 
 * @details Implements BLE connection, advertisement, communication, and GATT server.  
 * @version 1.0
 * @date 2026-01-23
 */

/* Includes ------------------------------------------------------------------*/
#include "final_patch.h" 
#include "inputs.h"
#include "outputs.h" 
#include "rtc.h" 

// logging 
LOG_MODULE_REGISTER(spect, LOG_LEVEL_INF);
#define NRFX_LOG_MODULE                 EXAMPLE
#define NRFX_EXAMPLE_CONFIG_LOG_ENABLED 1
#define NRFX_EXAMPLE_CONFIG_LOG_LEVEL   3

/* UUID ------------------------------------------------------------------*/
#define SPECT_BASE_UUID BT_UUID_128_ENCODE(0x7231db4c, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee)

static struct bt_uuid_128 spect_uuid = BT_UUID_INIT_128(SPECT_BASE_UUID);
static struct bt_uuid_128 sipo_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db4d, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee)); 
static struct bt_uuid_128 dac_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db4e, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
static struct bt_uuid_128 sramout_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db4f, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
static struct bt_uuid_128 al_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db50, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
static struct bt_uuid_128 dl_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db51, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee)); 
static struct bt_uuid_128 dataout_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db52, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
static struct bt_uuid_128 syscmd_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db53, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
static struct bt_uuid_128 count_status_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db54, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));

const struct bt_data ad[] = {
    /* Set advertising flags: General discoverable, BR/EDR not supported */
    BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
    
    /* Advertise the 128-bit Service UUID so the Motherboard can filter for it */
    BT_DATA_BYTES(BT_DATA_UUID128_ALL, 
        0xee, 0x47, 0x81, 0x34, 0x84, 0x2b, 0x9f, 0xbe, 
        0xf7, 0x4b, 0xed, 0x67, 0x4c, 0xdb, 0x31, 0x72), 
};

const struct bt_data sd[] = {
    BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1), 
};

/* Global Variables ------------------------------------------------------------------*/
struct bt_conn *current_conn;
struct sramout_ble_packet ble_sramout_packet;
struct count_status_packet status_packet; 

/* BLE Connection Functions ------------------------------------------------------------------*/
void on_connected(struct bt_conn *conn, uint8_t err)
{
    if (err) {
        LOG_ERR("Connection failed (err %u)\n", err);
        return;
    }

    LOG_INF("Connected! Motherboard is now talking to us.\n");

    // erase for actual patch 
    //nrf_gpio_pin_set(BLE_LED);
    
    // Save the connection reference
    current_conn = bt_conn_ref(conn);
} 

void on_disconnected(struct bt_conn *conn, uint8_t reason)
{
    printk("Disconnected (reason %u)\n", reason);
    // erase for actual patch 
    //nrf_gpio_pin_clear(BLE_LED); 
    
    if (current_conn) {
        bt_conn_unref(current_conn);
        current_conn = NULL;
    }
    
    // CRITICAL: Start advertising again so the Motherboard can reconnect!
    // bt_le_adv_start(BT_LE_ADV_CONN, NULL, 0, NULL, 0);
    patch_ad_start();
}

// Register the callbacks with the system
BT_CONN_CB_DEFINE(conn_callbacks) = {
    .connected = on_connected,
    .disconnected = on_disconnected,
};

/* BLE Callback Functions ------------------------------------------------------------------*/
static ssize_t sipo_write_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                             const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
{
    if (len != 16) {
        return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
    }

    
    sipo_reset(); 
    reset_sramout();  

    const uint8_t *data = (const uint8_t *)buf; 

    // LOG_INF("First byte: 0x%02X \n", data[0]);
    // LOG_INF("Second byte: 0x%02X \n", data[1]);
    // LOG_INF("Second byte: 0x%02X \n", data[2]);
    // LOG_INF("Sixth byte: 0x%02X \n", data[6]);
    // LOG_INF("Twelvth byte: 0x%02X \n", data[12]);
    // LOG_INF("Last byte: 0x%02X \n", data[15]);

    // prepare sipo_buffer 
    prepare_sipo_buffer(data); 

    // send the sipo data 
    sipo_trigger_transfer(); 

    // start the sipo transfer for now lets assume sending the sipo data means sipo_trigger 
    LOG_INF("SIPO Data Received! Sending the SIPO data with first byte: 0x%02X and last byte: 0x%02X", data[0], data[len-1]); 

    while(!sipo_done) {
        k_usleep(10); 
    }

    // sipo is done 
    done_wr_sipo = 1; 

    // notify motherboard that sipo is done 
    bt_gatt_notify(conn, attr, (const void *)&done_wr_sipo, sizeof(done_wr_sipo)); 

    LOG_INF("SIPO done! Sent done_wr_sipo to motherboard \n");

    return len;
} 

// dac write callback 
static ssize_t dac_write_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                             const void *buf, uint16_t len, uint16_t offset, uint8_t flags)
{
    if (len != 5) {
        return BT_GATT_ERR(BT_ATT_ERR_INVALID_ATTRIBUTE_LEN);
    }

    // Copy incoming wireless data to our local buffer
    //memcpy(ble_dac_buffer, buf, len);

    const uint8_t *data = (const uint8_t *)buf;

    // send dac data 
    dac_reset(); 
    dac_i2c_write(data, len); 

    // start the dac transfer for now lets assume sending the dac data means dac_trigger 
    LOG_INF("DAC Data Received! Sending the DAC data with first byte: 0x%02X and last byte: 0x%02X", data[0], data[len-1]); 

    // dac is done 
    done_wr_dac = 1; 
                    
    // notify motherboard that sipo is done 
    bt_gatt_notify(conn, attr, &done_wr_dac, sizeof(done_wr_dac));

    LOG_INF("DAC done! Sent done_wr_dac to motherboard \n");

    return len;
} 

// sramout read callback 
static ssize_t sramout_read_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                            void *buf, uint16_t len, uint16_t offset)
{

    // This helper function handles the offset and length logic for you 
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &ble_sramout_packet, sizeof(ble_sramout_packet));
    
} 

// al read callback 
static ssize_t al_read_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                            void *buf, uint16_t len, uint16_t offset)
{

    update_al_counter(); 
    
    // This helper function handles the offset and length logic for you 
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &ble_al_counter, sizeof(ble_al_counter));
} 

// dl read callback 
static ssize_t dl_read_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                            void *buf, uint16_t len, uint16_t offset)
{

    update_dl_counter();
 
    // This helper function handles the offset and length logic for you 
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &ble_dl_counter, sizeof(ble_dl_counter));
}

// dataout read callback 
static ssize_t dataout_read_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                            void *buf, uint16_t len, uint16_t offset)
{

    

    // struct dataout_ble_packet pkt; 
    // if (k_msgq_get(&fifo_data_out, &pkt, K_NO_WAIT) == 0){
    //     LOG_INF("Dataout read request: Popping 0x%08X", pkt.dataout);
    //     return bt_gatt_attr_read(conn, attr, buf, len, offset, &pkt, sizeof(pkt));
    // } else {
    //     // FIFO is empty, return 0 or an error code
    //     LOG_WRN("Dataout read request: FIFO Empty");
    //     return 0; 
    // }

    return 0; 
} 

// BLE ADDED
static ssize_t count_status_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                            void *buf, uint16_t len, uint16_t offset)
{   
    // erase 
    // struct dataout_ble_packet new_pkt;
    // new_pkt.dataout = 12; 
    // new_pkt.timestamp = 1; 
    // LOG_INF("Erasing flash"); 
    // flash_erase(FLASH_DEVICE, FLASH_BASE_OFFSET, FLASH_TOTAL_SIZE);
    // flash_write(FLASH_DEVICE, FLASH_BASE_OFFSET, &new_pkt, sizeof(new_pkt));
    // gamma_counts++; 

    // current_write_offset = 0; 
    // current_write_offset += sizeof(new_pkt);
    // new_pkt.dataout = 2; 
    // new_pkt.timestamp = 2;
    // flash_write(FLASH_DEVICE, FLASH_BASE_OFFSET + current_write_offset, &new_pkt, sizeof(new_pkt)); 
    // gamma_counts++; 
    get_count_status(); 
    
    return bt_gatt_attr_read(conn, attr, buf, len, offset, &status_packet, sizeof(status_packet));
} 

// ADDED
int dataout_dump(struct bt_conn *conn) {
    LOG_INF("dump start"); 
    if (!is_dumping || !conn) {
        return 0; 
    }
    
    struct dataout_ble_packet pkt; 
    struct dataout_ble_packet end_pkt = {
        .timestamp = 0xFFFFFFFF,    // All 32 bits set
        .dataout   = 0x3FFFFFF,     // All 26 bits set (max for 26-bit field)
        .reserved  = 0x3F           // All 6 bits set (max for 6-bit field)
    }; 

    int ble_err = 0; 
    int packets_sent_this_round = 0; 
    const int MAX_SENT_PER_CALL = 20; 
    
    // no gamma counts 
    if (gamma_counts == 0) {
        // send the end of data
        ble_err = bt_gatt_notify(conn, &spect_svc.attrs[15], &end_pkt, sizeof(end_pkt)); 
        if (ble_err == 0) {
            is_dumping = false; 
        }
        return ble_err; 
    }

    while (dump_offset < current_write_offset) {
        if (packets_sent_this_round >= MAX_SENT_PER_CALL) {
            return 0; // Return to main loop, will resume next pass
        }

        int flash_err = flash_read(FLASH_DEVICE, FLASH_BASE_OFFSET + dump_offset, 
                                   &pkt, sizeof(pkt)); 

        if (flash_err != 0) {
            LOG_ERR("Flash read error during dump at %u", dump_offset); 
            is_dumping = false; 
            return flash_err; 
        }

        ble_err = bt_gatt_notify(conn, &spect_svc.attrs[15], &pkt, sizeof(pkt)); // double check
        if (ble_err == 0) {
            dump_offset += sizeof(pkt); // Success: increment pointer
            packets_sent_this_round++; 
        } else if (ble_err == -ENOMEM) {
            // BLE stack is full for this millisecond. 
            // Exit the function and try again on the next main loop pass.
            return ble_err; 
        } else {
            LOG_ERR("BLE Notification failed: %d", ble_err);
            is_dumping = false;
            return ble_err;
        }

        if (dump_offset >= current_write_offset) { 
            ble_err = bt_gatt_notify(conn, &spect_svc.attrs[15], &end_pkt, sizeof(end_pkt)); 
            if(ble_err == -ENOMEM) {
                return ble_err; 
            }
            is_dumping = false; 
            LOG_INF("--- BULK TRANSFER COMPLETE --- Total Bytes: %u", dump_offset);
        } 
    }

    return 0; 
}

// ADDED 
void reset_mem(void) {
    LOG_INF("Erasing flash for experiment...");
    int err = flash_erase(FLASH_DEVICE, FLASH_BASE_OFFSET, FLASH_TOTAL_SIZE);
    if (err) {
            LOG_ERR("Flash erase failed: %d", err);
    }

    current_write_offset = 0;
}

// sys command callback  BLE ADDED 
static ssize_t syscmd_write_cb(struct bt_conn *conn, const struct bt_gatt_attr *attr,
                             const void *buf, uint16_t len, uint16_t offset, uint8_t flags) 
{
    uint8_t command = ((uint8_t *)buf)[0];
    
    switch (command) {
        case 0x01: // reset sipo
            done_wr_sipo = 0; 
            //memset((void*)sipo_buffer, 0, sizeof(sipo_buffer));
            LOG_INF("reset sipo \n");
            break;
        
        case 0x02: // reset dac
            dac_reset(); 
            //memset((void*)dac_buffer, 0, sizeof(dac_buffer));
            LOG_INF("reset dac \n"); 
            break; 
        
        case 0x03: // reset sramout   
            reset_sramout(); 
            LOG_INF("reset sramout \n"); 
            break; 
        
        case 0x04: // reset aldl
            reset_al_counter(); 
            reset_dl_counter();  
            LOG_INF("reset aldl \n");  
            break; 
        
        case 0x05: // reset dataout + start rtc timer
            reset_dataout(); 
            LOG_INF("reset dataout \n"); 
            break;
        
        case 0x06: // reset chip 
            LOG_INF("reset chip \n"); 
            chip_reset(); 
            break;
        
        case 0x07: // reset global
            // reset memory
            chip_reset(); 
            reset_mem(); 
            reset_dataout();
            chip_reset();
            reset_dataout(); 
            gamma_counts = 0; 
            rtc_overflow_count = 0; 
            // reset rtc_timer need to add 
            LOG_INF("reset global \n"); 
            break; 
        
        case 0x08: // stop gamma counts 
            // stop timer + call dataout_dum[ ]
            dump_offset = 0; 
            is_dumping = true; 
            stop_timestamp_rtc(); 
            LOG_INF("stop gamma counts \n");
            break;

        case 0x09: // start gamma counts  
            // stop timer + call dataout_dump  
            start_timestamp_rtc();
            LOG_INF("start gamma counts \n");
            struct dataout_ble_packet start_signal = {
                .timestamp = 0xFFFFFFFF,
                .dataout = 0x1, // Signal for START
                .reserved = 0
            };
            bt_gatt_notify(conn, &spect_svc.attrs[15], &start_signal, sizeof(start_signal));

            // reset_mem(); 
            // reset_dataout();
            // gamma_counts = 0; 

            // struct dataout_ble_packet new_pkt;
            // int err; 
            // for (int i = 1; i < 11; i++) {
            //     new_pkt.dataout = i; 
            //     new_pkt.timestamp = i + 1; 
            //     err = flash_write(FLASH_DEVICE, FLASH_BASE_OFFSET + current_write_offset, &new_pkt, sizeof(new_pkt));
            //     if (err < 0) {
            //         LOG_ERR("flash write failed");
            //     } else {
            //         current_write_offset += sizeof(new_pkt); 
            //         gamma_counts++; 
            //     }
            // }
            //dump_offset = 0;
            //is_dumping = true; 
            LOG_INF("Ready to dump");

            break;
        
        case 0x0A: // start gamma counts  
        // stop timer + call dataout_dump  
            LOG_INF("reset patch \n");
            static struct sramout_ble_packet reset_pkt;
        
            // Fill the whole struct with Fs
            memset(&reset_pkt, 0xFF, sizeof(reset_pkt));
            
            // Send the "Signal" to the Motherboard
            bt_gatt_notify(NULL, &spect_svc.attrs[8], &reset_pkt, sizeof(reset_pkt));
            k_msleep(100);
            sys_reboot(SYS_REBOOT_COLD);
            break; 

        default:
            LOG_INF("Unknown Command: 0x%02X\n", command);
            return BT_GATT_ERR(BT_ATT_ERR_VALUE_NOT_ALLOWED);
    }

    return len; 

}

void patch_ad_start(void) {
    LOG_INF("Device Name: %s", CONFIG_BT_DEVICE_NAME);
    int err = bt_le_adv_start(BT_LE_ADV_CONN, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
    if (err) {
        LOG_ERR("Adv start failed (err %d)", err);
    }
}

/* GATT Server ------------------------------------------------------------------*/
BT_GATT_SERVICE_DEFINE(spect_svc,
        BT_GATT_PRIMARY_SERVICE(&spect_uuid),
        BT_GATT_CHARACTERISTIC(&sipo_uuid.uuid,
                    BT_GATT_CHRC_WRITE | BT_GATT_CHRC_NOTIFY,    // Motherboard can write
                    BT_GATT_PERM_WRITE,    // Requires write permission
                    NULL, sipo_write_cb, NULL), 
        BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE), 
        BT_GATT_CHARACTERISTIC(&dac_uuid.uuid,
                    BT_GATT_CHRC_WRITE | BT_GATT_CHRC_NOTIFY,    // Motherboard can write
                    BT_GATT_PERM_WRITE,    // Requires write permission
                    NULL, dac_write_cb, NULL), 
        BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE), 
        BT_GATT_CHARACTERISTIC(&sramout_uuid.uuid,
                    BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,    // Motherboard can read
                    BT_GATT_PERM_READ,    // Requires read permission
                    sramout_read_cb, NULL, NULL),
        BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE), 
        BT_GATT_CHARACTERISTIC(&al_uuid.uuid,
                    BT_GATT_CHRC_READ,    // Motherboard can read
                    BT_GATT_PERM_READ,    // Requires read permission
                    al_read_cb, NULL, NULL),
        BT_GATT_CHARACTERISTIC(&dl_uuid.uuid,
                    BT_GATT_CHRC_READ,    // Motherboard can read
                    BT_GATT_PERM_READ,    // Requires read permission
                    dl_read_cb, NULL, NULL),
        BT_GATT_CHARACTERISTIC(&dataout_uuid.uuid,
                    BT_GATT_CHRC_READ | BT_GATT_CHRC_NOTIFY,    // Motherboard can read
                    BT_GATT_PERM_READ,    // Requires read permission
                    dataout_read_cb, NULL, NULL),
        BT_GATT_CCC(NULL, BT_GATT_PERM_READ | BT_GATT_PERM_WRITE),
        BT_GATT_CHARACTERISTIC(&syscmd_uuid.uuid,
                    BT_GATT_CHRC_WRITE,    
                    BT_GATT_PERM_WRITE,    
                    NULL, syscmd_write_cb, NULL), 
        BT_GATT_CHARACTERISTIC(&count_status_uuid.uuid,
                    BT_GATT_CHRC_READ,    // Motherboard can read
                    BT_GATT_PERM_READ,    // Requires read permission
                    count_status_cb, NULL, NULL)
);


