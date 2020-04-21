#!/usr/bin/python3 -u
"""
Script for controlling the range sensor to measure the fill level in water cistern
Is running in an infinite loop controlled via systemd.
Was copied from the original range_sensor.py script and rewritten for the
pigpio library which yields much better timing than the RPi.GPIO library

Created on 10.04.2020

@author: Rainer Minixhofer
"""
#pylint: disable=C0103, C0301, W0603, R0903, R1722
import os
import re
import signal
import time
from datetime import datetime
import logging
import argparse
import requests
import numpy as np
import pigpio #pylint: disable=E0401
import wiringpi #pylint: disable=E0401
from gpiozero import CPUTemperature #pylint: disable=E0401


#Parse command line
parser = argparse.ArgumentParser(description='Process arguments when used in command line mode')

# Argument to specify interval in seconds between cistern height measurements
parser.add_argument('--measureinterval',
                    nargs='?',
                    const=3*60,
                    default=3*60,
                    type=int,
                    help='Measure interval [seconds] between fill height measurements. \
			If set to 0 then just one measurement is taken. \
                        (Default 3mins = 3*60 seconds)')
parser.add_argument('--averaging',
                    nargs='?',
                    const=50,
                    default=50,
                    type=int,
                    help='If specified the sensor is measuring <averaging> times. \
			              The median of the <averaging> number of measurements is \
                          taken and outliers are skipped which are deviating more \
                          than 2*sigma from this median. The remaining measurements are \
                          averaged for the result. (Default 50)')
# Argument to specify location of ASI SDK Library (default specified in env_filename
parser.add_argument('--GPIOlib',
                    nargs='?',
                    const='PiGPIO',
                    default='PiGPIO',
                    help='GPIO library to be used. Currently WiringPi and PiGPIO are \
                        supported. (Default PiGPIO)')
# If specified the logging messages are output to stdout as well
parser.add_argument('--stdoutlog',
                    action='store_true',
                    help='Output of log messages to stdout in addition to rangesensor system log.')
# If specified the debug messages are logged as well
parser.add_argument('--debug',
                    action='store_true',
                    help='Include debugging messages in the log as well \
                          (default False).')
# If specified the ECHO pulse duration between up and down flanks is measured statically
# through pin state change instead of the default flank detection callback.
parser.add_argument('--staticdetect',
                    action='store_true',
                    help='If specified the ECHO pulse duration between up and down \
                        flanks is measured statically through pin state change \
                            instead of the default flank detection callback.')

args = parser.parse_args()

#Setup logging engine
loglevel = logging.DEBUG if args.debug else logging.INFO
logging.basicConfig(level=loglevel, \
	filename='/var/log/rangesensor.log', \
	filemode='a', format="%(asctime)s: %(name)s - %(levelname)s - %(message)s")

#if you want to see the log in stderr
if args.stdoutlog:
    logging.getLogger().addHandler(logging.StreamHandler())

logging.info("Daemon RangeSensor started.")

#Check consistency of command line arguments

if args.GPIOlib.lower() not in ['wiringpi', 'pigpio']:
    logging.error("Only WiringPI and PiGPIO as GPIO libraries supported.")
    exit()
else:
    usewiringpi = (args.GPIOlib.lower() == 'wiringpi')

if args.averaging*0.05 > args.measureinterval > 0:
    logging.error("Total averaging time takes longer than interval between measurements.")
    exit()

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

if usewiringpi:
#    GPIO.setmode(GPIO.BCM)
    wiringpi.wiringPiSetupGpio()
else:
    pi = pigpio.pi()

Tair = 15 # Temperature for calculation of sound speed
DS18B20ID = "28-0300a279f812" # ID of external temperature sensor
MEASUREINTERVAL = args.measureinterval # Measure every three minutes
#MEASUREINTERVAL = 10 # Measure every three minutes
TRIG = 10 # GPIO Pin where the TRIG signal is connected
ECHO = 17 # GPIO PIN where the ECHO signal is connected
TEMP = 4 # GPIO PIN where the 1-wire temperature sensor is connected
HEIGHTISEID = 25608 # ISE ID for Height systemvariable in Homematic
AIRTEMPISEID = 25612 # ISE ID for air temperature measurement in Homematic
CPUTEMPISEID = 25611 # ISE ID for CPUTemp systemvariable in Homematic
WATERISEID = 25609  # ISE ID for Water systemvariable in Homematic
FILLINGISEID = 25610 # ISE ID for Filling systemvariable in Homematic
QPUMP = 65 # Maximum output rate in l/min of the waterpump. Used to calculate limit of height change per measurement interval
OUTLIERSIGMAFACT = 2 # Consider every measurement outside the interval [median - <OUTLIERSIGMAFACT>*sigma, median + <OUTLIERSIGMAFACT>*sigma] an outlier

