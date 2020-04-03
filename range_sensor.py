#!/usr/bin/python
"""
Script for controlling the range sensor to measure the fill level in water cistern

Created on 30.03.2020

@author: Rainer Minixhofer
"""
#pylint: disable=C0103
import time
import logging
import requests
import RPi.GPIO as GPIO #pylint: disable=E0401
from gpiozero import CPUTemperature #pylint: disable=E0401

GPIO.setmode(GPIO.BCM)

TRIG = 10
ECHO = 4
HEIGHTISEID = 25608
CPUTEMPISEID = 25611
WATERISEID = 25609
FILLINGISEID = 25610

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

GPIO.output(TRIG, False)
logging.debug("Waiting For Sensor To Settle")
time.sleep(2)

GPIO.output(TRIG, True)
time.sleep(0.00001)
GPIO.output(TRIG, False)

while GPIO.input(ECHO) == 0:
    pulse_start = time.time()

while GPIO.input(ECHO) == 1:
    pulse_end = time.time()

pulse_duration = pulse_end - pulse_start

distance = pulse_duration * 17150

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
