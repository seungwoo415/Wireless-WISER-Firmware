import serial, time, queue, threading

ser = serial.Serial('/dev/cu.usbmodem101', 115200, timeout=0)

# Critical Mac/Zephyr handshake
ser.dtr = True
ser.rts = True

time.sleep(1.0)

CRC = 1

dataout_queue = {i: queue.Queue() for i in range(16)}

input_queues = {
    "SIPO_DONE": queue.Queue(),
    "DAC_DONE":  queue.Queue(),
    "SRAMOUT": queue.Queue()
} 

i = 0 

def serial_listener():
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('ascii').strip()
            if not line: continue 

            if line.startswith("DATAOUT:"): 
                try: 
                    _, payload = line.split(":") 
                    board_id, val, ts = map(int, payload.split(",")) 
                    # use put because it is thread safe
                    dataout_queue[board_id].put((val, ts))
                    # test
                    #test_val, test_ts = dataout_queue[0].get() 
                    #print(test_val, test_ts)
                except: 
                    continue
            elif "SIPO_DONE" in line:
                input_queues["SIPO_DONE"].put(True)
            elif "DAC_DONE" in line:
                input_queues["DAC_DONE"].put(True)
            elif line.startswith("SRAMOUT:"):
                input_queues["SRAMOUT"].put(line)

# Start the listener
threading.Thread(target=serial_listener, daemon=True).start()

def bitIdxLong(num, k, p): # input is any number (255, 0xE6, 0b1100), converted to bits and then sliced - result = num[k:p]
    binary = format(num, '128b')
    binary = binary.replace(' ', '0')
    end = len(binary) - p
    start = len(binary) - k - 1
    binrep = binary[start:end]
    return int(binrep, 2)

def SIPO_data_in(sipo_data0, sipo_data1, sipo_data2, sipo_data3, sipo_data4, sipo_data5, sipo_data6, sipo_data7): 

    cmd = f"SIPO:{sipo_data7:04X},{sipo_data6:04X},{sipo_data5:04X},{sipo_data4:04X},{sipo_data3:04X},{sipo_data2:04X},{sipo_data1:04X},{sipo_data0:04X}\n"
    ser.write(cmd.encode('ascii'))

    try:
        input_queues["SIPO_DONE"].get(timeout=5)
        print(f"SIPO done received!")
    except queue.Empty:
        print("SIPO timeout!") 
    
    return

def DAC_data_in(dac_data2, dac_data1, dac_data0):    
    cmd = f"DAC:{dac_data2:04X},{dac_data1:04X},{dac_data0:04X}\n"

    ser.write(cmd.encode('ascii'))

    try: 
        input_queues["DAC_DONE"].get(timeout=5)
        print(f"DAC done{i} received!") 
    except queue.Empty: 
        print("DAC timeout!") 
    
    return 

def SRAM_data_out():
    SRAMout = 0
    try:
        # Get the actual string from the SRAM bucket
        raw_msg = input_queues["SRAMOUT"].get(timeout=5)
        
        raw_data = raw_msg.replace("SRAMOUT:", "").split(",")
        vals = [int(v, 16) for v in raw_data]
        SRAMout = (vals[6] << 96) + (vals[5] << 80) + (vals[4] << 64) + \
                      (vals[3] << 48) + (vals[2] << 32) + (vals[1] << 16) + vals[0]
        print(vals[7], raw_data[8], raw_data[9])
        return SRAMout
    except queue.Empty:
        print("SRAM Timeout!")
        return 0

def writeToSRAM(rowaddr,data,timing):
    global CRC 
    CRC = 0 if CRC == 1 else 1 # toggle CRC
    sramWriteWireIn = (1 << 124) + (rowaddr << 115) + (data << 5) + (timing << 1) + CRC << 2 # what is that awful number? 2^124 since write iop is 10
    sram0 = bitIdxLong(sramWriteWireIn, 15, 0)
    sram1 = bitIdxLong(sramWriteWireIn, 31, 16)
    sram2 = bitIdxLong(sramWriteWireIn, 47, 32)
    sram3 = bitIdxLong(sramWriteWireIn, 63, 48)
    sram4 = bitIdxLong(sramWriteWireIn, 79, 64)
    sram5 = bitIdxLong(sramWriteWireIn, 95, 80)
    sram6 = bitIdxLong(sramWriteWireIn, 111, 96)
    sram7 = bitIdxLong(sramWriteWireIn, 127, 112)
    SIPO_data_in(sram0, sram1, sram2, sram3, sram4, sram5, sram6, sram7)
    return

