#!/usr/bin/env python3

import os
import signal
import time
from threading import Event
from datetime import datetime
from datetime import timezone
import logging
from logging.handlers import TimedRotatingFileHandler
import UpsPlusDevice

UPS_CONFIG = {
    # The timeout before shutdown the OS after power failure. Unit: second
    # E.g.:
    # Set to 10 * 60 will shutdown the OS after power failure for 10 minutes
    # Set to 0 will shutdown the OS immediately after power failure
    # Set to -1 will disable the timeout
    'powerFailureToShutdownTime': 10 * 60,
    # Shutdown the OS after battery voltage lower then this setting. Unit: V
    'shutdownVoltage': 3.90,
    # Set the threshold of UPS force power-off to prevent damage caused by battery over-discharge. Unit: V
    'batteryProtectionVoltage': 3.50,
    # Command to execute to shutdown the OS
    'shutdownCmd': 'sudo shutdown -h now',
    # Main loop interval. This is the maxium time to detect power failure
    'loopInterval': 5,
    # Path to save the log
    'logFilePath': '/var/log/upsplus.log',
    # Interval to log UPS status. Set to -1 to disable the status log
    'logStatusInterval': 60,
    # Set auto power on when power input connected. 1: enabled, 0: disabled
    'autoPowerOn': 1,
    # Shutdown countdown timer. UPS will power off on timeout. Be sure OS will finish shutdown before timeout. Unit: second
    'shutdownCountdown': 30,
    # Set the sample period. Unit: min default: 2 min
    'samplePeriod': 2,
}

# Create log file directory
os.makedirs(os.path.dirname(UPS_CONFIG['logFilePath']), exist_ok=True)

logFileHandler = TimedRotatingFileHandler(UPS_CONFIG['logFilePath'], when='D', interval=1, backupCount=7, encoding='utf-8', utc=True)
logStreamHandler = logging.StreamHandler()
logging.basicConfig(format='%(asctime)s [%(name)s][%(levelname)-4s] - %(message)s', level=logging.INFO, handlers=[logFileHandler,logStreamHandler])
logging.Formatter.converter = time.gmtime

log = logging.getLogger('UPS')
ups = UpsPlusDevice.get()



def getUpsPowerInputType():
    powerInput = ups.getPowerInput()

    powerInputType = ''
    if powerInput['typecVoltage'] > 4:
        powerInputType = 'TypeC'
    elif powerInput['microUsbVoltage'] > 4:
        powerInputType = 'MicroUSB'

    return powerInputType

############################## Main Loop ##############################
def upsLoop(context={}):
    log.info("-" * 60)

    currentTime = time.time()

    prevStatus = context.get('prevStatus') or {}
    prevPowerInType = prevStatus.get('powerInputType') or ''
    prevPowerFailure = not prevPowerInType

    upsStatus = ups.getStatus()

    powerInputType = ''
    powerInputVoltage = ''
    if upsStatus['typecVoltage'] > 4:
        powerInputType = 'TypeC'
        powerInputVoltage = upsStatus['typecVoltage']
    elif upsStatus['microUsbVoltage'] > 4:
        powerInputType = 'MicroUSB'
        powerInputVoltage = upsStatus['microUsbVoltage']
    powerFailure = not powerInputType

    newStatus = {
        'time': formatTimestamp(currentTime),
        'powerInputType': powerInputType,
        'powerInputVoltage': powerInputVoltage,
        'batteryVoltage': upsStatus['inaBatteryVoltage']
    }

    log.info(">"*20 + " UPS Loop " + ">"*20)

    # Update UPS device configuration
    if (upsStatus['batteryProtectionVoltage'] != UPS_CONFIG['batteryProtectionVoltage']):
        ups.setBatteryProtectionVoltage(round(UPS_CONFIG['batteryProtectionVoltage'] * 1000))    
    if (upsStatus['samplePeriod'] != UPS_CONFIG['samplePeriod']):
        ups.setSamplePeriod(UPS_CONFIG['samplePeriod'])
    if (upsStatus['autoPowerOn'] != UPS_CONFIG['autoPowerOn']):
        ups.setAutoPowerOn(UPS_CONFIG['autoPowerOn'])
    # Disable shutdown countdown
    if (upsStatus['shutdownCountdown'] != 0):
        ups.setShutdownCountdown(0)
    # Disable restart countdown
    if (upsStatus['restartCountdown'] != 0):
        ups.setRestartCountdown(0)

    shutdownNow = False

    if not powerFailure:
        log.info("Input power OK on %s", powerInputType)
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

    log.info("<"*20 + " UPS Loop " + "<"*20)

    newStatus['upsStatus'] = upsStatus
    if UPS_CONFIG['logStatusInterval'] >= 0:
        log.info("UPS status:")
        logDict(newStatus)

    if shutdownNow:
        shutdown()

    context['prevStatus'] = newStatus
    return newStatus

def shutdown():
    log.warning("X"*20 + " Shutdown on Power Failure " + "X"*20)
    log.warning("Shutdown the UPS after: %d seconds", UPS_CONFIG['shutdownCountdown'])
    ups.setShutdownCountdown(UPS_CONFIG['shutdownCountdown'])

    shutdownCmd = UPS_CONFIG['shutdownCmd']
    log.warning("Shutdown the OS by execute: %s", shutdownCmd)
    os.system(shutdownCmd)

    while True:
        time.sleep(10)

def formatTimestamp(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def logDict(value):
    __logDict("", value)

def __logDict(prefix, value):
    keyLenMax = 0
    for k in value.keys():
        keyLen = len(str(k))
        keyLenMax = keyLen if (keyLen > keyLenMax) else keyLenMax
    for (k, v) in value.items():
        if type(v) is not dict:
            log.info(prefix + str(k).ljust(keyLenMax) + ': ' + str(v))
        else:
            log.info(prefix + str(k).ljust(keyLenMax) + ':')
            __logDict(prefix + '    ', v)



exit = Event()

def exitHandler(_signo, _stack_frame):
    log.info("Receive signal[%d] to exit UPS daemon", _signo)
    exit.set()

def main():
    signal.signal(signal.SIGTERM, exitHandler)
    signal.signal(signal.SIGINT, exitHandler)

    context = {}
    context['prevLoopTime'] = time.time()
    while not exit.is_set():
        try:
            runLoop = False
            currentTime = time.time()

            prevPowerInputType = context.get('prevStatus').get('powerInputType') if context.get('prevStatus') else 'UnKnown'
            if getUpsPowerInputType() != prevPowerInputType:
                runLoop = True
            elif currentTime - context['prevLoopTime'] > UPS_CONFIG['logStatusInterval']:
                runLoop = True

            if runLoop:
                context['prevLoopTime'] = currentTime
                upsLoop(context)
        except:
            log.exception("Error in UPS daemon!")
        exit.wait(UPS_CONFIG['loopInterval'])

    log.info("Exit UPS daemon")

if __name__=="__main__":
    main()
