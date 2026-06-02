/**
 * @file ble.c
 * @author Archie Lee
 * @brief Handles motherboard BLE logic. 
 * @details Implements BLE connection, scanning, communication, and subscriptions.  
 * @version 1.0
 * @date 2026-02-3
 */

/* Includes ------------------------------------------------------------------*/
#include "final_mb.h" 
#include "ble.h" 

// logging 
LOG_MODULE_DECLARE(final_mb, LOG_LEVEL_INF);

/* UUID ------------------------------------------------------------------*/
#define SPECT_BASE_UUID BT_UUID_128_ENCODE(0x7231db4c, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee)

struct bt_uuid_128 spect_uuid = BT_UUID_INIT_128(SPECT_BASE_UUID);
struct bt_uuid_128 sipo_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db4d, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee)); 
struct bt_uuid_128 dac_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db4e, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
struct bt_uuid_128 sramout_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db4f, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
struct bt_uuid_128 al_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db50, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
struct bt_uuid_128 dl_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db51, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee)); 
struct bt_uuid_128 dataout_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db52, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
struct bt_uuid_128 syscmd_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db53, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));
struct bt_uuid_128 count_status_uuid  = BT_UUID_INIT_128(BT_UUID_128_ENCODE(0x7231db54, 0x67ed, 0x4bf7, 0xbe9f, 0x2b84348147ee));

/* Global Variables ------------------------------------------------------------------*/
uint16_t data_deq_0; 
uint16_t data_deq_1; 
uint32_t al_counter = 0; 
uint32_t dl_counter = 0; 
struct sramout_ble_packet ble_sramout_packet;
uint16_t dac2, dac1, dac0; 
uint16_t sipo7, sipo6, sipo5, sipo4, sipo3, sipo2, sipo1, sipo0; 

uint8_t done_wr_sipo = 0;
uint8_t done_wr_dac = 0;
uint16_t SRAM_rd_reset = 0; 
uint16_t dlal_reset = 0; 
uint16_t data_rd_reset = 0;
uint16_t sipo_reset = 0;

static struct bt_gatt_read_params al_read_params[MAX_PATCHES];
static struct bt_gatt_read_params dl_read_params[MAX_PATCHES];
static struct bt_gatt_read_params dataout_read_params[MAX_PATCHES];
static struct bt_gatt_read_params count_status_read_params[MAX_PATCHES];

static struct bt_gatt_discover_params discover_params[MAX_PATCHES];
static struct bt_gatt_discover_params ccc_params[MAX_PATCHES];
static struct bt_gatt_subscribe_params sipo_sub_params[MAX_PATCHES];
static struct bt_gatt_subscribe_params dac_sub_params[MAX_PATCHES];
static struct bt_gatt_subscribe_params sramout_sub_params[MAX_PATCHES];
static struct bt_gatt_subscribe_params dataout_sub_params[MAX_PATCHES];

// uint16_t sipo_data_handle; 
// uint16_t sipo_notify_handle;
// uint16_t dac_data_handle; 
// uint16_t dac_notify_handle; 
// uint16_t sramout_data_handle;
// uint16_t sramout_notify_handle;
// uint16_t dataout_data_handle; 
// uint16_t dataout_notify_handle;  
// uint16_t al_data_handle; 
// uint16_t dl_data_handle;  
// uint16_t syscmd_data_handle;
// uint16_t count_status_data_handle;

struct bt_conn *current_conn[MAX_PATCHES] = {NULL};
struct patch_handles patch_handle[MAX_PATCHES];

int connected_patches = 0; 
int patch_num = 2; 
static int found_patch_id = -1;

static bool found_target = false;
static const uint16_t ALL_FS_REF[10] = {0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF}; 
static bool is_connecting = false; 

static int get_slot_from_conn(struct bt_conn *conn) {
    for (int i = 0; i < MAX_PATCHES; i++) {
        if (current_conn[i] == conn) return i;
    }
    return -1;
}

/* BLE Read/Write/Notify Functions ------------------------------------------------------------------*/
static uint8_t sipo_notify_cb(struct bt_conn *conn, struct bt_gatt_subscribe_params *params,
                             const void *data, uint16_t length)
{
    if (!data) {
        LOG_WRN("Unsubscribed from SIPO notifications");
        params->value_handle = 0U;
        return BT_GATT_ITER_STOP;
    }

    done_wr_sipo = *(uint8_t *)data;
    if (done_wr_sipo == 1) {
        char sipo_done[] = "SIPO_DONE\n";
        int len = strlen(sipo_done); 
        int sent = 0;
        while (sent < len) {
            int ret = uart_fifo_fill(uart, (uint8_t *)sipo_done + sent, len - sent);
            if (ret > 0) {
                sent += ret;
            }
        }
        done_wr_sipo = 0; 
    }

    return BT_GATT_ITER_CONTINUE;
}