def readFromSRAM(rowaddr,data,timing): # why do we need to pass data here?
    global CRC
    CRC = 0 if CRC == 1 else 1 # toggle CRC
    sramWriteWireIn = (1 << 123) + (rowaddr << 115) + (data << 5) + (timing << 1) + CRC << 2 # what is that awful number? 2^123 since write iop is 01
    sram0 = bitIdxLong(sramWriteWireIn, 15, 0)
    sram1 = bitIdxLong(sramWriteWireIn, 31, 16)
    sram2 = bitIdxLong(sramWriteWireIn, 47, 32)
    sram3 = bitIdxLong(sramWriteWireIn, 63, 48)
    sram4 = bitIdxLong(sramWriteWireIn, 79, 64)
    sram5 = bitIdxLong(sramWriteWireIn, 95, 80)
    sram6 = bitIdxLong(sramWriteWireIn, 111, 96)
    sram7 = bitIdxLong(sramWriteWireIn, 127, 112)
    SIPO_data_in(sram0, sram1, sram2, sram3, sram4, sram5, sram6, sram7) 
    sram_rddata = SRAM_data_out()
    return bitIdxLong(sram_rddata, 109, 0)


def Main_data_out(i, boardAddress): 
    if i == 0:
        cmd = "DATAOUT_RST\n" # data_rd_reset
        ser.write(cmd.encode('ascii')) 

    dataout = 0
    timestamp = 0
    
    # check if boardAddress has at least one dataout 
    if not dataout_queue[boardAddress].empty(): 
        dataout, timestamp = dataout_queue[boardAddress].get()
 
    return dataout, timestamp

if __name__ == "__main__":
    time.sleep(1) 

    print("--- START ---")

    # set all srams to 0 
    # 76 rows in total but may need to account for test pixels 
    TEST_ROW = 0
    TEST_DATA = 0
    TEST_TIMING = 2
    for row in range(228): 
        TEST_ROW = row
        sucess = 0
        while not success: 
            writeToSRAM(TEST_ROW, TEST_DATA, TEST_TIMING) 
            time.sleep(0.5) 
            received_data = readFromSRAM(TEST_ROW, 0, TEST_TIMING) 
            if TEST_DATA == received_data: 
                success = 1

    # find the dac values 
    TEST_DATA = 0
    final_result = [] 
    DL = 0
    # bias each column in the row 
    for row_pix in range(76): 
        row_result = [0] * 110
        # enable mux 
        for col_pix in range(110): 
            found_threshold = False
            #dlal_reset
            for dac_val in range(1, 8):
                for wl in range(3): 
                    TEST_ROW = row_pix * 3 + wl
                    TEST_DATA = ((dac_val >> wl) & 1) << col_pix
                    writeToSRAM(TEST_ROW, TEST_DATA, TEST_TIMING)
                    time.sleep(0.5)
                    writeToSRAM(TEST_ROW, TEST_DATA, TEST_TIMING)
                # wait for 30 s before reading DL 
                time.sleep(30) 
                DL, AL = DL_ALValues()  
                if DL > 0: 
                    row_result[col_pix] = dac_val - 1
                    found_threshold = True
                    for wl in range(3):
                        writeToSRAM(row_pix * 3 + wl, 0, TEST_TIMING)
                        time.sleep(0.5)
                        writeToSRAM(row_pix * 3 + wl, 0, TEST_TIMING)
                    break 

            if not found_threshold: 
                row_result[col_pix] = 7
                for wl in range(3):
                    writeToSRAM(row_pix * 3 + wl, 0, TEST_TIMING)
                    time.sleep(0.5) 
                    writeToSRAM(row_pix * 3 + wl, 0, TEST_TIMING)

        final_result.append(row_result)
            
        
        

