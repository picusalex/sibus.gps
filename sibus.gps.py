#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import signal
import sys
import time

import serial as serial

from sibus_lib import BusElement, sibus_init, MessageObject

SERVICE_NAME = "sibus.gps"
logger, cfg_data = sibus_init(SERVICE_NAME)

gps_data = {
    'fix_time': None,
    'fix_quality': None,
    'satellites': None,
    'validity': None,
    'latitude': None,
    'latitude_hemisphere': None,
    'latitude_decimal': None,
    'longitude': None,
    'longitude_hemisphere': None,
    'longitude_decimal': None,
    'accuracy_m': None,
    'altitude_m': None,
    'speed_knots': None,
    'speed_kmh': None,
    'true_course': None,
    'fix_date': None,
    'variation': None,
    'variation_e_w': None,
}


# Helper function to take HHMM.SS, Hemisphere and make it decimal:
def degrees_to_decimal(data, hemisphere):
    try:
        decimalPointPosition = data.index('.')
        degrees = float(data[:decimalPointPosition - 2])
        minutes = float(data[decimalPointPosition - 2:]) / 60
        output = degrees + minutes
        if hemisphere is 'N' or hemisphere is 'E':
            return output
        if hemisphere is 'S' or hemisphere is 'W':
            return -output
    except:
        return -1


# Helper function to take knots and make it km/h:
def knots_to_kmh(data):
    try:
        return float(data) * 1.852
    except:
        return -1


# Helper function to take a $GPRMC sentence, and turn it into a Python dictionary.
# This also calls degrees_to_decimal and stores the decimal values as well.
def parse_GPRMC(data):
    global gps_data
    data = data.split(',')

    gps_data['fix_time'] = data[1]
    gps_data['validity'] = data[2]
    gps_data['latitude'] = data[3]
    gps_data['latitude_hemisphere'] = data[4]
    gps_data['longitude'] = data[5]
    gps_data['longitude_hemisphere'] = data[6]
    gps_data['speed_knots'] = data[7]
    gps_data['true_course'] = data[8]
    gps_data['fix_date'] = data[9]
    gps_data['variation'] = data[10]
    gps_data['variation_e_w'] = data[11]

    gps_data['latitude_decimal'] = degrees_to_decimal(gps_data['latitude'], gps_data['latitude_hemisphere'])
    gps_data['longitude_decimal'] = degrees_to_decimal(gps_data['longitude'], gps_data['longitude_hemisphere'])
    gps_data['speed_kmh'] = knots_to_kmh(gps_data['speed_knots'])


# Helper function to take a $GPGGA sentence, and turn it into a Python dictionary.
# This also calls degrees_to_decimal and stores the decimal values as well.
def parse_GPGGA(data):
    global gps_data
    data = data.split(',')

    gps_data['fix_time'] = data[1]
    gps_data['latitude'] = data[2]
    gps_data['latitude_hemisphere'] = data[3]
    gps_data['longitude'] = data[4]
    gps_data['longitude_hemisphere'] = data[5]
    gps_data['fix_quality'] = data[6]
    gps_data['satellites'] = data[7]
    gps_data['accuracy_m'] = data[8]
    gps_data['altitude_m'] = data[9]
    gps_data['latitude_decimal'] = degrees_to_decimal(gps_data['latitude'], gps_data['latitude_hemisphere'])
    gps_data['longitude_decimal'] = degrees_to_decimal(gps_data['longitude'], gps_data['longitude_hemisphere'])


def start_gps(dev):
    if not os.path.exists(dev):
        logger.error("Device '%s' does not exist !" % dev)
        message = MessageObject(data={
            "error": "Device '%s' does not exist !" % dev
        }, topic="info.gps.status.error")
        busclient.publish(message)
        return

    logger.info("Starting GPS on '%s'" % dev)
    # Set up serial:
    ser = serial.Serial(
        port=dev,
        baudrate=115200,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1)

    message = MessageObject(data={
        "device": dev
    }, topic="info.gps.status.connected")
    busclient.publish(message)

    # Main program loop:
    while True:
        try:
            line = ser.readline()
        except serial.SerialException as e:
            logger.error(e)
            break

        line = line.strip()
        logger.debug(line)
        if "$GPRMC" in line:
            data = parse_GPRMC(line)
        elif "$GPGGA" in line:
            data = parse_GPGGA(line)
        else:
            continue

        message = MessageObject(data=gps_data, topic="info.gps.data")
        busclient.publish(message)

    message = MessageObject(data={
        "device": dev
    }, topic="info.gps.status.disconnected")
    busclient.publish(message)


busclient = BusElement(SERVICE_NAME)
busclient.start()


def sigterm_handler(_signo=None, _stack_frame=None):
    busclient.stop()
    logger.info("Program terminated correctly")
    sys.exit(0)


signal.signal(signal.SIGTERM, sigterm_handler)

try:
    while 1:
        start_gps("/dev/ttyACM0")
        time.sleep(5)
except KeyboardInterrupt:
    logger.info("Ctrl+C detected !")
except Exception as e:
    busclient.stop()
    logger.exception("Program terminated incorrectly ! " + str(e))
    sys.exit(1)
finally:
    sigterm_handler()
