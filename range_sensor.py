#!/usr/bin/python
import RPi.GPIO as GPIO
import time
import requests
import logging

GPIO.setmode(GPIO.BCM)

TRIG = 10
ECHO = 4
ISEID = 25608
CISTERNHEIGHT = 250
logging.basicConfig(level=logging.INFO, \
	filename='/var/log/rangesensor.log', \
	filemode='a', format = "%(asctime)s: %(name)s - %(levelname)s - %(message)s")

logging.info("Distance Measurement In Progress")

GPIO.setup(TRIG,GPIO.OUT)
GPIO.setup(ECHO,GPIO.IN)

GPIO.output(TRIG, False)
logging.debug("Waiting For Sensor To Settle")
time.sleep(2)

GPIO.output(TRIG, True)
time.sleep(0.00001)
GPIO.output(TRIG, False)

while GPIO.input(ECHO)==0:
  pulse_start = time.time()

while GPIO.input(ECHO)==1:
  pulse_end = time.time()

pulse_duration = pulse_end - pulse_start

distance = pulse_duration * 17150

distance = round(distance, 2)
height = CISTERNHEIGHT - distance

#write datum into homematic
params = {'ise_id': ISEID, 'new_value': height}
URL = 'http://homematic.minixint.at/config/xmlapi/statechange.cgi'

try:
    result = requests.get(URL, params=params)
except requests.exceptions.RequestException as e:
    logging.error("Error occured, trying again later: ", exc_info=err)

logging.info("Distance: %6.2f cm", distance)
logging.info("Height: %6.2f cm", height)

GPIO.cleanup()