static uint8_t dac_notify_cb(struct bt_conn *conn, struct bt_gatt_subscribe_params *params,
                             const void *data, uint16_t length)
{
    if (!data) {
        LOG_WRN("Unsubscribed from DAC notifications");
        params->value_handle = 0U;
        return BT_GATT_ITER_STOP;
    }

    done_wr_dac = *(uint8_t *)data;
    if (done_wr_dac == 1) {
        char dac_done[] = "DAC_DONE\n";
        int len = strlen(dac_done); 
        int sent = 0;
        while (sent < len) {
            int ret = uart_fifo_fill(uart, (uint8_t *)dac_done + sent, len - sent);
            if (ret > 0) {
                sent += ret;
            }
        }
        done_wr_dac = 1;
    }

    return BT_GATT_ITER_CONTINUE;
}

static uint8_t sramout_notify_cb(struct bt_conn *conn,
                                 struct bt_gatt_subscribe_params *params,
                                 const void *data, uint16_t length)
{
    if (!data) {
        LOG_INF("SRAMOUT Unsubscribed");
        params->value_handle = 0U;
        return BT_GATT_ITER_STOP;
    }

    LOG_INF("Received %u bytes of SRAMOUT data", length);

    if (length == sizeof(struct sramout_ble_packet)) {
        memcpy(&ble_sramout_packet, data, sizeof(ble_sramout_packet));
        
        // patch reset is done 
        if (memcmp(data, ALL_FS_REF, sizeof(ble_sramout_packet)) == 0) {
            char patch_rst[] = "PATCH_RST_DONE\n";
            int len = strlen(patch_rst); 
            int sent = 0;
            while (sent < len) {
                int ret = uart_fifo_fill(uart, (uint8_t *)patch_rst + sent, len - sent);
                if (ret > 0) {
                    sent += ret;
                }
            }
            return BT_GATT_ITER_CONTINUE;
        }

        char buf[128];
        int len = snprintf(buf, sizeof(buf), 
                    "SRAMOUT:%04X,%04X,%04X,%04X,%04X,%04X,%04X,%04X,%04X,%04X\n",
                    ble_sramout_packet.SRAM_out0, ble_sramout_packet.SRAM_out1, ble_sramout_packet.SRAM_out2,
                    ble_sramout_packet.SRAM_out3, ble_sramout_packet.SRAM_out4, ble_sramout_packet.SRAM_out5,
                    ble_sramout_packet.SRAM_out6, ble_sramout_packet.SRAM_out7, ble_sramout_packet.SRAM_out8, ble_sramout_packet.SRAM_out9);

        int sent = 0;
        while (sent < len) {
            int ret = uart_fifo_fill(uart, (uint8_t *)buf + sent, len - sent);
            if (ret > 0) sent += ret;
        }

        LOG_INF("--- TEST DATA RECEIVED FROM PATCH ---");
        LOG_INF("Out0: 0x%04X", ble_sramout_packet.SRAM_out0); // Should be 0xAABB
        LOG_INF("Out1: 0x%04X", ble_sramout_packet.SRAM_out1); // Should be 0xCCDD
        LOG_INF("Out2: 0x%04X", ble_sramout_packet.SRAM_out2); // Should be 0x1234
        LOG_INF("Out3: 0x%04X", ble_sramout_packet.SRAM_out3);
        LOG_INF("Out4: 0x%04X", ble_sramout_packet.SRAM_out4);
        LOG_INF("Out5: 0x%04X", ble_sramout_packet.SRAM_out5);
        LOG_INF("Out6: 0x%04X", ble_sramout_packet.SRAM_out6);
        LOG_INF("Out7: 0x%04X", ble_sramout_packet.SRAM_out7); // Should be 0x5678
        LOG_INF("Out8: 0x%04X", ble_sramout_packet.SRAM_out8);
        LOG_INF("Out9: 0x%04X", ble_sramout_packet.SRAM_out9);
        LOG_INF("------------------------------------");
    } else {
        LOG_WRN("Unexpected SRAMOUT length: %u", length);
    }

    return BT_GATT_ITER_CONTINUE;
}

