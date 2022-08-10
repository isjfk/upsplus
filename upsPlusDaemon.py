#!/usr/bin/env python3

import os
import time
from datetime import datetime
from datetime import timezone
import logging
from logging.handlers import TimedRotatingFileHandler
import json
import smbus2
from ina219 import INA219

UPS_CONFIG = {
    # Shutdown the OS after battery voltage lower then this setting. Unit: V
    'shutdownVoltage': 3.90,
    # The timeout before shutdown the OS after power failure. Unit: second
    # E.g.:
    # Set to 10 * 60 will shutdown the OS after power failure for 10 minutes
    # Set to 0 will shutdown the OS immediately after power failure
    # Set to -1 will disable the timeout
    'powerFailureToShutdownTime': 10 * 60,
    # Command to execute to shutdown the OS
    'shutdownCmd': 'sudo shutdown -h now',
    # Log UPS status on read/write status file. Set to True if you want UPS status history in log
    'logStatus.read': False,
    'logStatus.write': True,
    # Path to save the log
    'logFilePath': os.getenv('HOME') + '/log/upsPlusDaemon.log',
    # Path to save UPS status. This file is required to calculate shutdown timeout
    'statusFilePath': '/tmp/upsPlusStatus.json',
}

UPS_DEVICE = {
    # Define I2C bus
    'bus': 1,
    # Define device i2c slave address
    'address': 0x17,
    # Set the sample period. Unit: min default: 2 min
    'samplePeriod': 2,
    # Set auto power on when charger connected. 1: enabled, 0: disabled
    'autoPowerOn': 1,
    # Set the threshold of UPS force power-off to prevent damage caused by battery over-discharge. Unit: V
    'batteryProtectionVoltage': 3.50,
    # Shutdown countdown timer. UPS will power off on timeout. Be sure OS will finish shutdown before timeout. Unit: second
    'shutdownCountdown': 30,
}

# Create log & status file directory
os.makedirs(os.path.dirname(UPS_CONFIG['logFilePath']), exist_ok=True)
os.makedirs(os.path.dirname(UPS_CONFIG['statusFilePath']), exist_ok=True)

logFileHandler = TimedRotatingFileHandler(UPS_CONFIG['logFilePath'], when='D', interval=1, backupCount=7, encoding='utf-8', utc=True)
logStreamHandler = logging.StreamHandler()
logging.basicConfig(format='%(asctime)s [%(name)s][%(levelname)-8s] - %(message)s', level=logging.INFO, handlers=[logFileHandler,logStreamHandler])
logging.Formatter.converter = time.gmtime

log = logging.getLogger('UPS')
log.setLevel(logging.INFO)

# Instance INA219.
ina_supply = INA219(0.00725, busnum=UPS_DEVICE['bus'], address=0x40)
ina_supply.configure()

# Raspberry Pi communicates with UPS via i2c protocol.
bus = smbus2.SMBus(UPS_DEVICE['bus'])

class DataOutOfRangeError(Exception):
    pass

def readUps():
    retryCount = 10
    while (retryCount > 0):
        try:
            return __readUps()
        except Exception as e:
            log.exception("Error read UPS status")
            retryCount -= 1
            if retryCount > 0:
                log.info("Retry read UPS status...")
                time.sleep(3)
            else:
                log.info("Abort read UPS status")
                raise e

