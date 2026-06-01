# uncompyle6 version 3.9.3
# Python bytecode version base 2.7 (62211)
# Decompiled from: Python 3.13.7 (main, Aug 14 2025, 11:12:11) [Clang 15.0.0 (clang-1500.1.0.2.5)]
# Embedded file name: WearableSPECTGUI_RahulLall.py
import tkinter as tk
from tkinter import filedialog
from tkinter.filedialog import asksaveasfile
import tkinter.scrolledtext as st
from PIL import ImageTk, Image
import subprocess as sub
from scipy.io import savemat
import numpy as np, csv, random, threading, time, sys, math, signal
import serial, time, queue, threading
import serial.tools.list_ports
#from ctypes import windll [Archie] for windows
#windll.shcore.SetProcessDpiAwareness(1)
window = tk.Tk()
window.geometry('1700x2025')
wh = 2025
ww = 1700
mainDACSlave1 = 16
maintestDACSlave2 = 18
filenameo = ''
x = 0
position = 0
lsdacenvar = tk.IntVar()
avdddis_var = tk.IntVar()
dlalvar = tk.IntVar()
v = tk.IntVar()
CRC = 1
dlCounts = []
alCounts = []
dlCPS = []
alCPS = []
#addr_miss = []
#viol = []
#pw = []
#row = []
#col = []
cnts = []
dlval = []
dlrows = []
rowval_sweep = 0
#cnt = 0
#avgCnt = 0
#avgPW = 0
avgEn = 0
defConfig = []
#timeStamp = []
rowSRAM = []
rowCounter = 0
running = True
runningDLAL = True
flagwindow = True
recTime = 0
elapsed_time_main = 0
i = 0
start_time_main = 0
start_time_dlal = 0
last_int = 0
after_id = None
after_id_main = None
boardAddress = 0
boardAddressQuery = 0 
patchNum = 1

# [Archie] 
addr_miss = [[] for _ in range(patchNum)] 
avgCnt = [0 for _ in range(patchNum)]
avgPW = [0 for _ in range(patchNum)]
cnt = [0 for _ in range(patchNum)]
col = [[] for _ in range(patchNum)]
pw = [[] for _ in range(patchNum)]
row = [[] for _ in range(patchNum)]
timeStamp = [[] for _ in range(patchNum)]
viol = [[] for _ in range(patchNum)]

ser = None 
patch_read_done = False

def find_motherboard():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        # p.product will contain "SPECT_MB" thanks to prj.conf
        if p.product and "SPECT_MB" in p.product:
            return p.device
    return None

# [Archie]
def Connect_Device():  
    global ser
    try: 
        port_name = find_motherboard()
        if port_name: 
            ser = serial.Serial(port_name, 115200, timeout=0)
            # Critical Mac/Zephyr handshake
            ser.dtr = True
            ser.rts = True 
            text_area.insert(tk.INSERT, 'Motherboard Connected! \n')
        else: 
            text_area.insert(tk.INSERT, 'Motherboard Not Found \n') 
    except Exception as e: 
        text_area.insert(tk.INSERT, 'Serial Port Incorrect \n') 
    time.sleep(1.0) 

def Reset_Motherboard(): 
    global ser
    if not ser:
        print("Reset Motherboard Fail: Device not connected")
        return
    
    try:
        # 1. Send the command
        cmd = f"RST_MB\n"
        ser.write(cmd.encode('ascii'))
        #text_area.insert(tk.INSERT, 'Reset command sent... \n')
        
        # 2. CLOSE the existing handle immediately
        # If you don't, the OS might get confused when the same port reappears
        ser.close()
        ser = None 

    except Exception as e: 
        text_area.insert(tk.INSERT, f'Error during reset write: {e} \n')

    #text_area.insert(tk.INSERT, 'Waiting for reset... \n')
    window.after(2000, Connect_Device) 


def Reset_Patch(): 
    global ser 

    if not ser:
        print("Reset Patch Fail: Device not connected")
        return
    Connect_Device() 
    try: 
        cmd = f"RST_SYS\n"
        ser.write(cmd.encode('ascii'))

        input_queues["PATCH_RST_DONE"].get(timeout=5) 
        text_area.insert(tk.INSERT, 'Patch Reset Done\n')
    except queue.Empty: 
        print("Patch Reset timeout!")

dataout_queue = {i: queue.Queue() for i in range(16)}
input_queues = {
    "SIPO_DONE": queue.Queue(),
    "DAC_DONE":  queue.Queue(), 
    "PATCH_RST_DONE": queue.Queue(), 
    "DATAOUT_DONE": queue.Queue(), 
    "SRAMOUT": queue.Queue(),
    "DLAL": queue.Queue(), 
    "COUNTSTART": queue.Queue(), 
    "COUNTSTATUS": queue.Queue()
}  

def serial_listener():
    global ser
    while True:
        try: 
            if ser: 
                if ser.in_waiting > 0:
                    line = ser.readline().decode('ascii').strip()
                    if not line: continue 

                    if line.startswith("DATAOUT:"): 
                        try: 
                            _, payload = line.split(":") 
                            board_id, val, ts = map(int, payload.split(",")) 
                            print(board_id, val)
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
                    elif "PATCH_RST_DONE" in line: 
                        input_queues["PATCH_RST_DONE"].put(True)
                    elif line.startswith("SRAMOUT:"):
                        input_queues["SRAMOUT"].put(line) 
                    elif line.startswith("COUNTSTART"):
                        input_queues["COUNTSTART"].put(True) 
                    elif "DATAOUT_DONE" in line: 
                        input_queues["DATAOUT_DONE"].put(True)
                    elif line.startswith("COUNTSTATUS:"): 
                        try: 
                            _, payload = line.split(":") 
                            board_id, counts, curr_ts, val, ts = map(int, payload.split(",")) 
                            #text_area.insert(tk.INSERT, f'Motherboard {board_id} Connected! Val: {val}, TS: {ts}\n')
                            #print(board_id, val)
                            # use put because it is thread safe
                            input_queues["COUNTSTATUS"].put((board_id, counts, curr_ts, val, ts))
                            # test
                            #test_val, test_ts = dataout_queue[0].get() 
                            #print(test_val, test_ts)
                        except: 
                            continue
                    elif line.startswith("DLAL_RESP:"): 
                        input_queues["DLAL"].put(line)
                    else: 
                        time.sleep(0.1) 
        except Exception as e: 
            #print("Ser error") 
            time.sleep(1)


threading.Thread(target=serial_listener, daemon=True).start()
 
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
        text_area.insert(tk.INSERT, "SRAM Timeout! \n")
        return 0


# def DL_helper():
#     dev.UpdateWireOuts()
#     return dev.GetWireOutValue(51) # dl_buf_out

# [Yashna] 
def SIPO_data_in(sipo_data0, sipo_data1, sipo_data2, sipo_data3, sipo_data4, sipo_data5, sipo_data6, sipo_data7,  widget, update): 
    if not ser:
        text_area.insert(tk.INSERT, "SIPO Fail: Device not connected \n")
        return
    
    cmd = f"SIPO:{sipo_data7:04X},{sipo_data6:04X},{sipo_data5:04X},{sipo_data4:04X},{sipo_data3:04X},{sipo_data2:04X},{sipo_data1:04X},{sipo_data0:04X}\n"
    ser.write(cmd.encode('ascii'))

    try:
        input_queues["SIPO_DONE"].get(timeout=5)
        widget.insert(tk.INSERT, update)
        text_area.insert(tk.INSERT, f"SIPO done received! \n")
    except queue.Empty:
        text_area.insert(tk.INSERT, "SIPO timeout! \n")
    
    return

# [Archie] keep dequeuing one dataout at a time --> first see if RTC works 
def Main_data_out(i, boardAddress): 
    # if i == 0 and ser is not None:
    #     cmd = "DATA_RD_RST\n" # data_rd_reset
    #     ser.write(cmd.encode('ascii')) 

    dataout = 0
    timestamp = 0
    
    # check if boardAddress has at least one dataout 
    if not dataout_queue[boardAddress].empty(): 
        dataout, timestamp = dataout_queue[boardAddress].get()
 
    return dataout, timestamp