static uint8_t dataout_notify_cb(struct bt_conn *conn,
                                 struct bt_gatt_subscribe_params *params,
                                 const void *data, uint16_t length)
{
    if (!data) {
        //LOG_INF("DATAOUT Unsubscribed");
        //params->value_handle = 0U;
        return BT_GATT_ITER_STOP;
    }

    LOG_INF("Received %u bytes of DATAOUT data", length);

    // int i = 1; 
    // if (i) {
    //     struct dataout_ble_packet pkt; 
    //     memcpy(&pkt, data, sizeof(pkt));
    //     LOG_INF("DATAOUT: 0x%07X, TS: %07X", pkt.dataout, pkt.timestamp);
    //     return BT_GATT_ITER_CONTINUE;
    // }

    if (length == sizeof(struct dataout_ble_packet)) {
        struct dataout_ble_packet pkt; 
        memcpy(&pkt, data, sizeof(pkt));

        // I need to process dataout --> need to change for more than one patch
        char tx_buf[64];
        int len; 
        if (pkt.timestamp != 0xFFFFFFFF) { 
            uint32_t raw_data = (uint32_t)pkt.dataout;
            uint32_t raw_time = (uint32_t)pkt.timestamp;    
            int slot = get_slot_from_conn(conn);
            len = snprintf(tx_buf, sizeof(tx_buf), "DATAOUT:%d,%u,%u\n", 
                           slot, raw_data, raw_time);
        } else {
            // Now we know timestamp IS 0xFFFFFFFF, check the 64-bit value to see if it's DONE
            if (*(uint64_t *)data == 0xFFFFFFFFFFFFFFFF) {
                strcpy(tx_buf, "DATAOUT_DONE\n");
                len = strlen(tx_buf);
            } else {
                // It's not the full 64-bit Fs, so it must be the START signal
                strcpy(tx_buf, "COUNTSTART\n");
                len = strlen(tx_buf);
            }
        }

        int sent = 0;
        while (sent < len) {
            int ret = uart_fifo_fill(uart, (uint8_t *)tx_buf + sent, len - sent);
            if (ret > 0) {
                sent += ret;
            }
        }
        
        LOG_INF("--- TEST DATA RECEIVED FROM PATCH ---");
        LOG_INF("DATAOUT: 0x%07X, TS: %08X", pkt.dataout, pkt.timestamp);
        LOG_INF("------------------------------------");
    } else {
        LOG_WRN("Unexpected DATAOUT length: %u", length);
    }

    return BT_GATT_ITER_CONTINUE;
}

static uint8_t al_read_response(struct bt_conn *conn, uint8_t err,
                                        struct bt_gatt_read_params *params,
                                        const void *data, uint16_t length)
{   
    if (err) {
        LOG_ERR("AL Read failed: %u \n", err);
        return BT_GATT_ITER_STOP;
    }

    if (!data) {
        LOG_WRN("No AL data \n"); 
        return BT_GATT_ITER_STOP;
    }

    al_counter = *(uint32_t *)data;
    LOG_INF("AL READ SUCCESS: %u \n", al_counter);

    // send the dlal values 
    char tx_buf[64];
    int len = snprintf(tx_buf, sizeof(tx_buf), "DLAL_RESP:%u,%u\n", dl_counter, al_counter);
    int sent = 0;
    while (sent < len) {
        int ret = uart_fifo_fill(uart, (uint8_t *)tx_buf + sent, len - sent);
        if (ret > 0) {
            sent += ret;
        }
    }

    return BT_GATT_ITER_STOP;
} 

static uint8_t dl_read_response(struct bt_conn *conn, uint8_t err,
                                        struct bt_gatt_read_params *params,
                                        const void *data, uint16_t length)
{   
    if (err) {
        LOG_ERR("DL Read failed: %u \n", err);
        return BT_GATT_ITER_STOP;
    }

    if (!data) {
        LOG_WRN("No DL data \n"); 
        return BT_GATT_ITER_STOP;
    }

    dl_counter = *(uint32_t *)data;
    LOG_INF("DL READ SUCCESS: %u \n", dl_counter);

    int slot = get_slot_from_conn(conn);
    if (slot != -1) {
        al_read(slot); 
    }

    return BT_GATT_ITER_STOP;
}

static uint8_t dataout_read_response(struct bt_conn *conn, uint8_t err,
                                        struct bt_gatt_read_params *params,
                                        const void *data, uint16_t length)
{   
    if (err) {
        LOG_ERR("DATAOUT Read failed: %u \n", err);
        return BT_GATT_ITER_STOP;
    }

    if (!data) {
        LOG_WRN("No DATAOUT data \n"); 
        return BT_GATT_ITER_STOP;
    }

    const uint8_t *b = (const uint8_t *)data; 
    uint32_t raw_val = (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3];
    
    data_deq_0 = (uint16_t)(raw_val & 0xFFFF);         // bits 15:0
    data_deq_1 = (uint16_t)((raw_val >> 16) & 0x03FF); // buts 25:16 

    LOG_INF("GUI Update -> DEQ_0: 0x%04X, DEQ_1: 0x%03X", data_deq_0, data_deq_1);

    return BT_GATT_ITER_STOP;
}