def __readUps():
    ups = {}

    ups['inaSupplyVoltage'] = round(ina_supply.voltage(), 2)
    ups['inaSupplyCurrent'] = round(ina_supply.current() / 1000, 3)
    ups['inaSupplyPower'] = round(ina_supply.power() / 1000, 3)

    # Batteries information
    ina_battery = INA219(0.005, busnum=UPS_DEVICE['bus'], address=0x45)
    ina_battery.configure()
    ups['inaBatteryVoltage'] = round(ina_battery.voltage(), 2)
    ups['inaBatteryCurrent'] = round(ina_battery.current() / 1000, 3)
    ups['inaBatteryPower'] = round(ina_battery.power() / 1000, 3)

    # Read all register
    buf = []
    for i in range(0, 8):
        buf.extend(bus.read_i2c_block_data(UPS_DEVICE['address'], i * 32, 32))

    ups['mcuVoltage'] = round(float(buf[0x02] << 8 | buf[0x01]) / 1000, 2)
    ups['pogoPinVoltage'] = round(float(buf[0x04] << 8 | buf[0x03]) / 1000, 2)
    ups['batteryVoltage'] = round(float(buf[0x06] << 8 | buf[0x05]) / 1000, 2)
    ups['typecVoltage'] = round(float(buf[0x08] << 8 | buf[0x07]) / 1000, 2)
    ups['microUsbVoltage'] = round(float(buf[0x0A] << 8 | buf[0x09]) / 1000, 2)
    ups['batteryTemperature'] = round(float(buf[0x0C] << 8 | buf[0x0B]), 2)
    ups['batteryFullVoltage'] = round(float(buf[0x0E] << 8 | buf[0x0D]) / 1000, 2)
    ups['batteryEmptyVoltage'] = round(float(buf[0x10] << 8 | buf[0x0F]) / 1000, 2)
    ups['batteryProtectionVoltage'] = round(float(buf[0x12] << 8 | buf[0x11]) / 1000, 2)
    ups['batteryRemaining'] = round(float(buf[0x14] << 8 | buf[0x13]), 2)
    ups['samplePeriod'] = buf[0x16] << 8 | buf[0x15]
    ups['powerStatus'] = buf[0x17]
    ups['shutdownCountdown'] = buf[0x18]
    ups['autoPowerOn'] = buf[0x19]
    ups['restartCountdown'] = buf[0x1A]
    ups['reset'] = buf[0x1B]
    ups['accumulatedRunningTime'] = buf[0x1F] << 24 | buf[0x1E] << 16 | buf[0x1D] << 8 | buf[0x1C]
    ups['accumulatedChargingTime'] = buf[0x23] << 24 | buf[0x22] << 16 | buf[0x21] << 8 | buf[0x20]
    ups['currentRunningTime'] = buf[0x27] << 24 | buf[0x26] << 16 | buf[0x25] << 8 | buf[0x24]
    ups['version'] = buf[0x29] << 8 | buf[0x28]
    ups['batteryParameters'] = buf[0x2A]
    uid0 = "%08X" % (buf[0xF3] << 24 | buf[0xF2] << 16 | buf[0xF1] << 8 | buf[0xF0])
    uid1 = "%08X" % (buf[0xF7] << 24 | buf[0xF6] << 16 | buf[0xF5] << 8 | buf[0xF4])
    uid2 = "%08X" % (buf[0xFB] << 24 | buf[0xFA] << 16 | buf[0xF9] << 8 | buf[0xF8])
    ups['serialNumber'] = uid0 + '-' + uid1 + '-' + uid2

    if ups['mcuVoltage'] < 2.4 or ups['mcuVoltage'] > 3.6:
        raise DataOutOfRangeError("MCU voltage %.2f out of range [2.4, 3.6]" % ups['mcuVoltage'])
    if ups['pogoPinVoltage'] < 0 or ups['pogoPinVoltage'] > 5.5:
        raise DataOutOfRangeError("Pogo pin voltage %.2f out of range [0, 5.5]" % ups['pogoPinVoltage'])
    if ups['batteryVoltage'] < 0 or ups['batteryVoltage'] > 4.5:
        raise DataOutOfRangeError("Battery voltage %.2f out of range [0, 4.5]" % ups['batteryVoltage'])
    if ups['typecVoltage'] < 0 or ups['typecVoltage'] > 13.5:
        raise DataOutOfRangeError("TypeC voltage %.2f out of range [0, 13.5]" % ups['typecVoltage'])
    if ups['microUsbVoltage'] < 0 or ups['microUsbVoltage'] > 13.5:
        raise DataOutOfRangeError("MicroUSB voltage %.2f out of range [0, 13.5]" % ups['microUsbVoltage'])
    if ups['batteryTemperature'] < -20 or ups['batteryTemperature'] > 65:
        raise DataOutOfRangeError("Battery temperature %.0f out of range [-20, 65]" % ups['batteryTemperature'])
    if ups['batteryFullVoltage'] < 0 or ups['batteryFullVoltage'] > 4.5:
        raise DataOutOfRangeError("Battery full voltage %.2f out of range [0, 4.5]" % ups['batteryFullVoltage'])
    if ups['batteryEmptyVoltage'] < 0 or ups['batteryEmptyVoltage'] > 4.5:
        raise DataOutOfRangeError("Battery empty voltage %.2f out of range [0, 4.5]" % ups['batteryEmptyVoltage'])
    if ups['batteryProtectionVoltage'] < 0 or ups['batteryProtectionVoltage'] > 4.5:
        raise DataOutOfRangeError("Battery protection voltage %.2f out of range [0, 4.5]" % ups['batteryProtectionVoltage'])
    if ups['batteryRemaining'] < 0 or ups['batteryRemaining'] > 100:
        raise DataOutOfRangeError("Batter remaining %.0f out of range [0, 100]" % ups['batteryRemaining'])
    if ups['samplePeriod'] < 1 or ups['samplePeriod'] > 1440:
        raise DataOutOfRangeError("Sample period %d out of range [1, 1440]" % ups['samplePeriod'])
    if ups['powerStatus'] < 0 or ups['powerStatus'] > 1:
        raise DataOutOfRangeError("Power status %d out of range [0, 1]" % ups['powerStatus'])
    if ups['shutdownCountdown'] < 0 or ups['shutdownCountdown'] > 255:
        raise DataOutOfRangeError("Shutdown countdown %d out of range [0, 255]" % ups['shutdownCountdown'])
    if ups['autoPowerOn'] < 0 or ups['autoPowerOn'] > 1:
        raise DataOutOfRangeError("Auto power on %d out of range [0, 1]" % ups['autoPowerOn'])
    if ups['restartCountdown'] < 0 or ups['restartCountdown'] > 255:
        raise DataOutOfRangeError("Restart countdown %d out of range [0, 255]" % ups['restartCountdown'])
    if ups['reset'] < 0 or ups['reset'] > 1:
        raise DataOutOfRangeError("Reset %d out of range [0, 1]" % ups['reset'])
    if ups['accumulatedRunningTime'] < 0 or ups['accumulatedRunningTime'] > 2147483647:
        raise DataOutOfRangeError("Accumulated running time %d out of range [0, 2147483647]" % ups['accumulatedRunningTime'])
    if ups['accumulatedChargingTime'] < 0 or ups['accumulatedChargingTime'] > 2147483647:
        raise DataOutOfRangeError("Accumulated charging time %d out of range [0, 2147483647]" % ups['accumulatedChargingTime'])
    if ups['currentRunningTime'] < 0 or ups['currentRunningTime'] > 2147483647:
        raise DataOutOfRangeError("Current running time %d out of range [0, 2147483647]" % ups['currentRunningTime'])
    if ups['version'] == 0xFFFF:
        raise DataOutOfRangeError("Version %d out of range" % ups['version'])
    if ups['batteryParameters'] == 0xFF:
        raise DataOutOfRangeError("Battery parameters %d out of range" % ups['batteryParameters'])
    if ups['serialNumber'] == 'FFFFFFFF-FFFFFFFF-FFFFFFFF':
        raise DataOutOfRangeError("Serial number %s out of range" % ups['serialNumber'])

    return ups