# need to reset all memory and RTC timer on patch
def Reset_global(widget):
    if not ser: return
    cmd = "RST_GLOBAL\n"
    ser.write(cmd.encode('ascii'))
    widget.insert(tk.INSERT, 'Global Reset of System\n')
    return

# [Yashna]
def DAC_data_in(dac_data2, dac_data1, dac_data0, widget, voltage):
    if not ser:
        text_area.insert(tk.INSERT, "DAC_data_in Fail: Device not connected \n")
        return
    
    widget.insert(tk.INSERT, format(dac_data2, '016b') + format(dac_data1, '016b') + format(dac_data0, '016b') + '\n')
     #do we neeed the widget and voltage parameters?
    cmd = f"DAC:{dac_data0:04X},{dac_data1:04X},{dac_data2:04X}\n"

    ser.write(cmd.encode('ascii'))

    try: 
        input_queues["DAC_DONE"].get(timeout=5)
        widget.insert(tk.INSERT, voltage + 'DAC Write Done\n')
    except queue.Empty: 
        text_area.insert(tk.INSERT, "DAC timeout! \n") 
    
    return

def DL_ALValues(): 
    if not ser: return
    
    cmd = "DLAL_RQST\n"
    ser.write(cmd.encode('ascii'))

    try: 
        raw_msg = input_queues["DLAL"].get(timeout=5) 
        raw_data = raw_msg.replace("DLAL_RESP:", "").strip().split(",")

        finalCount = int(raw_data[0])
        finalAddress = int(raw_data[1])
        # test 
        #print(f"DL:{finalCount}, AL:{finalAddress}")
        return (finalCount, finalAddress) 
    except queue.Empty: 
        print("DLAL timeout") 
        return None, None
    except (ValueError, IndexError) as e: 
        print(f"DLAL Data Error: Received malformed message. ({e})") 
        return None, None

# not needed maybe we do need it 
# def Toggle_Clock(clk_togg): 
#     dev.SetWireInValue(18, clk_togg) # clk_togg
#     return

def write_to_patch_n(boardAddressQuery): 
    cmd = "B_ADDR:" + str(boardAddressQuery) + "\n"
    ser.write(cmd.encode('ascii'))
    time.sleep(0.5)
    return

def count_Status(): 
    if not ser:
        text_area.insert(tk.INSERT, "count status Fail: Device not connected \n")
        return
    
    cmd = f"COUNTSTATUS_RQST\n"
    ser.write(cmd.encode('ascii'))

    try: 
        board_id, counts, curr_ts, dataout, ts = input_queues["COUNTSTATUS"].get(timeout=5)
        time = ts / 32768.0 # check if this is correct 
        curr_time = curr_ts / 32768.0
        addr_miss = bitIdxLong(dataout, 24, 24) 
        viol = bitIdxLong(dataout, 23, 23)
        pw = bitIdxLong(dataout, 22, 13)
        row = bitIdxLong(dataout, 12, 6)
        col = bitIdxLong(dataout, 5, 0)

        text_area.insert(tk.INSERT, f'Count Status: board id: {board_id}, counts: {counts}, current time: {curr_time}, addr_miss: {addr_miss}, viol: {viol}, pw: {pw}, row: {row}, col: {col}, time: {time}\n')
    except queue.Empty: 
        text_area.insert(tk.INSERT, "COUNT STATUS timeout!\n") 
    
    return


def updateMainAnalogVoltages():
    vbdl = float(vbdl_text.get())
    vbal = float(vbal_text.get())
    vgtailmain = float(vgtailmain_text.get())
    lspadtop = float(lspadtop_text.get())
    lspadbot = float(lspadbot_text.get())
    gd1 = float(gd1_text.get())
    gd2 = float(gd2_text.get())
    dclevel = float(dclevel_text.get())
    avddh = float(avddh_text.get())
    avddl = float(avddl_text.get())
    dvdd = float(dvdd_text.get())
    vbdl2, vbdl1, vbdl0 = dacIn(vbdl, 3, 0, mainDACSlave1, 3300)
    DAC_data_in(vbdl2, vbdl1, vbdl0, text_area, 'Vb_DL ')
    vbal2, vbal1, vbal0 = dacIn(vbal, 3, 1, mainDACSlave1, 3300)
    DAC_data_in(vbal2, vbal1, vbal0, text_area, 'Vb_AL ')
    vgtailmain2, vgtailmain1, vgtailmain0 = dacIn(vgtailmain, 3, 2, mainDACSlave1, 3300)
    DAC_data_in(vgtailmain2, vgtailmain1, vgtailmain0, text_area, 'VG_TAIL_MAIN ')
    lspadtop2, lspadtop1, lspadtop0 = dacIn(lspadtop, 3, 3, mainDACSlave1, 3300)
    DAC_data_in(lspadtop2, lspadtop1, lspadtop0, text_area, 'LS_PAD_TOP ')
    lspadbot2, lspadbot1, lspadbot0 = dacIn(lspadbot, 3, 4, mainDACSlave1, 3300)
    DAC_data_in(lspadbot2, lspadbot1, lspadbot0, text_area, 'LS_PAD_BOT ')
    gd12, gd11, gd10 = dacIn(gd1, 3, 5, mainDACSlave1, 3300)
    DAC_data_in(gd12, gd11, gd10, text_area, 'GD1 ')
    gd22, gd21, gd20 = dacIn(gd2, 3, 6, mainDACSlave1, 3300)
    DAC_data_in(gd22, gd21, gd20, text_area, 'GD2 ')
    dclevel2, dclevel1, dclevel0 = dacIn(dclevel, 3, 7, mainDACSlave1, 3300)
    DAC_data_in(dclevel2, dclevel1, dclevel0, text_area, 'DCLEVEL ')
    comm = 3
    avddval = avdddis_var.get()
    if avddval == 1:
        comm = 4
    avddh2, avddh1, avddh0 = dacIn(avddh, 3, 0, maintestDACSlave2, 3300)
    DAC_data_in(avddh2, avddh1, avddh0, text_area, 'AVDDH ')
    avddl2, avddl1, avddl0 = dacIn(avddl, 3, 1, maintestDACSlave2, 3300)
    DAC_data_in(avddl2, avddl1, avddl0, text_area, 'AVDDL ')
    dvdd2, dvdd1, dvdd0 = dacIn(dvdd, comm, 2, maintestDACSlave2, 3300)
    DAC_data_in(dvdd2, dvdd1, dvdd0, text_area, 'DVDD ')
    return


def updateTestAnalogVoltageDACs():
    top = float(top_text.get())
    bot = float(bot_text.get())
    vgtail = float(vgtail_text.get())
    #//dctest = float(dctest_text.get())
    #//avddhtest = float(avddhtest_text.get())
    top2, top1, top0 = dacIn(top, 3, 3, maintestDACSlave2, 3300)
    DAC_data_in(top2, top1, top0, text_area, 'TOP ')
    bot2, bot1, bot0 = dacIn(bot, 3, 4, maintestDACSlave2, 3300)
    DAC_data_in(bot2, bot1, bot0, text_area, 'BOT ')
    vgtail2, vgtail1, vgtail0 = dacIn(vgtail, 3, 5, maintestDACSlave2, 3300)
    DAC_data_in(vgtail2, vgtail1, vgtail0, text_area, 'VG_TAIL_TEST ')
    #dctest2, dctest1, dctest0 = dacIn(dctest, 3, 6, maintestDACSlave2, 3300)
    #//DAC_data_in(dctest2, dctest1, dctest0, text_area, 'DCTEST ')
    #avddhtest2, avddhtest1, avddhtest0 = dacIn(avddhtest, 3, 7, maintestDACSlave2, 3300)
    #//DAC_data_in(avddhtest2, avddhtest1, avddhtest0, text_area, 'AVDDH_TEST ')
    #updateTestMuxes()
    return