static uint8_t count_status_read_response(struct bt_conn *conn, uint8_t err,
                                        struct bt_gatt_read_params *params,
                                        const void *data, uint16_t length)
{   
    if (err) {
        LOG_ERR("Count status Read failed: %u \n", err);
        return BT_GATT_ITER_STOP;
    }

    if (!data) {
        LOG_WRN("No count status data \n"); 
        return BT_GATT_ITER_STOP;
    }

    if (length == sizeof(struct count_status_packet)) {
        struct count_status_packet status_pkt;  
        memcpy(&status_pkt, data, sizeof(status_pkt));
        uint32_t counts = status_pkt.counts; 
        uint32_t curr_time = status_pkt.curr_time; 
        
        for (int i = 0; i < 1; i++) {          
            uint32_t current_dataout = (uint32_t)status_pkt.dt[i].dataout;
            uint32_t current_ts = (uint32_t)status_pkt.dt[i].timestamp;

            // I need to process dataout --> need to change for more than one patch
            char tx_buf[64];
            int len = snprintf(tx_buf, sizeof(tx_buf), "COUNTSTATUS:%d,%u,%u,%u,%u\n", // need to change this in GUI
                            board_address, counts, curr_time, current_dataout, current_ts);

            int sent = 0;
            while (sent < len) {
                int ret = uart_fifo_fill(uart, (uint8_t *)tx_buf + sent, len - sent);
                if (ret > 0) {
                    sent += ret;
                }
            }
            LOG_INF("--- TEST DATA RECEIVED FROM PATCH ---");
            LOG_INF("DATAOUT: 0x%07X, TS: %lu", current_dataout, current_ts);
            LOG_INF("Counts: 0x%07X", counts);
            LOG_INF("------------------------------------");
        }

    } else {
        LOG_WRN("Unexpected COUNTSTATUS length: %u", length);
    }

    return BT_GATT_ITER_STOP;
}

void al_read(int slot) {
    if (slot < 0 || !current_conn[slot]) return;

    al_read_params[slot].func = al_read_response;
    al_read_params[slot].handle_count = 1;
    al_read_params[slot].single.handle = patch_handle[slot].al; 
    al_read_params[slot].single.offset = 0;

    bt_gatt_read(current_conn[slot], &al_read_params[slot]);
}

void dl_read(int slot) {
    if (slot < 0 || !current_conn[slot]) return;
    
    dl_read_params[slot].func = dl_read_response;
    dl_read_params[slot].handle_count = 1;
    dl_read_params[slot].single.handle = patch_handle[slot].dl; 
    dl_read_params[slot].single.offset = 0;

    bt_gatt_read(current_conn[slot], &dl_read_params[slot]);
}

void dataout_read(int slot) {
    if (slot < 0 || !current_conn[slot]) return;

    dataout_read_params[slot].func = dataout_read_response;
    dataout_read_params[slot].handle_count = 1;
    dataout_read_params[slot].single.handle = patch_handle[slot].dataout_data;
    dataout_read_params[slot].single.offset = 0;

    bt_gatt_read(current_conn[slot], &dataout_read_params[slot]);
}

void count_status_read(int slot) {
    if (slot < 0 || !current_conn[slot]) return;

    count_status_read_params[slot].func = count_status_read_response;
    count_status_read_params[slot].handle_count = 1;
    count_status_read_params[slot].single.handle = patch_handle[slot].count_status; 
    count_status_read_params[slot].single.offset = 0;
    LOG_INF("count_status_read for: %d", slot); 
    bt_gatt_read(current_conn[slot], &count_status_read_params[slot]);
}


void write_sipo(uint16_t s7, uint16_t s6, uint16_t s5, uint16_t s4, 
                             uint16_t s3, uint16_t s2, uint16_t s1, uint16_t s0, int slot)
{   
    uint8_t outgoing_sipo[16];
    
    outgoing_sipo[0]  = (uint8_t)(s7 >> 8);
    outgoing_sipo[1]  = (uint8_t)(s7 & 0xFF);
    outgoing_sipo[2]  = (uint8_t)(s6 >> 8);
    outgoing_sipo[3]  = (uint8_t)(s6 & 0xFF);
    outgoing_sipo[4]  = (uint8_t)(s5 >> 8);
    outgoing_sipo[5]  = (uint8_t)(s5 & 0xFF);
    outgoing_sipo[6]  = (uint8_t)(s4 >> 8);
    outgoing_sipo[7]  = (uint8_t)(s4 & 0xFF);
    outgoing_sipo[8]  = (uint8_t)(s3 >> 8);
    outgoing_sipo[9]  = (uint8_t)(s3 & 0xFF); 
    outgoing_sipo[10] = (uint8_t)(s2 >> 8);
    outgoing_sipo[11] = (uint8_t)(s2 & 0xFF);
    outgoing_sipo[12] = (uint8_t)(s1 >> 8);
    outgoing_sipo[13] = (uint8_t)(s1 & 0xFF);
    outgoing_sipo[14] = (uint8_t)(s0 >> 8);
    outgoing_sipo[15] = (uint8_t)(s0 & 0xFF);

    if (current_conn[slot] && patch_handle[slot].sipo_data != 0) {
        bt_gatt_write_without_response(current_conn[slot], patch_handle[slot].sipo_data, 
                                       outgoing_sipo, sizeof(outgoing_sipo), false);
    }
}