degree_sign = u'\N{DEGREE SIGN}'

CISTERNAREA = 109270 # Base area of cistern in cm^2
CISTERNHEIGHT = 239 #estimated distance between sensor and cistern floor in cm needs to be measured
WATERMAXHEIGHT = 171.5 # Maximum water height in cistern in cm
WATERFALLRATE = QPUMP*1000/CISTERNAREA # Maximum rate of sinking waterlevel change in cm/min when pump is running at max output rate

pulse_start = None
pulse_end = None

if usewiringpi:
    wiringpi.pinMode(TRIG, wiringpi.GPIO.INPUT)
    wiringpi.pinMode(ECHO, wiringpi.GPIO.OUTPUT)
    wiringpi.pullUpDnControl(ECHO, wiringpi.GPIO.PUD_OFF)
#    GPIO.setup(TRIG, GPIO.OUT)
#    GPIO.setup(ECHO, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
#    GPIO.remove_event_detect(ECHO)
else:
    pi.set_mode(TRIG, pigpio.OUTPUT)
    pi.set_mode(ECHO, pigpio.INPUT)
    pi.set_pull_up_down(ECHO, pigpio.PUD_OFF)

# Open datafile for processing

workdir = os.path.dirname(os.path.abspath(__file__))
logging.debug("Working directory is %s", workdir)
datfile = workdir+"/rangesensor.dat"

if os.path.isfile(datfile):
    f = open(datfile, "a+", buffering=1)
    logging.info('Reading previous data from datafile %s', datfile)
    databuffer = np.genfromtxt(datfile, delimiter=',')
    logging.info('Read %d lines', databuffer.shape[0])

else:
    f = open(datfile, "w", buffering=1)
    #Write Header when opened the first time
    f.write("DateTime,Distance,Height,Stored_Water,Fill_Height,CPU_Temp,Air_Temp")
    databuffer = np.array([])

def measure_temperature(devid):
    """

    Parameters
    ----------
    def measure_temperature : TYPE
        Reads temperature from device-file with the ID devid

    Returns
    -------
    Float
        Temperature in degrees Celsius.

    """
    devf = open("/sys/bus/w1/devices/"+devid+"/w1_slave", "r")
    devcont = devf.read()
    tstring = re.search(r"t=(\d+)\n", devcont).group(1)
    devf.close()
    return int(tstring)/1000

def measure_flank_time_pigpio(pin, level, tick):
    """
    Callback for flank detection at pin ECHO
    """

    global pulse_start
    global pulse_end

    if pin == ECHO:
        if level == 1:     # steigende Flanke, Startzeit speichern
            pulse_start = tick
        else:                         # fallende Flanke, Endezeit speichern
            pulse_end = tick

def measure_flank_time_wiringpi():
    """
    Callback for flank detection at pin ECHO
    """

    global pulse_start
    global pulse_end
    if wiringpi.digitalRead(ECHO) == 1:
        # Rising Flank, save start time
        pulse_start = wiringpi.micros()
    else:
        # Falling Flank, save end time
        pulse_end = wiringpi.micros()
    return True

if usewiringpi:
    if not args.staticdetect:
        wiringpi.wiringPiISR(ECHO, wiringpi.GPIO.INT_EDGE_BOTH, \
                             measure_flank_time_wiringpi)
#        GPIO.add_event_detect(ECHO, GPIO.BOTH, callback=measure_flank_time_wiringpi)
    wiringpi.digitalWrite(TRIG, 0)
#    GPIO.output(TRIG, False)
else:
    if not args.staticdetect:
        pi.callback(ECHO, 2, measure_flank_time_pigpio)
    pi.write(TRIG, False)

logging.info("Distance measurement daemon RangeSensor started. Waiting for sensor to settle")
time.sleep(2)


