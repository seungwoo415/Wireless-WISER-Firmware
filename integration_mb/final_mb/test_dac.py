import serial, time, queue, threading

ser = serial.Serial('/dev/cu.usbmodem101', 115200, timeout=0)

# Critical Mac/Zephyr handshake
ser.dtr = True
ser.rts = True

time.sleep(1.0)

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


def SIPO_data_in(sipo_data0, sipo_data1, sipo_data2, sipo_data3, sipo_data4, sipo_data5, sipo_data6, sipo_data7): 

    cmd = f"SIPO:{sipo_data7:04X},{sipo_data6:04X},{sipo_data5:04X},{sipo_data4:04X},{sipo_data3:04X},{sipo_data2:04X},{sipo_data1:04X},{sipo_data0:04X}\n"
    ser.write(cmd.encode('ascii'))

    try:
        input_queues["SIPO_DONE"].get(timeout=5)
        print(f"SIPO done{i} received!")
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

        return SRAMout
    except queue.Empty:
        print("SRAM Timeout!")
        return 0

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

def bitIdx(num, k, p):
    binary = format(num, '016b')
    end = len(binary) - p
    start = len(binary) - 1 - k
    binrep = binary[start:end]
    return int(binrep, 2)


def dacIn(inputval, dacop, dac, addr, vref):
    val_in = int(inputval / vref * 65536)
    analogWireIn_2 = (addr << 9) + (dacop << 3) + bitIdx(dac, 3, 1)
    analogWireIn_1 = (bitIdx(dac, 0, 0) << 15) + (bitIdx(val_in, 15, 8) << 6) + bitIdx(val_in, 7, 3)
    analogWireIn_0 = bitIdx(val_in, 2, 0) << 13
    return (analogWireIn_2, analogWireIn_1, analogWireIn_0)

# if __name__ == "__main__":
#     time.sleep(1) 
    
#     print("--- START ---") 

#     inputval_dac = 1200 # DAC output is 0.9 V
#     dacop_dac = 3 # table 1 COMMAND, always 3 for us 
#     which_addr = 18 # 16 for DAC1 18 for DAC2
#     which_dac = 0
#     vref_dac = 3300 

#     print(f"Calculating I2C payload for {inputval_dac}mV on DAC (A/B/C..) {which_dac} in DAC addr (DAC1/2) {which_addr}")

#     # Calculate the 3 Wire Values
#     v2, v1, v0 = dacIn(inputval_dac, dacop_dac, which_dac, which_addr, vref_dac)
#     bitstream = format(v2, '016b') + format(v1, '016b') + format(v0, '016b')
#     print(f"SDA: {bitstream}")

#     # send DAC values 
#     DAC_data_in(v2, v1, v0) 

#     print("Script Complete.")

#     cmd = f"CH_RST\n"
#     ser.write(cmd.encode('ascii'))

if __name__ == "__main__":
    time.sleep(1) 
    
    print("--- START ---") 

    dacop_dac = 3
    which_addr = 18
    vref_dac = 3300
    
    # user inputs 
    vdd_vals = [(0, 1200), (1, 600), (2, 1200), (3, 1200), (4, 2200)] 
    afe_vals = [(0, 500), (1, 600), (2, 600), (3, 400), (4, 500), (5, 0), (6, 0), (7, 300)]
    afe_en = True 
    
    for wdac, ival in vdd_vals: 
        inputval_dac = ival
        which_dac = wdac 
        print(f"Calculating I2C payload for {inputval_dac}mV on DAC (A/B/C..) {which_dac} in DAC addr (DAC1/2) {which_addr}")

        # Calculate the 3 Wire Values
        v2, v1, v0 = dacIn(inputval_dac, dacop_dac, which_dac, which_addr, vref_dac)
        bitstream = format(v2, '016b') + format(v1, '016b') + format(v0, '016b')
        print(f"SDA: {bitstream}")

        # send DAC values 
        DAC_data_in(v2, v1, v0) 
        
        time.sleep(5) 

    if afe_en: 
        which_addr = 16
        for wdac, ival in afe_vals: 
            inputval_dac = ival
            which_dac = wdac 
            print(f"Calculating I2C payload for {inputval_dac}mV on DAC (A/B/C..) {which_dac} in DAC addr (DAC1/2) {which_addr}")

            # Calculate the 3 Wire Values
            v2, v1, v0 = dacIn(inputval_dac, dacop_dac, which_dac, which_addr, vref_dac)
            bitstream = format(v2, '016b') + format(v1, '016b') + format(v0, '016b')
            print(f"SDA: {bitstream}")

            # send DAC values 
            DAC_data_in(v2, v1, v0) 
            
            time.sleep(5)
    
    cmd = f"CH_RST\n"
    ser.write(cmd.encode('ascii'))
    
    time.sleep(5) 

    print("Script Complete.")

'''
On DAC1 (addr 16)
A - VbDL
B - VbAL
C - VgtailMain
D - LSTop
E - LSBot
F - GD1
G - DACIN
H - DCLevel
On DAC2 (addr 18)
A - AVDDH 0 1200
B - AVDDL 1
C - DVDD 2 1400
D - VDDHSRAM 3 1200
E - AVDDHBUFF 4 1800
F - DAC_extra1 5 3200
G - NC
H - NC
'''