void write_dac(uint16_t d2, uint16_t d1, uint16_t d0, int slot)
{
    uint8_t payload[5];

    /* * Packaging to match Patch logic:
     * Patch does: (data[0]<<28) | (data[1]<<20) | (data[2]<<12) | (data[3]<<4) | (data[4]>>4)
     * This equals 36 bits total.
     */

    payload[0] = (uint8_t)(d2 >> 8);         // d2 bits [15:8]
    payload[1] = (uint8_t)(d2 & 0xFF);       // d2 bits [7:0]
    payload[2] = (uint8_t)(d1 >> 8);         // d1 bits [15:8]
    payload[3] = (uint8_t)(d1 & 0xFF);       // d1 bits [7:0]
    payload[4] = (uint8_t)(d0 & 0xF0);       // d0 top 4 bits [15:12] -> payload[4] upper nibble

    if (current_conn[slot] && patch_handle[slot].dac_data != 0) {
        int err = bt_gatt_write_without_response(current_conn[slot], patch_handle[slot].dac_data, 
                                                 payload, sizeof(payload), false);
        if (err) {
            LOG_ERR("DAC Write Failed (err %d)", err);
        } else {
            LOG_INF("DAC Write Sent: d2=0x%04X, d1=0x%04X, d0_top=0x%X", d2, d1, (d0 >> 12));
        }
    } else {
        LOG_WRN("Cannot write DAC for %d: No connection or handle", slot);
    }
}

void write_sys_cmd(uint8_t command, int slot)
{
    if (current_conn[slot] && patch_handle[slot].syscmd != 0) {
        int err = bt_gatt_write_without_response(current_conn[slot], patch_handle[slot].syscmd, 
                                                 &command, sizeof(command), false);
        if (err) {
            LOG_ERR("SysCmd 0x%02X failed (err %d)", command, err);
        } else {
            LOG_INF("SysCmd Sent: 0x%02X", command);
        }
    } else {
        LOG_WRN("Cannot send SysCmd: No connection or handle");
    }
} 



/* BLE Connection Functions ------------------------------------------------------------------*/
static bool parse_ad_cb(struct bt_data *data, void *user_data) {
    static bool is_spect_device = false; 

    // Only look at 128-bit UUID blocks
    if (data->type == BT_DATA_UUID128_ALL) {
        struct bt_uuid_128 found_uuid;
        // Create UUID from raw bytes
        bt_uuid_create(&found_uuid.uuid, data->data, data->data_len);

        // Compare with your global SPECT_BASE_UUID
        if (bt_uuid_cmp(&found_uuid.uuid, &spect_uuid.uuid) == 0) {
            is_spect_device = true; 
            //LOG_INF("uuid found"); 
            return true; 
        }
    } 

    //LOG_INF("parse_ad_cb"); 
    
    if (is_spect_device && (data->type == BT_DATA_NAME_COMPLETE)) {
        // Verify the prefix "SPECT_PATCH" (11 characters)
        if (data->data_len >= 11 && strncmp(data->data, "SPECT_PATCH", 11) == 0) {
            //LOG_INF(" -> String: %.*s", data->data_len, data->data); 
            // Extract the ID from the 12th character (index 11)
            if (data->data_len > 11) {
                found_patch_id = data->data[11] - '0';
            } else {
                found_patch_id = 0; // Default if no number suffix
            }

            found_target = true;
            is_spect_device = false; // Reset the flag for the next device we scan
            
            //LOG_INF("Success! Found SPECT Patch ID: %d", found_patch_id);
            
            // Stop parsing this device; we found what we need
            return false; 
        }
    }
       

    return true;


    // struct bt_uuid_128 found_uuid;
    // // Create UUID from raw bytes
    // bt_uuid_create(&found_uuid.uuid, data->data, data->data_len);

    // // Compare with your global SPECT_BASE_UUID
    // if (bt_uuid_cmp(&found_uuid.uuid, &spect_uuid.uuid) == 0) {
    //     found_target = true; 
    //     return false; // Found it! Stop parsing.
    // }

    // found_target = true; 
    // return false; // Found it! Stop parsing.

    // return true;
}

void device_found(const bt_addr_le_t *addr, int8_t rssi, uint8_t type,
                         struct net_buf_simple *ad)
{   
    if (is_connecting || connected_patches >= patch_num) {
        return; 
    }

    found_patch_id = -1;
    found_target = false; 
    bt_data_parse(ad, parse_ad_cb, NULL);