def writeToMain():
    clkSRAM = int(clkSRAM_text.get())
    clkPISO = int(clkPISO_text.get())
    clkaddr = int(clkaddr_text.get())
    clkcnt = int(clkcnt_text.get())
    lsdacenval = lsdacenvar.get()
    clk_togg = v.get()
    mainWriteWireIn = 1024 + (lsdacenval << 9) + (clkSRAM << 7) + (clkPISO << 5) + (clkaddr << 3) + clkcnt << 5
    #Toggle_Clock(clk_togg)
    if clk_togg == 1:
        SIPO_data_in(0, 0, 0, 0, 0, 0, 0, mainWriteWireIn, text_area, 'Main Write, LS DAC EN: ' + str(lsdacenval) + ', SRAM CLK: ' + str(clkSRAM) + ', PISO CLK: ' + str(clkPISO) + ', ADDR CLK: ' + str(clkaddr) + ', CNT CLK: ' + str(clkcnt) + ', CLK USED: Crystal \n')
    else:
        SIPO_data_in(0, 0, 0, 0, 0, 0, 0, mainWriteWireIn, text_area, 'Main Write, LS DAC EN: ' + str(lsdacenval) + ', SRAM CLK: ' + str(clkSRAM) + ', PISO CLK: ' + str(clkPISO) + ', ADDR CLK: ' + str(clkaddr) + ', CNT CLK: ' + str(clkcnt) + ', CLK USED: FPGA \n')
    return


def writeToSRAM():
    global CRC
    rowaddr = int(row_text.get())
    data = int(data_text.get())
    timing = int(timing_text.get())
    CRC = 0 if CRC == 1 else 1
    sramWriteWireIn = 21267647932558653966460912964485513216 + (rowaddr << 115) + (data << 5) + (timing << 1) + CRC << 2
    sram0 = bitIdxLong(sramWriteWireIn, 15, 0)
    sram1 = bitIdxLong(sramWriteWireIn, 31, 16)
    sram2 = bitIdxLong(sramWriteWireIn, 47, 32)
    sram3 = bitIdxLong(sramWriteWireIn, 63, 48)
    sram4 = bitIdxLong(sramWriteWireIn, 79, 64)
    sram5 = bitIdxLong(sramWriteWireIn, 95, 80)
    sram6 = bitIdxLong(sramWriteWireIn, 111, 96)
    sram7 = bitIdxLong(sramWriteWireIn, 127, 112)
    SIPO_data_in(sram0, sram1, sram2, sram3, sram4, sram5, sram6, sram7, text_area, 'SRAM Write, ROW ADDR: ' + str(rowaddr) + ', DATA: ' + str(data) + ', TIMING: ' + str(timing) + '\n')
    return


def readFromSRAM():
    global CRC
    rowaddr = int(row_text.get())
    data = int(data_text.get())
    timing = int(timing_text.get())
    CRC = 0 if CRC == 1 else 1
    sramWriteWireIn = 10633823966279326983230456482242756608 + (rowaddr << 115) + (data << 5) + (timing << 1) + CRC << 2
    sram0 = bitIdxLong(sramWriteWireIn, 15, 0)
    sram1 = bitIdxLong(sramWriteWireIn, 31, 16)
    sram2 = bitIdxLong(sramWriteWireIn, 47, 32)
    sram3 = bitIdxLong(sramWriteWireIn, 63, 48)
    sram4 = bitIdxLong(sramWriteWireIn, 79, 64)
    sram5 = bitIdxLong(sramWriteWireIn, 95, 80)
    sram6 = bitIdxLong(sramWriteWireIn, 111, 96)
    sram7 = bitIdxLong(sramWriteWireIn, 127, 112)
    SIPO_data_in(sram0, sram1, sram2, sram3, sram4, sram5, sram6, sram7, text_area, 'SRAM Read, ROW ADDR: ' + str(rowaddr) + ', TIMING: ' + str(timing) + '\n')
    sram_rddata = SRAM_data_out()
    if sram_rddata == 3:
        text_area.insert(tk.INSERT, 'SRAM Read Data From Row ' + str(rowaddr) + ': OP ERROR OCCURRED\n')
    else:
        text_area.insert(tk.INSERT, 'SRAM Read Data From Row ' + str(rowaddr) + ': ' + str(bitIdxLong(sram_rddata, 109, 0)) + '\n')
    return


def getReadFromSRAM():
    global CRC
    rowaddr = int(row_text.get())
    data = int(data_text.get())
    timing = int(timing_text.get())
    CRC = 0 if CRC == 1 else 1
    sramWriteWireIn = 10633823966279326983230456482242756608 + (rowaddr << 115) + (data << 5) + (timing << 1) + CRC << 2
    sram0 = bitIdxLong(sramWriteWireIn, 15, 0)
    sram1 = bitIdxLong(sramWriteWireIn, 31, 16)
    sram2 = bitIdxLong(sramWriteWireIn, 47, 32)
    sram3 = bitIdxLong(sramWriteWireIn, 63, 48)
    sram4 = bitIdxLong(sramWriteWireIn, 79, 64)
    sram5 = bitIdxLong(sramWriteWireIn, 95, 80)
    sram6 = bitIdxLong(sramWriteWireIn, 111, 96)
    sram7 = bitIdxLong(sramWriteWireIn, 127, 112)
    SIPO_data_in(sram0, sram1, sram2, sram3, sram4, sram5, sram6, sram7, text_area, 'SRAM Read, ROW ADDR: ' + str(rowaddr) + ', TIMING: ' + str(timing) + '\n')
    sram_rddata = SRAM_data_out()
    if sram_rddata == 3:
        text_area.insert(tk.INSERT, 'SRAM Read Data From Row ' + str(rowaddr) + ': OP ERROR OCCURRED\n')
    elif sram_rddata < 511:
        text_area.insert(tk.INSERT, 'Mux Row Changed To Row ' + str(sram_rddata) + '\n')
    else:
        text_area.insert(tk.INSERT, 'SRAM Read Data From Row ' + str(rowaddr) + ': ' + str(bitIdxLong(sram_rddata, 109, 0)) + '\n')
    return bitIdxLong(sram_rddata, 109, 0)


def displayDLALMux():
    global CRC
    rowaddr = int(row_text.get())
    data = int(data_text.get())
    timing = int(timing_text.get())
    CRC = 0 if CRC == 1 else 1
    sramWriteWireIn = (rowaddr << 115) + (data << 5) + (timing << 1) + CRC << 2
    sram0 = bitIdxLong(sramWriteWireIn, 15, 0)
    sram1 = bitIdxLong(sramWriteWireIn, 31, 16)
    sram2 = bitIdxLong(sramWriteWireIn, 47, 32)
    sram3 = bitIdxLong(sramWriteWireIn, 63, 48)
    sram4 = bitIdxLong(sramWriteWireIn, 79, 64)
    sram5 = bitIdxLong(sramWriteWireIn, 95, 80)
    sram6 = bitIdxLong(sramWriteWireIn, 111, 96)
    sram7 = bitIdxLong(sramWriteWireIn, 127, 112)
    SIPO_data_in(sram0, sram1, sram2, sram3, sram4, sram5, sram6, sram7, text_area, 'DL/AL Mux Output, ROW ADDR: ' + str(rowaddr) + ', TIMING: ' + str(timing) + '\n')
    mux_status = SRAM_data_out()
    text_area.insert(tk.INSERT, 'Mux Updated Row: ' + str(rowaddr) + ', Chip Status Mux Updated Row: ' + str(mux_status) + '\n')
    return


def startdlal():
    global alCPS
    global alCounts
    global dlCPS
    global dlCounts
    global runningDLAL
    global startTimeDLAL
    global x
    if dlalvar.get():
        runningDLAL = True
        dlCounts = []
        alCounts = []
        dlCPS = []
        alCPS = []
        text_area.insert(tk.INSERT, 'DL/AL Mux Active... \n')
        x = 0
        startTimeDLAL = time.time()
        dlal_Print()
    else:
        runningDLAL = False
        text_area.insert(tk.INSERT, '... DL/AL Mux Display Stopped \n')
    return