def shutdown():
    setUpsShutdownCountdown(UPS_DEVICE['shutdownCountdown'])

    shutdownCmd = UPS_CONFIG['shutdownCmd']
    log.warning("Shutdown the OS by execute: %s", shutdownCmd)
    os.system(shutdownCmd)

    while True:
        time.sleep(10)

def setUpsBatteryProtectionVoltage(value):
    writeUpsRegister(0x11, [ value & 0xFF, (value >> 8) & 0xFF ])
    log.info("Set UPS battery projection voltage to %d", value & 0xFFFF)

def setUpsSamplePeriod(value):
    writeUpsRegister(0x15, [ value & 0xFF, (value >> 8) & 0xFF ])
    log.info("Set UPS sample period to %d", value & 0xFFFF)

def setUpsShutdownCountdown(value):
    writeUpsRegister(0x18, value)
    log.info("Set UPS shutdown countdown to %d", value)

def setUpsAutoPowerOn(value):
    writeUpsRegister(0x19, value)
    log.info("Set UPS auto power on to %d", value)

def setUpsRestartCountdown(value):
    writeUpsRegister(0x1A, value)
    log.info("Set UPS restart countdown to %d", value)

def writeUpsRegister(register, values):
    retryCount = 10
    while (retryCount > 0):
        try:
            return __writeUpsRegister(register, values)
        except Exception as e:
            log.exception("Error write UPS register")
            retryCount -= 1
            if retryCount > 0:
                log.info("Retry write UPS register...")
                time.sleep(3)
            else:
                log.info("Abort write UPS register")
                raise e

def __writeUpsRegister(register, values):
    if type(values) is not list:
        values = [values]
    for i, value in enumerate(values):
        bus.write_byte_data(UPS_DEVICE['address'], register + i, value)

def readStatus():
    statusFilePath = UPS_CONFIG['statusFilePath']
    try:
        if os.path.exists(statusFilePath):
            with open(statusFilePath, 'r') as statusFile:
                status = json.load(statusFile)
            if UPS_CONFIG['logStatus.read']:
                log.info("Read status file [%s]: %s", statusFilePath, json.dumps(status, indent=4))
            else:
                log.info("Read status file [%s]", statusFilePath)
            return status
        else:
            log.info("Status file [%s] not existed", statusFilePath)
            return {}
    except:
        log.exception("Error read status file [%s]", statusFilePath)
        deleteStatus()

def saveStatus(status):
    statusFilePath = UPS_CONFIG['statusFilePath']
    try:
        with open(statusFilePath, 'w') as statusFile:
            json.dump(status, statusFile)
        if UPS_CONFIG['logStatus.write']:
            log.info("Save status file [%s]: %s", statusFilePath, json.dumps(status, indent=4))
        else:
            log.info("Save status file [%s]", statusFilePath)
    except:
        log.exception("Error save status file [%s]", statusFilePath)
        deleteStatus()