    if (found_target && found_patch_id != -1) {
        int slot = found_patch_id; 
        
        //LOG_INF("found_patch_id: %d", found_patch_id); 

        if (slot >= MAX_PATCHES) {
            LOG_WRN("Found PATCH%d, but MAX_PATCHES is %d. Ignoring.", slot, MAX_PATCHES);
            return;
        } 

        if (current_conn[slot] == NULL) {
            is_connecting = true; 
            // STEP 1: Stop scanning to prioritize the connection handshake
            bt_le_scan_stop();
            //LOG_INF("Stopped scanning to connect to Patch %d", slot);

            // STEP 2: Create the connection
            int err = bt_conn_le_create(addr, BT_CONN_LE_CREATE_CONN, 
                                            BT_LE_CONN_PARAM_DEFAULT, &current_conn[slot]);
            if (err) {
                printk("Create conn failed (err %d)\n", err);
                is_connecting = false; 
                // Restart scanning if the attempt failed immediately
                bt_le_scan_start(&scan_param, device_found);
            }
        }
        

        // if (current_conn[slot] != NULL) {
        //         return; 
        // }

        // //bt_le_scan_stop();

        // // Create the connection
        // int err = bt_conn_le_create(addr, BT_CONN_LE_CREATE_CONN, 
        //                                 BT_LE_CONN_PARAM_DEFAULT, &current_conn[slot]);
        // if (err) {
        //         printk("Create conn failed (err %d)\n", err);
        //         bt_le_scan_start(NULL, device_found);
        // }
    }
    // Stop scanning so we can focus on connecting
}

static uint8_t discover_ccc_dataout_func(struct bt_conn *conn,
                                 const struct bt_gatt_attr *attr,
                                 struct bt_gatt_discover_params *params)
{
    int slot = get_slot_from_conn(conn);
    if (!attr || slot == -1) return BT_GATT_ITER_STOP;

    // We found the CCCD!
    patch_handle[slot].dataout_notify = attr->handle;
    LOG_INF("Found DATAOUT CCCD Handle: 0x%04X", patch_handle[slot].dataout_notify);
    // Step 3: Now that we have the handle, turn on notifications
    //uint16_t value = 0x0001; // 0x0001 = Notifications, 0x0002 = Indications

    dataout_sub_params[slot].value_handle = patch_handle[slot].dataout_data; // The characteristic value handle
    dataout_sub_params[slot].ccc_handle = patch_handle[slot].dataout_notify; // The CCCD handle we just found
    dataout_sub_params[slot].notify = dataout_notify_cb;         // The callback function above
    dataout_sub_params[slot].value = BT_GATT_CCC_NOTIFY;

    int err = bt_gatt_subscribe(conn, &dataout_sub_params[slot]);
    if (err) {
        LOG_ERR("Subscription failed (err %d)", err);
    }

    //bt_gatt_write_without_response(conn, sramout_notify_handle, &value, sizeof(value), false);
    LOG_INF("Notifications enabled for DATAOUT");

    if (connected_patches < patch_num) {
        LOG_INF("Patch %d setup complete. Resuming scan for next device...", slot);
        
        // Use the same scan_param you defined earlier
        int err = bt_le_scan_start(&scan_param, device_found);
        if (err) {
            LOG_ERR("Scanning failed to resume (err %d)", err);
        }
    }

    return BT_GATT_ITER_STOP;
}

static uint8_t discover_ccc_sramout_func(struct bt_conn *conn,
                                 const struct bt_gatt_attr *attr,
                                 struct bt_gatt_discover_params *params)
{
    int slot = get_slot_from_conn(conn);
    if (!attr || slot == -1) return BT_GATT_ITER_STOP;

    // We found the CCCD!
    patch_handle[slot].sramout_notify = attr->handle;
    LOG_INF("Found SRAMOUT CCCD Handle: 0x%04X", patch_handle[slot].sramout_notify);
    // Step 3: Now that we have the handle, turn on notifications
    //uint16_t value = 0x0001; // 0x0001 = Notifications, 0x0002 = Indications

    sramout_sub_params[slot].value_handle = patch_handle[slot].sramout_data; // The characteristic value handle
    sramout_sub_params[slot].ccc_handle = patch_handle[slot].sramout_notify; // The CCCD handle we just found
    sramout_sub_params[slot].notify = sramout_notify_cb;         // The callback function above
    sramout_sub_params[slot].value = BT_GATT_CCC_NOTIFY;

    int err = bt_gatt_subscribe(conn, &sramout_sub_params[slot]);
    if (err) {
        LOG_ERR("Subscription failed (err %d)", err);
    }

    //bt_gatt_write_without_response(conn, sramout_notify_handle, &value, sizeof(value), false);
    LOG_INF("Notifications enabled for SRAMOUT");

    ccc_params[slot].func = discover_ccc_dataout_func;
    ccc_params[slot].start_handle = patch_handle[slot].dataout_data + 1;
    bt_gatt_discover(conn, &ccc_params[slot]);

    return BT_GATT_ITER_STOP;
}