def dlal_Print():
    global x
    if runningDLAL:
        dl, al = DL_ALValues(x)
        dlCounts.append(dl)
        alCounts.append(al)
        if x != 0:
            dlCPS.append(dlCounts[x] - dlCounts[x - 1])
            alCPS.append(alCounts[x] - alCounts[x - 1])
        else:
            dlCPS.append(dlCounts[x])
            alCPS.append(alCounts[x])
        if time.time() - startTimeDLAL > 1:
            text_area.insert(tk.INSERT, 'Time ' + str(time.time() - startTimeDLAL) + ': ' + 'DL CPS: ' + str(dlCPS[x]) + ', AL CPS: ' + str(alCPS[x]) + '\n')
        x = x + 1
        window.after(1000, dlal_Print)
    return


def windowShrink():
    global flagwindow
    global wh
    global ww
    if flagwindow:
        window.geometry('2850x800')
        flagwindow = False
    else:
        window.geometry(str(ww) + 'x' + str(wh))
        flagwindow = True
    return

# this only sets the output wire sof s0-3 on fpga. need to change this so that it sends to correct patch wirelessly 
def boardAddressChange():
    global boardAddressQuery
    boardAddressQuery = int(boardaddress_text.get())
    write_to_patch_n(boardAddressQuery)
    return

def patchNumber():
    global patchNum
    patchNum = int(patchnum_text.get())

    cmd = "PATCH_NUM:" + str(patchNum) + "\n"
    ser.write(cmd.encode('ascii'))
    time.sleep(0.5)
    return

# [Archie] 
def startMain():
    global addr_miss, avgCnt, avgPW, cnt, col, pw, row, timeStamp, viol # lists 
    global after_id_main, avgCPS_val, boardAddress, elapsed_time_main, i, recTime, running, start_time_main
    recTime = float(filename.get().split(',')[1])
    dataout = 0
    calDisable = calConfigSettings.get().split(',')
    if running and float(elapsed_time_main) < 60 * recTime:
        dataout, hit_timestamp = Main_data_out(i, boardAddress) # change so that it also returns the timestamp
        if dataout != 0: 
            hit_timestamp_s = hit_timestamp / 32768.0 # check if this is correct 

            timeStamp[boardAddress].append(hit_timestamp_s) 
            addr_miss[boardAddress].append(bitIdxLong(dataout, 24, 24)) 
            viol[boardAddress].append(bitIdxLong(dataout, 23, 23))
            pw[boardAddress].append(bitIdxLong(dataout, 22, 13))
            row[boardAddress].append(bitIdxLong(dataout, 12, 6))
            col[boardAddress].append(bitIdxLong(dataout, 5, 0))
            cnt[boardAddress] += 1
            stopMainSaveFile()
        #elif i == 0: # I can probably reset everything here 
            #for j in range(16): cnt[j] = 0
            #stopMainSaveFile()
        boardAddress = (boardAddress + 1) % patchNum
        elapsed_time_main = time.time() - start_time_main
        i = i + 1
        print (time.time() - start_time_main) 

        # make sure to initialize avgcnt and avgpw values as 0s in the beginning 
        if timeStamp[boardAddressQuery]: 
            latest_hit_time = max(timeStamp[boardAddressQuery]) # elapsed time for the patch 
            avgCnt[boardAddressQuery] = float(cnt[boardAddressQuery]) / latest_hit_time

            avgPW[boardAddressQuery] = float(sum(pw[boardAddressQuery])) / float(len(pw[boardAddressQuery]))

        stringSummary = str(avgCnt[boardAddressQuery]) + ', ' + str(avgPW[boardAddressQuery])
        avgCPS_val.config(text=stringSummary)
        if after_id_main:
            window.after_cancel(after_id_main)
        after_id_main = window.after(20, startMain)
    elif float(elapsed_time_main) > 60 * recTime:
        text_area.insert(tk.INSERT, '...Main Program Finished Recording \n')
        running = False
        stopMainSaveFile()
        return
    return

# [Archie]: everything is reset here 
def initialize_run():
    global addr_miss, cnt, col, pw, row, timeStamp, viol
    global boardAddress, elapsed_time_main, i, running, start_time_main, dlrows, dlval, last_int, rowval_sweep, start_time_sram
    global dataout_queue, input_queues
    addr_miss = [[] for _ in range(patchNum)] 
    cnt = [0 for _ in range(patchNum)]
    col = [[] for _ in range(patchNum)]
    pw = [[] for _ in range(patchNum)]
    row = [[] for _ in range(patchNum)]
    timeStamp = [[] for _ in range(patchNum)]
    viol = [[] for _ in range(patchNum)] 

    dataout_queue = {i1: queue.Queue() for i1 in range(16)}
    input_queues["DATAOUT_DONE"] = queue.Queue() 
    input_queues["SRAMOUT"] = queue.Queue() 
    input_queues["COUNTSTART"] = queue.Queue()
    input_queues["COUNTSTATUS"] = queue.Queue()

    # didn't change 
    dlval = []
    dlrows = []
    rowval_sweep = 0
    i = 0
    boardAddress = 0
    start_time_sram = time.time()
    last_int = time.time()
    elapsed_time_main = 0
    #text_area.insert(tk.INSERT, 'Main Program Running... \n')
    start_time_main = time.time()
    for j in range(16): cnt[j] = 0
    # here need to start the patch: rtc timer
    if not ser:
        print("Start Fail: Device not connected")
        return
    
    try:
        cmd = f"STARTG:\n"
        ser.write(cmd.encode('ascii'))

        #print("waiting")
        input_queues["COUNTSTART"].get(timeout=10)
        text_area.insert(tk.INSERT, f"Main Program Running... \n")
    except queue.Empty:
        text_area.insert(tk.INSERT, "COUNTSTART timeout! \n")

    running = True

    #window.after(20, startMain)
    return

# not needed 
# def demo_run():
#     global after_id
#     if runningDemo:
#         stagepos = float(stage_pos.get())
#         if stagepos == 0:
#             avgCPS.config(text='1cm: Avg CPS, Avg DT ')
#             avgCPS.config(fg='blue')
#             changeEntryWidget(diodeselect_text, str(1))
#             updateTestAnalogVoltageDACs()
#             changeEntryWidget(stage_pos, str(-5))
#             moveStage()
#             changeEntryWidget(diodeselect_text, str(0))
#             updateTestAnalogVoltageDACs()
#             changeEntryWidget(filename, filename.get().split(',')[0] + ',' + str(2))
#         elif stagepos == -5:
#             avgCPS.config(text='5mm: Avg CPS, Avg DT ')
#             avgCPS.config(fg='red')
#             changeEntryWidget(diodeselect_text, str(1))
#             updateTestAnalogVoltageDACs()
#             changeEntryWidget(stage_pos, str(0))
#             moveStage()
#             changeEntryWidget(diodeselect_text, str(0))
#             updateTestAnalogVoltageDACs()
#             changeEntryWidget(filename, filename.get().split(',')[0] + ',' + str(2))
#         globalReset()
#         time.sleep(1)
#         globalReset()
#         time.sleep(1)
#         writeToMain()
#         time.sleep(1)
#         writeToMain()
#         print ('Function Executed')
#         initialize_run()
#         rT = float(filename.get().split(',')[1])
#         moveTime = int(66000.0 * rT)
#         print (moveTime)
#         if after_id:
#             window.after_cancel(after_id)
#         after_id = window.after(moveTime, demo_run)
#     return

# not needed
# def demo_run_init():
#     global runningDemo
#     runningDemo = True
#     demo_run()
#     return

# not needed
# def demo_stop():
#     global running
#     global runningDemo
#     running = False
#     runningDemo = False
#     text_area.insert(tk.INSERT, '...Demo Program Stopped \n')
#     stopMainSaveFile()
#     return

