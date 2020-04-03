#!/usr/bin/python
"""
Script for controlling the range sensor to measure the fill level in water cistern

Created on 30.03.2020

@author: Rainer Minixhofer
"""
#pylint: disable=C0103, W0603
import time
import logging
import requests
import RPi.GPIO as GPIO #pylint: disable=E0401
from gpiozero import CPUTemperature #pylint: disable=E0401

GPIO.setmode(GPIO.BCM)

Tc = 15
TRIG = 10
ECHO = 4
HEIGHTISEID = 25608
CPUTEMPISEID = 25611
WATERISEID = 25609
FILLINGISEID = 25610
STATIC_DETECT = False

degree_sign = u'\N{DEGREE SIGN}'

CISTERNAREA = 109270 # Base area of cistern in cm^2
CISTERNHEIGHT = 239 #estimated distance between sensor and cistern floor in cm needs to be measured
WATERMAXHEIGHT = 171.5 # Maximum water height in cistern in cm

logging.basicConfig(level=logging.INFO, \
	filename='/var/log/rangesensor.log', \
	filemode='a', format="%(asctime)s: %(name)s - %(levelname)s - %(message)s")

logging.info("Distance Measurement In Progress")

GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.remove_event_detect(ECHO)

def measure(channel):
    """
    Callback for flank detection at pin ECHO
    """

    global pulse_start
    global pulse_end
    if GPIO.input(channel) == 1:     # steigende Flanke, Startzeit speichern
        pulse_start = time.time()
    else:                         # fallende Flanke, Endezeit speichern
        pulse_end = time.time()

if not STATIC_DETECT:
    GPIO.add_event_detect(ECHO, GPIO.BOTH, callback=measure)

GPIO.output(TRIG, False)
logging.debug("Waiting For Sensor To Settle")
time.sleep(2)

#set trigger for 10us to high. The ultrasonic signal (8x40kHz bursts)
#is sent out with the falling flank #of the TRIG output.
GPIO.output(TRIG, True)
time.sleep(0.00001)
GPIO.output(TRIG, False)

#After the burst is sent the ECHO pin is going from low to high and
#stays high until the echo of the bursts is detected. Thus the duration
#between the low/high and the high/low flank is proportional to 2xthe
#distance sound travels in this time interval
#We thus measure the time between the two flanks with either an
#interrupt callback (when STATIC_DETECT is False) or looping in a while loop
#until the flank high/low occurs (when STATIC_DETECT is True).
if STATIC_DETECT:
    while GPIO.input(ECHO) == 0:
        pulse_start = time.time()

    while GPIO.input(ECHO) == 1:
        pulse_end = time.time()
else:
    #Wait a bit longer than maximum allowed time of high signal on ECHO pin.
    time.sleep(0.040)

#When the pulse duration is equal or longer than 38ms no echo has been detected
pulse_duration = pulse_end - pulse_start

#Distance is half of the sound speed times the pulse_duration
#Take approximation for temperature dependence of sound speed into account
distance = pulse_duration * (33140 + 60 * Tc) /2

distance = round(distance, 2)
height = CISTERNHEIGHT - distance # in cm
water = CISTERNAREA*height/1000 # in Liters
filling = height/WATERMAXHEIGHT*100 # in %
URL = 'http://homematic.minixint.at/config/xmlapi/statechange.cgi'

#write datum into homematic
if 0 <= filling < 110:

    try:
        result = requests.get(URL + '?ise_id=%d,%d,%d' % (HEIGHTISEID, WATERISEID, FILLINGISEID) + \
                                    '&new_value=%.1f,%d,%.2f' % (height, water, filling))
        logging.info(result.url)
    except requests.exceptions.RequestException as err:
        logging.error("Error occured, trying again later: ", exc_info=err)
        GPIO.cleanup()

    logging.info("Distance: %6.2f cm", distance)
    logging.info("Height: %6.2f cm", height)
    logging.info("Stored Water: %d Liters", water)
    logging.info("Fill Height: %.2f %%", filling)
else:
    logging.error("Measured height out of bounds (0%%<height<110%%)")

cpu = CPUTemperature()

logging.info("CPU Temp: %.2f degC", cpu.temperature)

try:
    result = requests.get(URL + '?ise_id=%d' % CPUTEMPISEID + '&new_value=%.2f' % cpu.temperature)
    logging.info(result.url)
except requests.exceptions.RequestException as err:
    logging.error("Error occured, trying again later: ", exc_info=err)
    GPIO.cleanup()

GPIO.cleanup()