static uint8_t discover_ccc_dac_func(struct bt_conn *conn,
                                 const struct bt_gatt_attr *attr,
                                 struct bt_gatt_discover_params *params)
{
    int slot = get_slot_from_conn(conn);
    if (!attr || slot == -1) return BT_GATT_ITER_STOP;

    // We found the CCCD!
    patch_handle[slot].dac_notify = attr->handle;
    LOG_INF("Found DAC CCCD Handle: 0x%04X", patch_handle[slot].dac_notify);
    // Step 3: Now that we have the handle, turn on notifications
    //uint16_t value = 0x0001; // 0x0001 = Notifications, 0x0002 = Indications
 
    dac_sub_params[slot].value_handle = patch_handle[slot].dac_data; // The characteristic value handle
    dac_sub_params[slot].ccc_handle =patch_handle[slot].dac_notify; // The CCCD handle we just found
    dac_sub_params[slot].notify = dac_notify_cb;         // The callback function above
    dac_sub_params[slot].value = BT_GATT_CCC_NOTIFY;

    int err = bt_gatt_subscribe(conn, &dac_sub_params[slot]);
    if (err) {
        LOG_ERR("Subscription failed (err %d)", err);
    }

    //bt_gatt_write_without_response(conn, dac_notify_handle, &value, sizeof(value), false);
    LOG_INF("Notifications enabled for DAC");
    
    // next ccc discovery
    ccc_params[slot].func = discover_ccc_sramout_func;
    ccc_params[slot].start_handle = patch_handle[slot].sramout_data + 1;
    bt_gatt_discover(conn, &ccc_params[slot]);

    return BT_GATT_ITER_STOP;
}

static uint8_t discover_ccc_sipo_func(struct bt_conn *conn,
                                 const struct bt_gatt_attr *attr,
                                 struct bt_gatt_discover_params *params)
{   
    int slot = get_slot_from_conn(conn);
    if (!attr || slot == -1) return BT_GATT_ITER_STOP;

    // if (!attr) {
    //     LOG_INF("SIPO CCCD discovery ended \n");
    //     return BT_GATT_ITER_STOP;
    // }

    // Manually check if the descriptor found is the CCCD
    if (bt_uuid_cmp(attr->uuid, BT_UUID_GATT_CCC) == 0) {
        patch_handle[slot].sipo_notify = attr->handle;
        LOG_INF("Found SIPO CCCD Handle: 0x%04X", patch_handle[slot].sipo_notify);

        sipo_sub_params[slot].value_handle = patch_handle[slot].sipo_data;
        sipo_sub_params[slot].ccc_handle = patch_handle[slot].sipo_notify;
        sipo_sub_params[slot].notify = sipo_notify_cb;
        sipo_sub_params[slot].value = BT_GATT_CCC_NOTIFY;

        int err = bt_gatt_subscribe(conn, &sipo_sub_params[slot]);
        if (err) {
            LOG_ERR("Subscription failed (err %d)", err);
        } else {
            LOG_INF("Notifications enabled for SIPO");
        }

        // CHAIN TO NEXT: Start DAC CCCD Discovery
        ccc_params[slot].uuid = NULL; 
        ccc_params[slot].func = discover_ccc_dac_func;
        ccc_params[slot].start_handle = patch_handle[slot].dac_data + 1;
        bt_gatt_discover(conn, &ccc_params[slot]);

        return BT_GATT_ITER_STOP; // We found what we wanted, stop this iteration
    }

    return BT_GATT_ITER_CONTINUE;
}

void start_ccc_discovery(struct bt_conn *conn) {
    int slot = get_slot_from_conn(conn);
    if (slot == -1 || patch_handle[slot].sipo_data == 0) {
        LOG_ERR("Cannot start CCC discovery for slot %d", slot);
        return;
    }

    LOG_INF("Starting CCCD discovery at handle 0x%04X", patch_handle[slot].sipo_data + 1);

    ccc_params[slot].uuid = NULL;
    ccc_params[slot].func = discover_ccc_sipo_func; // Start with SIPO
    ccc_params[slot].start_handle = patch_handle[slot].sipo_data + 1;
    ccc_params[slot].end_handle = BT_ATT_LAST_ATTRIBUTE_HANDLE;
    ccc_params[slot].type = BT_GATT_DISCOVER_DESCRIPTOR;
    int err = bt_gatt_discover(conn, &ccc_params[slot]);
    if (err) {
        LOG_ERR("CCCD Discovery failed to start (err %d)", err);
    }
}

static uint8_t discover_func(struct bt_conn *conn,
                             const struct bt_gatt_attr *attr,
                             struct bt_gatt_discover_params *params)
{   
    int slot = get_slot_from_conn(conn);
    if (slot == -1) return BT_GATT_ITER_STOP;

    if (!attr) {
        LOG_INF("[Slot %d] Discovery finished. Now Finding CCCDs...", slot);
        start_ccc_discovery(conn);
        return BT_GATT_ITER_STOP;
    }