def retrieve_data(boardAddress): 
    try:
        is_done = input_queues["DATAOUT_DONE"].get(block=False)
    except queue.Empty:
        is_done = False

    if is_done:
        if dataout_queue[boardAddress].empty():
            return True
        else:
            # Not ready yet! Put it back for the next check
            input_queues["DATAOUT_DONE"].put(True)

    dataout, hit_timestamp = Main_data_out(i, boardAddress) # change so that it also returns the timestamp

    if dataout != 0: 
        hit_timestamp_s = hit_timestamp / 32768.0 # check if this is correct 

        timeStamp[boardAddress].append(hit_timestamp_s) 
        addr_miss[boardAddress].append(bitIdxLong(dataout, 24, 24)) 
        viol[boardAddress].append(bitIdxLong(dataout, 23, 23))
        pw[boardAddress].append(bitIdxLong(dataout, 22, 13))
        row[boardAddress].append(bitIdxLong(dataout, 12, 6))
        col[boardAddress].append(bitIdxLong(dataout, 5, 0))
        cnt[boardAddress] += 1
        #stopMainSaveFile()
        return False
    # elif i == 0: # I can probably reset everything here 
    #     for j in range(16): cnt[j] = 0
    #     stopMainSaveFile()
    # boardAddress = (boardAddress + 1) % num_patch
    #elapsed_time_main = time.time() - start_time_main
    #i = i + 1
    #print (time.time() - start_time_main) 

    # make sure to initialize avgcnt and avgpw values as 0s in the beginning 
    # if timeStamp[boardAddressQuery]: 
    #     latest_hit_time = max(timeStamp[boardAddressQuery]) # elapsed time for the patch 
    #     avgCnt[boardAddressQuery] = float(cnt[boardAddressQuery]) / latest_hit_time

    #     avgPW[boardAddressQuery] = float(sum(pw[boardAddressQuery])) / float(len(pw[boardAddressQuery]))

    #stringSummary = str(avgCnt[boardAddressQuery]) + ', ' + str(avgPW[boardAddressQuery])
    #avgCPS_val.config(text=stringSummary)
    # if after_id_main:
    #     window.after_cancel(after_id_main)
    # after_id_main = window.after(20, startMain)

# stop main calls
def stopMain():
    global running
    running = False 
    patch_read_done = False

    text_area.insert(tk.INSERT, '...Main Program Stopped and Retrieving Data\n') 

    process_next_patch(0) 

    # boardAddress = (boardAddress + 1) % num_patch
    #stopMainSaveFile()
    return 

def process_next_patch(i): 
    if i >= patchNum:
        stopMainSaveFile() 
        text_area.insert(tk.INSERT, 'All Patches Processed Successfully.\n')
        return

    # Send the stop command for THIS patch only
    cmd = f"STOPG{i}\n"
    ser.write(cmd.encode('ascii')) 
    text_area.insert(tk.INSERT, f'...Retrieving Data from Patch{i}...\n')

    # Start draining this specific patch
    drain_and_save(i)

def drain_and_save(i):
    # Attempt to retrieve remaining data 
    finished = retrieve_data(i) 
    
    if not finished:
        # If there's still data in the queue, check again in 10ms
        # This keeps the GUI responsive while data is being saved!
        window.after(10, drain_and_save, i)
    else:
        text_area.insert(tk.INSERT, f'...Patch{i} Data Saved Successfully.\n')
        
        # THIS IS THE MAGIC: Move to the next patch in the sequence
        process_next_patch(i + 1)

# [Archie]  
def stopMainSaveFile(): 
    data_dic = {} 
    
    # check if this is correct 
    for i in range(patchNum): 
        suffix = "" if i == 0 else str(i) 
        data_dic[f'time{suffix}']      = timeStamp[i]
        data_dic[f'addr_miss{suffix}'] = addr_miss[i]
        data_dic[f'viol{suffix}']      = viol[i]
        data_dic[f'pw{suffix}']        = pw[i]
        data_dic[f'row{suffix}']       = row[i]
        data_dic[f'col{suffix}']       = col[i]
        
    filename_val = filename.get().split(',')[0]
    savemat(filename_val.replace('\n', '') + '.mat', data_dic)
    return


def globalReset():
    Reset_global(text_area)
    return


def loadDefaultConfig():
    filenamebrowse = browseFiles()
    if filenamebrowse == '':
        text_area.insert(tk.INSERT, 'File is empty. Please load a correct settings configuration file. \n')
        changeEntryWidget('', f)
        return
    i = 0
    filestr = ''
    calconfigparamstring = '' 
    stagestring = '' 
    file1 = open(filenamebrowse, 'r')
    lines = file1.readlines()
    for line in lines:
        if i <= 26:
            res = line.split('=')
            defConfig.append(int(res[1]))
        elif i == 27:
            res = line.split('=')
            filestr = res[1]
        elif i == 28:
            res = line.split('=')
            rectimestr = res[1]
        elif i == 29:
            res = line.split('=')
            calconfigparamstring = res[1]
        elif i == 30:
            res = line.split('=')
            disenstring = res[1]
        else:
            res = line.split('=')
            stagestring = res[1]
        i = i + 1

    defConfig.append(filestr)
    defConfig.append(rectimestr)
    defConfig.append(calconfigparamstring)
    defConfig.append(disenstring)
    defConfig.append(stagestring)
    loadConfig()
    return


def loadConfig():
    changeEntryWidget(vbdl_text, str(defConfig[0]))
    changeEntryWidget(vbal_text, str(defConfig[1]))
    changeEntryWidget(vgtailmain_text, str(defConfig[2]))
    changeEntryWidget(lspadtop_text, str(defConfig[3]))
    changeEntryWidget(lspadbot_text, str(defConfig[4]))
    changeEntryWidget(gd1_text, str(defConfig[5]))
    changeEntryWidget(gd2_text, str(defConfig[6]))
    changeEntryWidget(dclevel_text, str(defConfig[7]))
    changeEntryWidget(avddh_text, str(defConfig[8]))
    changeEntryWidget(avddl_text, str(defConfig[9]))
    changeEntryWidget(dvdd_text, str(defConfig[10]))
    changeEntryWidget(vgtail_text, str(defConfig[11]))
    changeEntryWidget(top_text, str(defConfig[12]))
    changeEntryWidget(bot_text, str(defConfig[13]))
    changeEntryWidget(inplus_text, str(defConfig[14]))
    changeEntryWidget(inminus_text, str(defConfig[15]))
    changeEntryWidget(dctest_text, str(defConfig[16]))
    changeEntryWidget(diodeselect_text, str(defConfig[17]))
    changeEntryWidget(pixeldac_text, str(defConfig[18]))
    changeEntryWidget(avddhtest_text, str(defConfig[19]))
    changeEntryWidget(row_text, str(defConfig[20]))
    changeEntryWidget(data_text, str(defConfig[21]))
    changeEntryWidget(timing_text, str(defConfig[22]))
    changeEntryWidget(clkSRAM_text, str(defConfig[23]))
    changeEntryWidget(clkPISO_text, str(defConfig[24]))
    changeEntryWidget(clkaddr_text, str(defConfig[25]))
    changeEntryWidget(clkcnt_text, str(defConfig[26]))
    changeEntryWidget(filename, defConfig[27] + ',' + str(defConfig[28]))
    changeEntryWidget(calConfigSettings, defConfig[29])
    changeEntryWidget(disable_text, defConfig[30])
    changeEntryWidget(stage_pos, defConfig[31])
    return


