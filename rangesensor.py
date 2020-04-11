#!/usr/bin/python3 -u
"""
Script for controlling the range sensor to measure the fill level in water cistern
Is running in an infinite loop controlled via systemd.
Was copied from the original range_sensor.py script and rewritten for the
pigpio library which yields much better timing than the RPi.GPIO library

Created on 10.04.2020

@author: Rainer Minixhofer
"""
#pylint: disable=C0103, C0301, W0603, R0903
import os
import signal
import time
from datetime import datetime
import logging
import requests
import numpy as np
import pigpio #pylint: disable=E0401
from gpiozero import CPUTemperature #pylint: disable=E0401

class GracefulKiller:
    """
    Class for handling terminating signals (e.g. from systemd)
    """
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame): #pylint: disable=W0613
        """
        Function for setting kill_now parameter

        Parameters
        ----------
        signum : TYPE
            DESCRIPTION.
        frame : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        self.kill_now = True

killer = GracefulKiller()

pi = pigpio.pi()

Tc = 15 # Temperature for calculation of sound speed
MEASUREINTERVAL = 3*60 # Measure every three minutes
TRIG = 10 # GPIO Pin where the TRIG signal is connected
ECHO = 4 # GPIO PIN where the ECHO signal is connected
HEIGHTISEID = 25608 # ISE ID for Height systemvariable in Homematic
CPUTEMPISEID = 25611 # ISE ID for CPUTemp systemvariable in Homematic
WATERISEID = 25609  # ISE ID for Water systemvariable in Homematic
FILLINGISEID = 25610 # ISE ID for Filling systemvariable in Homematic
STATIC_DETECT = False # True if ECHO Signal should be detected statically, False if trigger based detection should be used
QPUMP = 65 # Maximum output rate in l/min of the waterpump. Used to calculate limit of height change per measurement interval

degree_sign = u'\N{DEGREE SIGN}'

CISTERNAREA = 109270 # Base area of cistern in cm^2
CISTERNHEIGHT = 239 #estimated distance between sensor and cistern floor in cm needs to be measured
WATERMAXHEIGHT = 171.5 # Maximum water height in cistern in cm
WATERFALLRATE = QPUMP*1000/CISTERNAREA # Maximum rate of sinking waterlevel change in cm/min when pump is running at max output rate

logging.basicConfig(level=logging.INFO, \
	filename='/var/log/rangesensor.log', \
	filemode='a', format="%(asctime)s: %(name)s - %(levelname)s - %(message)s")

#Enable next line if you want to see the log in stderr
logging.getLogger().addHandler(logging.StreamHandler())

logging.info("Daemon RangeSensor started.")

pi.set_mode(TRIG, pigpio.OUTPUT)
pi.set_mode(ECHO, pigpio.INPUT)

#GPIO.remove_event_detect(ECHO)

# Open datafile for processing

workdir = os.path.dirname(os.path.abspath(__file__))
logging.info("Working directory is %s", workdir)
datfile = workdir+"/range_sensor.dat"

logging.info('Reading previous data from datafile %s', datfile)
databuffer = np.genfromtxt(datfile, delimiter=',')
logging.info('Read %d lines', databuffer.shape[0])

if os.path.isfile(datfile):
    f = open(datfile, "a+", buffering=1)
else:
    f = open(datfile, "w", buffering=1)
    #Write Header when opened the first time
    f.write("DateTime,Distance,Height,Stored_Water,Fill_Height,CPU_Temp")

def measure(GPIO, level, tick):
    """
    Callback for flank detection at pin ECHO
    """

    global pulse_start
    global pulse_end
    if level == 1:     # steigende Flanke, Startzeit speichern
        pulse_start = tick
    else:                         # fallende Flanke, Endezeit speichern
        pulse_end = tick

pi.callback(ECHO, 2, measure)

pi.write(TRIG, False)
logging.info("Distance measurement daemon RangeSensor started. Waiting for sensor to settle")
time.sleep(2)


while not killer.kill_now:

    #set trigger for 10us to high. The ultrasonic signal (8x40kHz bursts)
    #is sent out with the falling flank #of the TRIG output.
    pi.gpio_trigger(TRIG, 10, 1)

    #After the burst is sent the ECHO pin is going from low to high and
    #stays high until the echo of the bursts is detected. Thus the duration
    #between the low/high and the high/low flank is proportional to 2xthe
    #distance sound travels in this time interval
    #We thus measure the time between the two flanks with an
    #interrupt callback.
    #Wait a bit longer than maximum allowed time of high signal on ECHO pin.
    time.sleep(0.040)

    #When the pulse duration is equal or longer than 38ms no echo has been detected
    #The time ticks of pigpio are wrapping around from 4294967295 to 0 thus we take the modulo
    pulse_duration = 10**-6*((pulse_end - pulse_start) % 4294967295)

    #Distance is half of the sound speed times the pulse_duration
    #Take approximation for temperature dependence of sound speed into account
    distance = pulse_duration * (33140 + 60 * Tc) /2

    distance = round(distance, 2)
    height = CISTERNHEIGHT - distance # in cm
    water = CISTERNAREA*height/1000 # in Liters
    filling = height/WATERMAXHEIGHT*100 # in %

    date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S") # current date and time

    URL = 'http://homematic.minixint.at/config/xmlapi/statechange.cgi'


    # Outlier Check

    #write datum into homematic
    if 0 <= filling < 110:

        try:
            result = requests.get(URL + '?ise_id=%d,%d,%d' % (HEIGHTISEID, WATERISEID, FILLINGISEID) + \
                                        '&new_value=%.1f,%d,%.2f' % (height, water, filling))
            logging.debug(result.url)
        except requests.exceptions.RequestException as err:
            logging.error("Error occured, trying again later: ", exc_info=err)

        logging.info("Distance: %6.2f cm", distance)
        logging.info("Height: %6.2f cm", height)
        logging.info("Stored Water: %5d Liters", water)
        logging.info("Fill Height: %.2f %%", filling)

    else:
        logging.error("Measured height out of bounds (0%%<height<110%%)")

    #np.append(databuffer, [[date_time, distance, height, water, filling]])

    f.write("%s,%6.2f,%6.2f,%5d,%.2f" % (date_time, distance, height, water, filling))

    cpu = CPUTemperature()

    logging.info("CPU Temp: %.2f degC", cpu.temperature)
    f.write(",%.2f\n" % (cpu.temperature))


    try:
        result = requests.get(URL + '?ise_id=%d' % CPUTEMPISEID + '&new_value=%.2f' % cpu.temperature)
        logging.debug(result.url)
    except requests.exceptions.RequestException as err:
        logging.error("Error occured, trying again later: ", exc_info=err)

    counter = MEASUREINTERVAL
    while not killer.kill_now and counter > 0:
        time.sleep(1)
        counter -= 1

f.close()
pi.stop()
logging.info("Daemon RangeSensor stopped.")