    struct bt_gatt_chrc *chrc = (struct bt_gatt_chrc *)attr->user_data;

    // SIPO Characteristic
    if (bt_uuid_cmp(chrc->uuid, &sipo_uuid.uuid) == 0) {
        patch_handle[slot].sipo_data = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found SIPO Handle: 0x%04X", patch_handle[slot].sipo_data);
    } 
    else if (bt_uuid_cmp(chrc->uuid, &dac_uuid.uuid) == 0) {
        patch_handle[slot].dac_data = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found DAC Handle: 0x%04X", patch_handle[slot].dac_data);
    }
    else if (bt_uuid_cmp(chrc->uuid, &sramout_uuid.uuid) == 0) {
        patch_handle[slot].sramout_data = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found SRAMOUT Handle: 0x%04X", patch_handle[slot].sramout_data);
    } 
    else if (bt_uuid_cmp(chrc->uuid, &al_uuid.uuid) == 0) {
        patch_handle[slot].al = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found AL Handle: 0x%04X", patch_handle[slot].al);
    }
    else if (bt_uuid_cmp(chrc->uuid, &dl_uuid.uuid) == 0) {
        patch_handle[slot].dl = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found DL Handle: 0x%04X", patch_handle[slot].dl);
    }
    else if (bt_uuid_cmp(chrc->uuid, &dataout_uuid.uuid) == 0) {
        patch_handle[slot].dataout_data = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found DATAOUT Handle: 0x%04X", patch_handle[slot].dataout_data);
    }
    else if (bt_uuid_cmp(chrc->uuid, &syscmd_uuid.uuid) == 0) {
        patch_handle[slot].syscmd = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found SYSCMD Handle: 0x%04X", patch_handle[slot].syscmd );
    } 
    else if (bt_uuid_cmp(chrc->uuid, &count_status_uuid.uuid) == 0) {
        patch_handle[slot].count_status = bt_gatt_attr_value_handle(attr);
        LOG_INF("Found COUNTSTATUS Handle: 0x%04X", patch_handle[slot].count_status);
    }

    return BT_GATT_ITER_CONTINUE; 
}

void on_connected(struct bt_conn *conn, uint8_t err)
{   
    is_connecting = false; 

    LOG_INF("on_connected started"); 
    int slot = get_slot_from_conn(conn);

    if (err) {
        LOG_ERR("Connection failed (err %u)", err);
        //int slot = get_slot_from_conn(conn);
        if (slot != -1) current_conn[slot] = NULL;
        bt_le_scan_start(&scan_param, device_found);
        return;
    }

    if (slot == -1) {
        LOG_ERR("Received connection for unknown slot!");
        bt_le_scan_start(&scan_param, device_found);
        return;
    }

    LOG_INF("Connected! Finding SIPO handle...");
    connected_patches++; 
    current_conn[slot] = bt_conn_ref(conn);

    // Setup discovery to find CHARACTERISTICS
    discover_params[slot].uuid = NULL; // Discover all to see everything
    discover_params[slot].func = discover_func; // The "Inspector" function (Step 3)
    discover_params[slot].start_handle = BT_ATT_FIRST_ATTRIBUTE_HANDLE;
    discover_params[slot].end_handle = BT_ATT_LAST_ATTRIBUTE_HANDLE;
    discover_params[slot].type = BT_GATT_DISCOVER_CHARACTERISTIC;

    int disc_err = bt_gatt_discover(conn, &discover_params[slot]);
    if (disc_err) {
        LOG_ERR("Discovery failed to start (err %d)", disc_err);
    }

    // if (connected_patches < patch_num) {
    //     bt_le_scan_start(&scan_param, device_found);
    // }
}

static void on_disconnected(struct bt_conn *conn, uint8_t reason)
{
    int slot = get_slot_from_conn(conn);
    LOG_INF("Disconnected Slot %d (reason %u)", slot, reason);

    //LOG_INF("Disconnected (reason %u)", reason);
    
    if (slot != -1) {
        bt_conn_unref(current_conn[slot]);
        current_conn[slot] = NULL;
        memset(&patch_handle[slot], 0, sizeof(struct patch_handles));
        connected_patches--; 
    }

    // Reset handles so we don't try to write to a dead connection

    // sipo_data_handle = 0;
    // dac_data_handle = 0; 
    // sramout_data_handle = 0;
    // al_data_handle = 0; 
    // dl_data_handle = 0;
    // dataout_data_handle = 0; 
    // syscmd_data_handle = 0;
    // count_status_data_handle = 0; 

    // Start scanning again to find the Patch
    if (connected_patches < patch_num) {
        bt_le_scan_start(&scan_param, device_found);
    }
    
    //bt_le_scan_start(&scan_param, device_found);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
    .connected = on_connected,
    .disconnected = on_disconnected, // You'll want to add this to restart scanning
};