def saveConfig():
    defConfigSave = []
    defConfigSave.append(vbdl_text.get())
    defConfigSave.append(vbal_text.get())
    defConfigSave.append(vgtailmain_text.get())
    defConfigSave.append(lspadtop_text.get())
    defConfigSave.append(lspadbot_text.get())
    defConfigSave.append(gd1_text.get())
    defConfigSave.append(gd2_text.get())
    defConfigSave.append(dclevel_text.get())
    defConfigSave.append(avddh_text.get())
    defConfigSave.append(avddl_text.get())
    defConfigSave.append(dvdd_text.get())
    defConfigSave.append(vgtail_text.get())
    defConfigSave.append(top_text.get())
    defConfigSave.append(bot_text.get())
    defConfigSave.append(inplus_text.get())
    defConfigSave.append(inminus_text.get())
    defConfigSave.append(dctest_text.get())
    defConfigSave.append(diodeselect_text.get())
    defConfigSave.append(pixeldac_text.get())
    defConfigSave.append(avddhtest_text.get())
    defConfigSave.append(row_text.get())
    defConfigSave.append(data_text.get())
    defConfigSave.append(timing_text.get())
    defConfigSave.append(clkSRAM_text.get())
    defConfigSave.append(clkPISO_text.get())
    defConfigSave.append(clkaddr_text.get())
    defConfigSave.append(clkcnt_text.get())
    defConfigSave.append(filename.get().split(',')[0])
    defConfigSave.append(filename.get().split(',')[1])
    defConfigSave.append(calConfigSettings.get())
    defConfigSave.append(disable_text.get())
    defConfigSave.append(stage_pos.get())
    strSave = 'vbdlo=' + defConfigSave[0] + '\nvbalo=' + defConfigSave[1] + '\nvgtailmaino=' + defConfigSave[2] + '\nlspadtopo=' + defConfigSave[3] + '\nlspadboto=' + defConfigSave[4] + '\ngd1o=' + defConfigSave[5] + '\ngd2o=' + defConfigSave[6] + '\ndclevelo=' + defConfigSave[7] + '\navddho=' + defConfigSave[8] + '\navddlo=' + defConfigSave[9] + '\ndvddo=' + defConfigSave[10] + '\nvgtailo=' + defConfigSave[11] + '\ntopo=' + defConfigSave[12] + '\nboto=' + defConfigSave[13] + '\ninpluso=' + defConfigSave[14] + '\ninminuso=' + defConfigSave[15] + '\ndctesto=' + defConfigSave[16] + '\ndiodeselecto=' + defConfigSave[17] + '\npixeldaco=' + defConfigSave[18] + '\navddhtest=' + defConfigSave[19] + '\nrowo=' + defConfigSave[20] + '\ndatao=' + defConfigSave[21] + '\ntimingo=' + defConfigSave[22] + '\nclkSRAMo=' + defConfigSave[23] + '\nclkPISOo=' + defConfigSave[24] + '\nclk_addr=' + defConfigSave[25] + '\nclk_cnt=' + defConfigSave[26] + '\nfilename=' + defConfigSave[27] + 'recTimeMin=' + defConfigSave[28] + '\nsettings=' + defConfigSave[29] + 'pixsett=' + defConfigSave[30] + 'stagepos=' + defConfigSave[31]
    text_file_name = asksaveasfile(initialfile='Untitled.txt', defaultextension='.txt', filetypes=[('All Files', '*.*'), ('Text Documents', '*.txt')])
    n = text_file_name.write(strSave)
    text_file_name.close()
    text_area.insert(tk.INSERT, 'Analog/Digital Configuration Saved in ' + text_file_name.name + '\n')
    return


def externalLSAllPixels():
    disableparam = disable_text.get().split(',')
    i = int(disableparam[2])
    for i in range(int(disableparam[2]), int(disableparam[3])):
        changeEntryWidget(row_text, str(i))
        if (i + 1) % 3 == 1:
            changeEntryWidget(data_text, str(1298074214633706907132624082305023))
        else:
            changeEntryWidget(data_text, str(0))
        writeToSRAM()
        writeToSRAM()

    text_area.insert(tk.INSERT, 'All Pixels Disabled')
    return


def disableAllPixels():
    disableparam = disable_text.get().split(',')
    i = int(disableparam[0])
    for i in range(int(disableparam[0]), int(disableparam[1])):
        changeEntryWidget(row_text, str(i))
        changeEntryWidget(data_text, str(0))
        writeToSRAM()

    text_area.insert(tk.INSERT, 'All Pixels Disabled')
    single_en = int(disableparam[6])
    if single_en == 1:
        isingle = int(disableparam[4])
        for isingle in range(int(disableparam[4]), int(disableparam[4]) + 3):
            changeEntryWidget(row_text, str(isingle))
            colval = int(disableparam[5])
            SRAMrd = getReadFromSRAM()
            if bitIdxLong(SRAMrd, colval * 2, colval * 2) != 0:
                SRAMrd1 = getReadFromSRAM()
                strSRAM = SRAMrd1 - 2 ** (colval * 2)
                changeEntryWidget(data_text, str(strSRAM))
                time.sleep(0.1)
                writeToSRAM()
            if bitIdxLong(SRAMrd, colval * 2 + 1, colval * 2 + 1) != 0:
                SRAMrd2 = getReadFromSRAM()
                strSRAM = SRAMrd2 - 2 ** (colval * 2 + 1)
                changeEntryWidget(data_text, str(strSRAM))
                time.sleep(0.1)
                writeToSRAM()

        text_area.insert(tk.INSERT, 'One Pixel Disabled')
    #print (str(DL_helper()))
    return


def loadSRAMConfiguration():
    SRAMfile = browseFiles()
    rowCounter = 0
    if SRAMfile == '':
        text_area.insert(tk.INSERT, 'File is empty. Please load a correct SRAM configuration file.\n')
        return
    with open(SRAMfile, 'r') as file:
        csvreader = csv.reader(file)
        for row in csvreader:
            rowbinstr = [format(int(n.split('.')[0]), '003b') for n in row]
            rowbin = format(int(('').join(rowbinstr), 2), '0330b')
            rowSRAM.append(int(rowbin[2::3], 2))
            changeEntryWidget(row_text, str(rowCounter))
            changeEntryWidget(data_text, str(rowSRAM[-1]))
            writeToSRAM()
            rowCounter = rowCounter + 1
            rowSRAM.append(int(rowbin[1::3], 2))
            changeEntryWidget(row_text, str(rowCounter))
            changeEntryWidget(data_text, str(rowSRAM[-1]))
            writeToSRAM()
            rowCounter = rowCounter + 1
            rowSRAM.append(int(rowbin[::3], 2))
            changeEntryWidget(row_text, str(rowCounter))
            changeEntryWidget(data_text, str(rowSRAM[-1]))
            writeToSRAM()
            rowCounter = rowCounter + 1

    text_area.insert(tk.INSERT, 'SRAM configuration correctly written')
    return

# not needed 
# def moveStage():
#     global direction
#     global position
#     global step
#     newPos = float(stage_pos.get())
#     print ('newPos' + str(newPos))
#     deltaPos = 40 * (newPos - position)
#     if deltaPos < 0:
#         step = int(abs(deltaPos))
#         print (step)
#         direction = 0
#         print (direction)
#         if step == 3800:
#             k = 0
#             while k < 9:
#                 Change_Stage_Position(400, direction)
#                 k += 1

#             Change_Stage_Position(200, direction)
#         else:
#             Change_Stage_Position(step, direction)
#     elif deltaPos > 0:
#         step = int(abs(deltaPos))
#         print (step)
#         direction = 1
#         print (direction)
#         if step == 3800:
#             m = 0
#             while m < 9:
#                 Change_Stage_Position(400, direction)
#                 m += 1

#             Change_Stage_Position(200, direction)
#         else:
#             Change_Stage_Position(step, direction)
#     else:
#         step = 0
#         direction = 0
#     newPosBacktrack = float(deltaPos) / 40 + position
#     stringPos = 'Stage X: ' + str(newPosBacktrack) + ' mm'
#     position = newPosBacktrack
#     stage_lab.config(text=stringPos)
#     return


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


def bitIdxLong(num, k, p):
    print (num)
    binary = format(num, '128b')
    binary = binary.replace(' ', '0')
    print (binary)
    end = len(binary) - p
    start = len(binary) - k - 1
    binrep = binary[start:end]
    return int(binrep, 2)


