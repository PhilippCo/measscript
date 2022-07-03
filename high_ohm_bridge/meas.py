#!/usr/bin/env python
# coding: utf-8

# In[1]:


import testgear
import time
import openpyxl as xls
import datetime
import numpy as np


# In[2]:


setup  = "Ref_W480_W481_Dut_A7"

ref    = 10  #10V Referenzspannung
offset = 10e-6 #10ppm +/- Offset bei Messung


# In[3]:


det        = testgear.Keithley.K617(gpib=8)
dmm        = testgear.HPAK.HP3458A(gpib=22, gwip="192.168.2.88")
mux        = testgear.HPAK.HP3488A(gpib=10, gwip="192.168.2.88")
ref_source = testgear.Knick.JS3010(gpib=11, gwip="192.168.2.88")
dut_source = testgear.Fluke.F5440B(gpib=20, gwip="192.168.2.88")
tc         = testgear.LakeShore.LS331(gpib=12)


# In[4]:


tc


# ### Determine Reference Value
# 
# just used to estimate the needed DMM range

# In[ ]:


test_voltage = 10

ref_source.set_output(test_voltage)
dut_source.set_output(0)

time.sleep(5)
rref = test_voltage / det.read_avg(10)["mean"]

print("estimated reference: {:0.6f} MOhm".format(rref*1e-6))

if rref < 100:
    exit()


# ### Determine DUT Value

# In[ ]:


test_voltage = 10

ref_source.set_output(enabled=False) #special for Knick -> fix in testgear lib!
dut_source.set_output(test_voltage)

time.sleep(5)
dut = test_voltage / det.read_avg(10)["mean"]

print("estimated DUT: {:0.6f} MOhm".format(dut*1e-6))

if dut < 100:
    exit()


# ### Estimate DUT voltage

# In[ ]:


utest = ref / rref * dut
utest


# In[ ]:


dmm.conf_function_DCV(mrange=utest, nplc=100)


# In[ ]:


dmm.query("RANGE?")


# ### Estimate rough zero voltages

# In[ ]:


def adjust_calibrator(start=0):
    act = dut_source.get_output().set_voltage
    dut_source.set_output(start)
    
    if np.abs(act - start) > 10:
        time.sleep(10)
        
    time.sleep(10)
    
    while True:
        res = det.read_avg(20)["mean"]
        print("residual current: {0:0.1f} pA".format(res*1e12))
     
        add = res * dut * -1
                
        if np.abs(res) < 2e-12:
            break
        else:
            act = dut_source.get_output().set_voltage

            print("set output to {0:0.6f} V".format(act + add))
            dut_source.set_output(act+add)

            time.sleep(10)            
    
    return dut_source.get_output().set_voltage


# In[ ]:





# In[ ]:


def read3458(channel, readings=3):
    mux.select_channel(4, channel)
    time.sleep(2)
    
    read = dmm.read_avg(readings)["mean"]
    
    #mux.write("OPEN 400")
    #mux.write("OPEN 401")
    
    return read


# In[ ]:


wb = xls.Workbook()
ws = wb.active
filename = time.strftime("%Y%m%d-%H%M%S")+"_" + setup + "_meas.xlsx"
ws.append(["time", "m10", "m11", "m12", "m20", "m21", "m22", "m30", "m31", "m32", "m40", "m41", "m42", "temperature"])

volt_delay = 8 #8
det_avg    = 10 #20


while True:
    ##determine rough voltages
    ref_source.set_output(-1*ref) #Reference Resistor to -10V
    time.sleep(5)

    pos_rough = adjust_calibrator()
    print("estimated +zero at V", pos_rough)
    print(" ")


    ref_source.set_output(ref) #Reference Resistor to +10V
    time.sleep(5)

    neg_rough = adjust_calibrator(start=-1*pos_rough)
    print("estimated -zero at V", neg_rough)
    print(" ")


    for count in range(0, 50):
        dut_source.set_output(0)
        ref_source.set_output(-1*ref) #Reference Resistor to -10V
        time.sleep(5)

        #Measurement 1: set calibrator to pos estimate + offset
        dut_source.set_output(pos_rough * (1+offset))
        time.sleep(volt_delay)
        m10 = read3458(1) #read ref voltage
        m11 = read3458(0) #read DUT voltage
        m12 = det.read_avg(det_avg)["mean"] #read current

        #Measurement 2: set calibrator to pos estimate + offset
        dut_source.set_output(pos_rough * (1-offset))
        time.sleep(volt_delay)
        m20 = read3458(1) #read ref voltage
        m21 = read3458(0) #read DUT voltage
        m22 = det.read_avg(det_avg)["mean"] #read current

        dut_source.set_output(0)
        ref_source.set_output(ref) #Reference Resistor to -10V
        time.sleep(5)

        #Measurement 3: set calibrator to neg estimate + offset
        dut_source.set_output(neg_rough * (1+offset))
        time.sleep(volt_delay)
        m30 = read3458(1) #read ref voltage
        m31 = read3458(0) #read DUT voltage
        m32 = det.read_avg(det_avg)["mean"] #read current

        #Measurement 4: set calibrator to neg estimate - offset
        dut_source.set_output(neg_rough * (1-offset))
        time.sleep(volt_delay)
        m40 = read3458(1) #read ref voltage
        m41 = read3458(0) #read DUT voltage
        m42 = det.read_avg(det_avg)["mean"] #read current


        data  = [datetime.datetime.today(), m10, m11, m12, m20, m21, m22, m30, m31, m32, m40, m41, m42, tc.get_temp()]

        pos_1 = m11 - ( m21-m11 ) / ( m22-m12 )  * m12
        pos_2 = (m10 + m20)/2

        neg_1 = m31 - ( m41 - m31 ) / ( m42 - m32 )  * m32
        neg_2 = (m30 + m40)/2

        ratio = (pos_1 - neg_1) / (pos_2 - neg_2)

        print(datetime.datetime.today(), count, ratio)
        ws.append(data)
        wb.save(filename)


# In[ ]:


#alles aus
ref_source.set_output(enabled=False) #special for Knick -> fix in testgear lib!
dut_source.set_output(0)


# während dritter Messung Guard Kabel an 5440B angeschlossen

# Nach der Messung Guard vom 5440B auf extern und Guard to LO am 3458A an

# In[ ]:




