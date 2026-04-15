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


def writeToMain(clkSRAM, clkPISO, clkaddr, clkcnt, lsdacenval):
    '''
    clkSRAM = 1 # can replace with just some number - these are two bit numbers (except clk cnt 3 which is 3 bit), allowed values in  cnt clk_mux.v
    clkPISO = 1 # same as above
    clkaddr = 1 # same as above
    clkcnt = 1 # same as above
    lsdacenval = 1 # lsdacen = tk.Checkbutton(text='LS_DAC_EN', variable=lsdacenvar, onvalue=1, offvalue=0).grid(row=rmain + 11, column=4, sticky='e', pady=2) - so it this just a boolean value? yes enable
    '''
    mainWriteWireIn = 1024 + (lsdacenval << 9) + (clkSRAM << 7) + (clkPISO << 5) + (clkaddr << 3) + clkcnt << 5 # what is the size of each? each wire is 16 bits in total LS_DAC_EN <= data[9]; 
    # note that the << 5 at the very end is for the whole string - we concatenate 11 bits and then puth them to the left by 5 to make it 16 bits to send to wire 7
    '''
    from reg_bank.v
    reg_clk_cnt <= data[2:0]; // reg_clk_cnt is the input to clk_mux in dig_top.v
	reg_clk_addr <= data[4:3]; 
	reg_clk_piso <= data[6:5]; 
	reg_clk_SRAM <= data[8:7];
    '''
    SIPO_data_in(0, 0, 0, 0, 0, 0, 0, mainWriteWireIn)
    print(f"Sending Configuration: {bin(mainWriteWireIn)}")
    
    return



if __name__ == "__main__":
    time.sleep(1)
    # RESET
    cmd = f"CH_RST\n"
    ser.write(cmd.encode('ascii'))

    time.sleep(4)

    # C. Define Inputs Here (Change these values to configure)
    input_clkSRAM  = 1  # Range: 0,1,2,3     0 is too fast, 1 only works with RTT on, 2 and 3 work 
    input_clkPISO  = 3  # Range: 0,1,2,3
    input_clkaddr  = 0   # Range: 0,1,2,3
    input_clkcnt   = 1   # Range: 0,1,2,3,8
    input_lsdacen  = 1   # Range: 0 or 1

    # D. Write Configuration to Main
    writeToMain(input_clkSRAM, input_clkPISO, input_clkaddr, input_clkcnt, input_lsdacen)

