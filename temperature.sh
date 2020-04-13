#!/bin/bash

# Temperatur auslesen
tempread=`cat /sys/bus/w1/devices/28-0300a279f812/w1_slave`
#Formatieren
temp=`echo "scale=2; "\`echo ${tempread##*=}\`" / 1000" | bc`

#Ausgabe
echo "Die gemessene Temperatur beträgt" $temp "°C"
