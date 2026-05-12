/**
 * @file final_mb.h
 * @author Archie Lee
 * @brief Header file for motherboard.
 * @details Defines includes, data buffers, devices, and global variables.
 * @version 1.0
 * @date 2026-02-03
 */

#ifndef FINAL_PATCH_H
#define FINAL_PATCH_H

/* Includes ------------------------------------------------------------------*/
#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/gatt.h>
#include <zephyr/bluetooth/uuid.h>
#include <zephyr/logging/log.h>
#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/usb/usb_device.h>
#include <zephyr/sys/reboot.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Number of Patches ------------------------------------------------------------------*/
#define NUM_PATCHES 1

/* Global Data Buffers ------------------------------------------------------------------*/
extern uint16_t data_deq_0; 
extern uint16_t data_deq_1; 
extern uint32_t al_counter; 
extern uint32_t dl_counter; 
extern struct sramout_ble_packet ble_sramout_packet;
extern uint16_t dac2, dac1, dac0; 
extern uint16_t sipo7, sipo6, sipo5, sipo4, sipo3, sipo2, sipo1, sipo0;

extern uint8_t done_wr_sipo; 
extern uint8_t done_wr_dac; 
extern uint16_t SRAM_rd_reset; 
extern uint16_t dlal_reset; 
extern uint16_t data_rd_reset;
extern uint16_t sipo_reset; 

// for status count 
extern uint32_t status_count; 

extern uint16_t status_data_0; 
extern uint16_t status_data_1; 

extern uint16_t status_data_2; 
extern uint16_t status_data_3; 

extern uint16_t status_data_4; 
extern uint16_t status_data_5;

extern uint16_t status_data_6; 
extern uint16_t status_data_7; 

extern uint16_t status_data_8; 
extern uint16_t status_data_9;

extern uint16_t status_data_10; 
extern uint16_t status_data_11;

extern uint16_t status_data_12; 
extern uint16_t status_data_13;

extern uint16_t status_data_14; 
extern uint16_t status_data_15;

extern uint16_t status_data_16; 
extern uint16_t status_data_17;

extern uint16_t status_data_18; 
extern uint16_t status_data_19;


extern int board_address;

/* UART  ------------------------------------------------------------------*/
extern const struct device *uart; 

/* BLE Variables ------------------------------------------------------------------*/
extern struct bt_conn *current_conn;
extern const struct bt_data ad[2]; 
extern struct bt_le_scan_param scan_param;

struct __packed sramout_ble_packet {
    uint16_t SRAM_out0;
    uint16_t SRAM_out1;
    uint16_t SRAM_out2;
    uint16_t SRAM_out3;
    uint16_t SRAM_out4;
    uint16_t SRAM_out5;
    uint16_t SRAM_out6;
    uint16_t SRAM_out7;
    uint16_t SRAM_out8;
    uint16_t SRAM_out9;  
};

// struct __packed dataout_ble_packet {
//     uint32_t dataout; 
//     uint64_t timestamp; 
// }; // need to change 

struct __packed dataout_ble_packet {
    uint64_t dataout   : 26; // Your ASIC pulse width (26 bits)
    uint64_t reserved  : 6;  // Padding to reach exactly 64 bits (8 bytes) 
    uint64_t timestamp : 32; // Lower 32 bits of RTC (30.5us precision)
}; 

struct __packed count_status_packet {
    uint32_t counts; 
    uint32_t curr_time; 
    struct dataout_ble_packet dt[1];
};

/* K_WORK  ------------------------------------------------------------------*/
struct command_work_t {
    struct k_work work;
    char payload[128];
};

extern struct command_work_t process_command_work;

#ifdef __cplusplus
}
#endif

#endif /* FINAL_MB_H */