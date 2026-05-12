#include <zephyr/kernel.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/fs/nvs.h>
#include <zephyr/sys/printk.h>
#include <zephyr/usb/usb_device.h>
#include <zephyr/logging/log.h>

#include <zephyr/drivers/flash.h>

LOG_MODULE_REGISTER(main);

// external flash partitions
//#define NVS_PARTITION		 external_storage_partition 
//#define NVS_PARTITION_DEVICE	 FIXED_PARTITION_DEVICE(NVS_PARTITION)
//#define NVS_PARTITION_OFFSET	 FIXED_PARTITION_OFFSET(NVS_PARTITION) 

/* Get the node identifier for the partition label in your overlay */
#define FLASH_PARTITION_NODE DT_NODELABEL(external_storage_partition)

/* Use the DT_FLASH_AREA macros to get the device and offset */
#define FLASH_DEVICE DEVICE_DT_GET(DT_MTD_FROM_FIXED_PARTITION(FLASH_PARTITION_NODE))
#define FLASH_PARTITION_OFFSET DT_REG_ADDR(FLASH_PARTITION_NODE)
#define FLASH_BASE_OFFSET DT_REG_ADDR(FLASH_PARTITION_NODE)

// id for nvs (each data == id) 
#define FLASH_TOTAL_SIZE  (512 * 4096)

static uint32_t current_write_offset = 0;

// static struct nvs_fs fs = {
// 	.flash_device = NVS_PARTITION_DEVICE,
// 	.offset = NVS_PARTITION_OFFSET,
//         .sector_size = 4096, 
//         .sector_count = 512,
// };

int main(void) {
        int err; 

        if (!device_is_ready(FLASH_DEVICE)) {
                LOG_INF("Flash device is not ready\n");
                return 0;
        }

        LOG_INF("Erasing flash for experiment...");
        err = flash_erase(FLASH_DEVICE, FLASH_BASE_OFFSET, FLASH_TOTAL_SIZE);
        if (err) {
                LOG_ERR("Flash erase failed: %d", err);
                return 0;
        }

        // array to be stored 
        int arr[5] = {85, 92, 78, 95, 88};
        
        // write the array 
        err = flash_write(FLASH_DEVICE, FLASH_BASE_OFFSET + current_write_offset, arr, sizeof(arr)); 
        if (err < 0) {
                LOG_ERR("flash_write failed");
        }
        current_write_offset = current_write_offset + sizeof(arr);  
        
        int read_buf[5]; 
        /// read the array
        err = flash_read(FLASH_DEVICE, FLASH_BASE_OFFSET, read_buf, sizeof(read_buf)); 
        if (err < 0) {
                LOG_ERR("flash_read failed"); 
        } else {
                LOG_INF("read data1: %d %d %d %d %d", arr[0], arr[1], arr[2],  arr[3], arr[4]); 
        }

        // modify the array
        arr[0] = 20;

        // write the array 
        err = flash_write(FLASH_DEVICE, FLASH_BASE_OFFSET + current_write_offset, arr, sizeof(arr)); 
        if (err < 0) {
                LOG_ERR("flash_write failed");
        }
        uint32_t prev_offset = current_write_offset; 
        current_write_offset = current_write_offset + sizeof(arr);

        /// read the array
        err = flash_read(FLASH_DEVICE, FLASH_BASE_OFFSET + prev_offset, read_buf, sizeof(read_buf)); 
        if (err < 0) {
                LOG_ERR("flash_read failed");
        } else {
                LOG_INF("modified read data2: %d %d %d %d %d", arr[0], arr[1], arr[2],  arr[3], arr[4]); 
        }

        return 0; 

}