def changeEntryWidget(e, text):
    e.delete(0, tk.END)
    e.insert(0, text)
    return


def browseFiles():
    filenamebrowse = filedialog.askopenfilename(initialdir='./', title='Select a File', filetypes=(
     ('all files', '*.*'),
     ))
    return filenamebrowse


logo = Image.open('RPTChipWWISERLogo_ArchieLee.png')
size = (200, 200)
logo.thumbnail(size)
img = ImageTk.PhotoImage(logo)
tk.Label(window, image=img).grid(row=0, column=0, columnspan=2, rowspan=5, padx=5, pady=5)
#demobutt = tk.Button(text='Start Demo', command=demo_run_init)
#demobuttstop = tk.Button(text='Stop Demo', command=demo_stop)
#demobutt.grid(row=5, column=0)
#demobuttstop.grid(row=5, column=1)
shrinkbutt = tk.Button(text='Resize', command=windowShrink)
shrinkbutt.grid(row=5, column=0, columnspan=2, rowspan=1, pady=10)
text_area = st.ScrolledText(window, width=75, height=20, font=('Times New Roman', 12))
text_area.grid(row=0, column=2, columnspan=3, rowspan=7, padx=5, pady=5)
text_area.insert(tk.INSERT, 'Returned Values from RPT Chip:\n')
avgCPS = tk.Label(text='Avg CPS, Avg DT ', height=2, width=25, font='Helvetica 16 bold')
avgCPS.grid(row=0, column=5, columnspan=1, rowspan=1)
avgCPS_val = tk.Label(text='N/A, N/A', font=('Times New Roman', 13))
avgCPS_val.grid(row=1, column=5, columnspan=1, rowspan=1, pady=10, sticky='n')
connect = tk.Button(text='Connect BLE Motherboard', command=Connect_Device).grid(row=2, column=5, columnspan=1, rowspan=1, sticky='n') 
reset_mb = tk.Button(text='Reset BLE Motherboard', command=Reset_Motherboard).grid(row=2, column=6, columnspan=1, rowspan=1, sticky='n') #here
reset_patch = tk.Button(text='Reset Patch', command=Reset_Patch).grid(row=3, column=6, columnspan=1, rowspan=1, sticky='n')
count_status = tk.Button(text='Count Status', command=count_Status).grid(row=4, column=6, columnspan=1, rowspan=1, sticky='n')
globReset = tk.Button(text='Global Reset Patch & Chip', command=globalReset).grid(row=3, column=5, columnspan=1, rowspan=1, sticky='n')
run = tk.Button(text='Start Recording Gamma Counts', command=initialize_run).grid(row=4, column=5, columnspan=1, rowspan=1, sticky='n')
stop = tk.Button(text='Stop Recording', command=stopMain).grid(row=5, column=5, columnspan=1, rowspan=1, sticky='n')
filename = tk.Entry(width=25)
filename.grid(row=6, column=5, pady=2, sticky='s')
rmain_new = 6
rmain = 7
vbdl_text = tk.Entry(width=25)
vbal_text = tk.Entry(width=25)
vgtailmain_text = tk.Entry(width=25)
lspadtop_text = tk.Entry(width=25)
lspadbot_text = tk.Entry(width=25)
gd1_text = tk.Entry(width=25)
gd2_text = tk.Entry(width=25)
dclevel_text = tk.Entry(width=25)
avddh_text = tk.Entry(width=25)
avddl_text = tk.Entry(width=25)
dvdd_text = tk.Entry(width=25)
vbdl_text.grid(row=rmain_new + 1, column=1, pady=2)
vbal_text.grid(row=rmain_new + 2, column=1, pady=2)
vgtailmain_text.grid(row=rmain_new + 3, column=1, pady=2)
lspadtop_text.grid(row=rmain_new + 4, column=1, pady=2)
lspadbot_text.grid(row=rmain_new + 5, column=1, pady=2)
gd1_text.grid(row=rmain_new + 6, column=1, pady=2)
gd2_text.grid(row=rmain_new + 7, column=1, pady=2)
dclevel_text.grid(row=rmain_new + 8, column=1, pady=2)
avddh_text.grid(row=rmain_new + 9, column=1, pady=2)
avddl_text.grid(row=rmain_new + 10, column=1, pady=2)
dvdd_text.grid(row=rmain_new + 11, column=1, pady=2)
avdddis = tk.Checkbutton(text='disable', variable=avdddis_var, onvalue=1, offvalue=0).grid(row=rmain + 14, column=4, sticky='e', pady=2)
mainalogbutt = tk.Button(text='Main Analog Update', command=updateMainAnalogVoltages)
mainalogbutt.grid(row=rmain_new + 12, column=0, columnspan=2, rowspan=1, pady=10)
main_alog = tk.Label(text='Main Analog Voltages', height=2, width=25, font='Helvetica 18 bold')
vbdl_lab = tk.Label(text='VB_DL (mV)', height=2, width=25)
vbal_lab = tk.Label(text='VB_AL (mV)', height=2, width=25)
vgtailmain_lab = tk.Label(text='VG_TAIL_MAIN (mV)', height=2, width=25)
lspadtop_lab = tk.Label(text='LS_PAD_TOP (mV)', height=2, width=25)
lspadbot_lab = tk.Label(text='LS_PAD_BOT (mV)', height=2, width=25)
gd1_lab = tk.Label(text='GD1 (mV)', height=2, width=25)
gd2_lab = tk.Label(text='DACIN (mV)', height=2, width=25)
dclevel_lab = tk.Label(text='DCLEVEL (mV)', height=2, width=25)
avddh_lab = tk.Label(text='AVDDH (mV)', height=2, width=25)
avddl_lab = tk.Label(text='AVDDL (mV)', height=2, width=25)
dvdd_lab = tk.Label(text='DVDD (mV)', height=2, width=25)
main_alog.grid(row=rmain_new, column=0, columnspan=2, rowspan=1, padx=5, pady=5)
vbdl_lab.grid(row=rmain_new + 1, column=0, pady=2)
vbal_lab.grid(row=rmain_new + 2, column=0, pady=2)
vgtailmain_lab.grid(row=rmain_new + 3, column=0, pady=2)
lspadtop_lab.grid(row=rmain_new + 4, column=0, pady=2)
lspadbot_lab.grid(row=rmain_new + 5, column=0, pady=2)
gd1_lab.grid(row=rmain_new + 6, column=0, pady=2)
gd2_lab.grid(row=rmain_new + 7, column=0, pady=2)
dclevel_lab.grid(row=rmain_new + 8, column=0, pady=2)
avddh_lab.grid(row=rmain_new + 9, column=0, pady=2)
avddl_lab.grid(row=rmain_new + 10, column=0, pady=2)
dvdd_lab.grid(row=rmain_new + 11, column=0, pady=2)
stage_lab = tk.Label(text='Stage X: N/A mm', height=2, width=25)
stage_lab.grid(row=rmain + 13, column=0, columnspan=2, rowspan=1, pady=2)
stage_pos = tk.Entry(width=25)
stage_pos.grid(row=rmain + 14, column=0, pady=10)
#updatePosButt = tk.Button(text='Update X Position', command=moveStage) changed 
#updatePosButt.grid(row=rmain + 14, column=1, columnspan=1, rowspan=1, pady=10) changed
vgtail_text = tk.Entry(width=25)
top_text = tk.Entry(width=25)
bot_text = tk.Entry(width=25)
inplus_text = tk.Entry(width=25)
inminus_text = tk.Entry(width=25)
dctest_text = tk.Entry(width=25)
diodeselect_text = tk.Entry(width=25)
pixeldac_text = tk.Entry(width=25)
avddhtest_text = tk.Entry(width=25)
vgtail_text.grid(row=rmain + 1, column=3, pady=2)
top_text.grid(row=rmain + 2, column=3, pady=2)
bot_text.grid(row=rmain + 3, column=3, pady=2)
#inplus_text.grid(row=rmain + 4, column=3, pady=2)
#inminus_text.grid(row=rmain + 5, column=3, pady=2)
#dctest_text.grid(row=rmain + 6, column=3, pady=2)
#diodeselect_text.grid(row=rmain + 7, column=3, pady=2)
#pixeldac_text.grid(row=rmain + 8, column=3, pady=2)
#avddhtest_text.grid(row=rmain + 9, column=3, pady=2)
testalogbutt = tk.Button(text='Test Analog Update', command=updateTestAnalogVoltageDACs)
testalogbutt.grid(row=rmain + 5, column=2, columnspan=2, rowspan=1)
test_alog = tk.Label(text='Test Analog Voltages', height=2, width=25, font='Helvetica 18 bold')
vgtail_lab = tk.Label(text='DAC_EXTRA_1 (mV)', height=2, width=25)
top_lab = tk.Label(text='VDDHSRAM (mV)', height=2, width=25)
bot_lab = tk.Label(text='AVDDHBUFF (mV)', height=2, width=25)
#inplus_lab = tk.Label(text='INPLUS (1b)', height=2, width=25)
#inminus_lab = tk.Label(text='INMINUS (1b)', height=2, width=25)
#dctest_lab = tk.Label(text='DAC_EXTRA_2 (mV)', height=2, width=25)
#diodeselect_lab = tk.Label(text='DIODESELECT_TEST (0-15)', height=2, width=25)
#pixeldac_lab = tk.Label(text='PIXELDAC_TEST (0-7)', height=2, width=25)
#avddhtest_lab = tk.Label(text='DAC_EXTRA_3 (mV)', height=2, width=25)
test_alog.grid(row=rmain, column=2, columnspan=2, rowspan=1, padx=5, pady=5)
vgtail_lab.grid(row=rmain + 1, column=2, pady=2)
top_lab.grid(row=rmain + 2, column=2, pady=2)
bot_lab.grid(row=rmain + 3, column=2, pady=2)
#inplus_lab.grid(row=rmain + 4, column=2, pady=2)
#inminus_lab.grid(row=rmain + 5, column=2, pady=2)
#dctest_lab.grid(row=rmain + 6, column=2, pady=2)
#diodeselect_lab.grid(row=rmain + 7, column=2, pady=2)
#pixeldac_lab.grid(row=rmain + 8, column=2, pady=2)
#avddhtest_lab.grid(row=rmain + 9, column=2, pady=2)
loadconfigbutt = tk.Button(text='Load Configuration', command=loadDefaultConfig)
loadconfigbutt.grid(row=rmain + 7, column=2, columnspan=1, rowspan=1)
writeconfigbutt = tk.Button(text='Save Configuration', command=saveConfig)
writeconfigbutt.grid(row=rmain + 6, column=2, columnspan=1, rowspan=1)
disPixButt = tk.Button(text='Disable All Pixels', command=disableAllPixels)
disPixButt.grid(row=rmain + 6, column=3, columnspan=1, rowspan=1)
sramConfigButt = tk.Button(text='Load SRAM Configuration', command=loadSRAMConfiguration)
sramConfigButt.grid(row=rmain + 7, column=3, columnspan=1, rowspan=1)
calConfigSettings = tk.Entry(width=25)
calConfigSettings.grid(row=rmain + 8, column=2)
disable_text = tk.Entry(width=25)
disable_text.grid(row=rmain + 9, column=2)
padConfigButt = tk.Button(text='Disable DACs', command=externalLSAllPixels)
padConfigButt.grid(row=rmain + 9, column=3, columnspan=1, rowspan=1)
row_text = tk.Entry(width=25)
data_text = tk.Entry(width=25)
timing_text = tk.Entry(width=25)
clkSRAM_text = tk.Entry(width=25)
clkPISO_text = tk.Entry(width=25)
clkaddr_text = tk.Entry(width=25)
clkcnt_text = tk.Entry(width=25)
boardaddress_text = tk.Entry(width=25)
patchnum_text = tk.Entry(width=25)
row_text.grid(row=rmain + 1, column=5, pady=2)
data_text.grid(row=rmain + 2, column=5, pady=2)
timing_text.grid(row=rmain + 3, column=5, pady=2)
clkSRAM_text.grid(row=rmain + 7, column=5, pady=2)
clkPISO_text.grid(row=rmain + 8, column=5, pady=2)
clkaddr_text.grid(row=rmain + 9, column=5, pady=2)
clkcnt_text.grid(row=rmain + 10, column=5, pady=2)
boardaddress_text.grid(row=rmain + 12, column=5, pady=2)
patchnum_text.grid(row=rmain + 12, column=3, pady=2)
muxbutt = tk.Button(text='DL/AL Multiplexer', command=displayDLALMux)
sramrdbutt = tk.Button(text='SRAM Read', command=readFromSRAM)
sramwrbutt = tk.Button(text='SRAM Write', command=writeToSRAM)
mainwrbutt = tk.Button(text='Main Write', command=writeToMain)
boardaddressbutt = tk.Button(text='Board Address', command=boardAddressChange)
patchnumbutt = tk.Button(text='Number of Patches', command=patchNumber)
lsdacen = tk.Checkbutton(text='LS_DAC_EN', variable=lsdacenvar, onvalue=1, offvalue=0).grid(row=rmain + 11, column=4, sticky='e', pady=2)
clk_radio_fpga = tk.Radiobutton(text='FPGA_clk', variable=v, value=0).grid(row=rmain + 12, column=4, pady=2)
clk_radio_cryst = tk.Radiobutton(text='Crystal_clk', variable=v, value=1)
clk_radio_external = tk.Radiobutton(text='External_clk', variable=v, value=2).grid(row=rmain + 13, column=4, pady=2)
dlalmuxen = tk.Checkbutton(text='DL/AL_EN', variable=dlalvar, onvalue=1, offvalue=0, command=startdlal).grid(row=rmain + 5, column=4, sticky='e', pady=2)
muxbutt.grid(row=rmain + 4, column=4, sticky='e', pady=2)
sramrdbutt.grid(row=rmain + 4, column=5, pady=2)
sramwrbutt.grid(row=rmain + 5, column=5, pady=2)
mainwrbutt.grid(row=rmain + 11, column=5)
boardaddressbutt.grid(row=rmain + 13, column=5)
patchnumbutt.grid(row=rmain + 13, column=3)
sram_mux = tk.Label(text='SRAM/MUX Operations', height=2, width=25, font='Helvetica 18 bold')
row_lab = tk.Label(text='ROW', height=2, width=25)
data_lab = tk.Label(text='DATA', height=2, width=25)
timing_lab = tk.Label(text='TIMING', height=2, width=25)
main = tk.Label(text='Main Operations', height=2, width=25, font='Helvetica 18 bold')
clkSRAM_lab = tk.Label(text='CLK_SRAM (0-3)', height=2, width=25)
clkPISO_lab = tk.Label(text='CLK_PISO (0-3)', height=2, width=25)
clkaddr_lab = tk.Label(text='CLK_ADDR (0-3)', height=2, width=25)
clkcnt_lab = tk.Label(text='CLK_CNT (0-7)', height=2, width=25)
sram_mux.grid(row=rmain, column=4, columnspan=2, rowspan=1, padx=5, pady=5)
row_lab.grid(row=rmain + 1, column=4, pady=2)
data_lab.grid(row=rmain + 2, column=4, pady=2)
timing_lab.grid(row=rmain + 3, column=4, pady=2)
main.grid(row=rmain + 6, column=4, columnspan=2, rowspan=1, padx=5, pady=5)
clkSRAM_lab.grid(row=rmain + 7, column=4, pady=2)
clkPISO_lab.grid(row=rmain + 8, column=4, pady=2)
clkaddr_lab.grid(row=rmain + 9, column=4, pady=2)
clkcnt_lab.grid(row=rmain + 10, column=4, pady=2)
window.mainloop()
#return  removed
# global avgEn ## Warning: Unused global
# global cnts ## Warning: Unused global

# okay decompiling WearableSPECTGUI_RahulLall.pyc