def deleteStatus(reason=None):
    statusFilePath = UPS_CONFIG['statusFilePath']
    try:
        if reason:
            logSuffix = "for %s" % reason
        else:
            logSuffix = "for fail safe"

        if os.path.exists(statusFilePath):
            log.warning("Delete status file [%s] %s...", statusFilePath, logSuffix)
            os.remove(statusFilePath)
            log.warning("Delete status file [%s] success", statusFilePath)
    except:
        log.exception("Error delete status file [%s]", statusFilePath)

def formatTimestamp(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")



############################## Main ##############################
def upsDaemon():
    currentTime = time.time()

    prevStatus = readStatus()
    if prevStatus.get('timestamp') and abs(currentTime - prevStatus.get('timestamp')) > 3*60:
        log.warning("Previous timestamp [%s] out of range, ignore previous status", formatTimestamp(prevStatus.get('timestamp')))
        deleteStatus()
        prevStatus = {}

    prevChargingType = prevStatus.get('chargingType') or ''
    prevPowerFailure = not prevChargingType

    upsStatus = readUps()

    if upsStatus['typecVoltage'] > 4:
        chargingType = 'TypeC'
    elif upsStatus['microUsbVoltage'] > 4:
        chargingType = 'MicroUSB'
    else:
        chargingType = ''
    powerFailure = not chargingType

    newStatus = {
        'timestamp': currentTime,
        'time': formatTimestamp(currentTime),
        'chargingType': chargingType,
        'batteryVoltage': upsStatus['inaBatteryVoltage']
    }

    log.info("#" * 40)

    # Update UPS device configuration
    if (upsStatus['batteryProtectionVoltage'] != UPS_DEVICE['batteryProtectionVoltage']):
        setUpsBatteryProtectionVoltage(round(UPS_DEVICE['batteryProtectionVoltage'] * 1000))    
    if (upsStatus['samplePeriod'] != UPS_DEVICE['samplePeriod']):
        setUpsSamplePeriod(UPS_DEVICE['samplePeriod'])
    if (upsStatus['autoPowerOn'] != UPS_DEVICE['autoPowerOn']):
        setUpsAutoPowerOn(UPS_DEVICE['autoPowerOn'])
    # Disable shutdown countdown
    if (upsStatus['shutdownCountdown'] != 0):
        setUpsShutdownCountdown(0)
    # Disable restart countdown
    if (upsStatus['restartCountdown'] != 0):
        setUpsRestartCountdown(0)

    shutdownNow = False

    if not powerFailure:
        log.info("Input power OK on %s", chargingType)
    else:
        if not prevPowerFailure:
            log.warning("Input power failure detected, running on battery!")
            newStatus['powerFailureTimestamp'] = currentTime
            newStatus['powerFailureTime'] = formatTimestamp(currentTime)
        else:
            log.warning("Input power failure continue, running on battery!")
            if (prevStatus.get('powerFailureTimestamp') is None) or (prevStatus.get('powerFailureTimestamp') >= currentTime):
                log.warning("Power failure time not valid, reset to current time")
                newStatus['powerFailureTimestamp'] = currentTime
                newStatus['powerFailureTime'] = formatTimestamp(currentTime)
            else:
                # Keep power failure time to calculate power off time
                newStatus['powerFailureTimestamp'] = prevStatus.get('powerFailureTimestamp')
                newStatus['powerFailureTime'] = prevStatus.get('powerFailureTime')

        if UPS_CONFIG['powerFailureToShutdownTime'] >= 0:
            shutdownTimeout = UPS_CONFIG['powerFailureToShutdownTime'] - round(currentTime - newStatus['powerFailureTimestamp'])
            if shutdownTimeout > 0:
                log.warning("About to shutdown in %d seconds", shutdownTimeout)
            else:
                log.warning("About to shutdown immediately due to power failure timeout")
                shutdownNow = True

        if not shutdownNow:
            if newStatus['batteryVoltage'] > UPS_CONFIG['shutdownVoltage']:
                log.warning("About to shutdown after batteryVoltage[%.3f] <= shutdownVoltage[%.3f]", newStatus['batteryVoltage'], UPS_CONFIG['shutdownVoltage'])
            else:
                log.warning("About to shutdown immediately due to batteryVoltage[%.3f] <= shutdownVoltage[%.3f]", newStatus['batteryVoltage'], UPS_CONFIG['shutdownVoltage'])
                shutdownNow = True

    if shutdownNow:
        deleteStatus("shutdown")
        shutdown()
    else:
        log.info("#" * 40)
        newStatus['upsStatus'] = upsStatus
        saveStatus(newStatus)

def main():
    try:
        log.info("-" * 60)
        upsDaemon()
    except:
        log.exception("Error in UPS daemon!")
        deleteStatus()

if __name__=="__main__":
    main()