while not killer.kill_now:


    #First measure air temperature to get sonic speed temperature dependence
    Tair = measure_temperature(DS18B20ID)
    logging.info("Air Temp: %.2f degC", Tair)

    cpu = CPUTemperature()
    logging.info("CPU Temp: %.2f degC", cpu.temperature)

    arr = np.zeros(args.averaging)

    for idx, _ in np.ndenumerate(arr):
        #set trigger for 10us to high. The ultrasonic signal (8x40kHz bursts)
        #is sent out with the falling flank #of the TRIG output.
        logging.debug("Send Trigger pulse on TRIG pin")
        if usewiringpi:
            wiringpi.digitalWrite(TRIG, 1)
    #        GPIO.output(TRIG, True)
            wiringpi.delayMicroseconds(10)
    #        time.sleep(0.00001) # Not very accurate. Need better solution
            wiringpi.digitalWrite(TRIG, 0)
    #        GPIO.output(TRIG, False)
        else:
            pi.gpio_trigger(TRIG, 10, 1)

        #After the burst is sent the ECHO pin is going from low to high and
        #stays high until the echo of the bursts is detected. Thus the duration
        #between the low/high and the high/low flank is proportional to 2xthe
        #distance sound travels in this time interval
        #We thus measure the time between the two flanks with either an
        #interrupt callback (when args.staticdetect is False) or looping in a while loop
        #until the flank high/low occurs (when args.staticdetect is True).
        logging.debug("Iteration %d: Waiting for response", idx[0]+1)
        if args.staticdetect:
            while usewiringpi and wiringpi.digitalRead(ECHO) == 0 or not usewiringpi and pi.read(ECHO) == 0:
                pulse_start = time.time()
            while usewiringpi and wiringpi.digitalRead(ECHO) == 1 or not usewiringpi and pi.read(ECHO) == 1:
                pulse_end = time.time()
            #Convert into Microseconds timing
            pulse_end = (pulse_end - pulse_start)*10**6
            pulse_start = 0
        else:
            #Wait a bit longer than maximum allowed time of high signal on ECHO pin.
            if usewiringpi:
                wiringpi.delay(40)
            else:
                time.sleep(0.040)
        #The time ticks are wrapping around at the max value of an unsigned 32-bit number thus we take the modulo
        logging.debug("Detected rising edge at time-stamp %d", pulse_start)
        logging.debug("Detected falling edge at time-stamp %d", pulse_end)
        pulse_duration = ((pulse_end - pulse_start) % int('0b'.ljust(34, '1'), 2))
        arr[idx] = pulse_duration
        logging.debug("ECHO Pulse duration %.1f us", pulse_duration)

    # Drop all measurements which deviate more than 3xStandardDeviation from Median value
    print(arr)
    pd_median = np.median(arr)
    pd_stddev = OUTLIERSIGMAFACT * np.std(arr)
    selector = ((pd_median - pd_stddev) < arr) & (arr < (pd_median + pd_stddev))
    nroutliers = np.count_nonzero(np.invert(selector))
    if nroutliers > 0:
        logging.info("We have %d outlier(s) which have been dropped from averaging.", nroutliers)
    arr = arr[selector]
    pulse_duration = np.mean(arr)

    logging.debug("ECHO Pulse duration %.1f us", pulse_duration)

    #When the pulse duration is equal or longer than 38ms no echo has been detected

    #Distance is half of the sound speed times the pulse_duration
    #Take approximation for temperature dependence of sound speed into account
    distance = pulse_duration *10**-6 * (33140 + 60 * Tair) /2

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
        logging.error("Measured fill height out of bounds (0%%<%.2f<110%%)", filling)
        logging.info("Pulse Duration: %6.2f us", pulse_duration*10**6)
        logging.info("Distance: %6.2f cm", distance)

    #np.append(databuffer, [[date_time, distance, height, water, filling]])

    f.write("%s,%6.2f,%6.2f,%5d,%.2f" % (date_time, distance, height, water, filling))
    f.write(",%.2f,%.2f\n" % (cpu.temperature, Tair))

    try:
        result = requests.get(URL + '?ise_id=%d' % CPUTEMPISEID + '&new_value=%.2f' % cpu.temperature)
        logging.debug(result.url)
        result = requests.get(URL + '?ise_id=%d' % AIRTEMPISEID + '&new_value=%.2f' % Tair)
        logging.debug(result.url)

    except requests.exceptions.RequestException as err:
        logging.error("Error occured, trying again later: ", exc_info=err)

    if MEASUREINTERVAL > 0:
        counter = MEASUREINTERVAL
        while not killer.kill_now and counter > 0:
            wiringpi.delay(1000)
#            time.sleep(1)
            counter -= 1
    else:
        killer.kill_now = True

f.close()
if not usewiringpi:
    pi.stop()
logging.info("Daemon RangeSensor stopped.")
