#!/usr/bin/env python3

import os
import signal
import time
from threading import Event
from datetime import datetime
from datetime import timezone
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
import UpsPlusDevice


LOG_FILE_PATH="/var/log/upsplus.log"

# Create log file directory
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

logFileHandler = TimedRotatingFileHandler(LOG_FILE_PATH, when='D', interval=1, backupCount=7, encoding='utf-8', utc=True)
logStreamHandler = logging.StreamHandler()
logging.basicConfig(format='%(asctime)s [%(name)s][%(levelname)-4s] - %(message)s', level=logging.INFO, handlers=[logFileHandler,logStreamHandler])
logging.Formatter.converter = time.gmtime

log = logging.getLogger('UPS')


# Read configuration from file
CONFIG_FILE = 'upsplus.conf'
CONFIG_PATH_LIST = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), CONFIG_FILE)),
    os.path.abspath(os.path.join('/etc', CONFIG_FILE)),
]

config = configparser.ConfigParser()

def readConfig(configPath):
    if os.path.exists(configPath):
        try:
            config.read(configPath)
            log.info("Read config: %s", configPath)
            return True
        except:
            log.exception("Error read config: %s", configPath)
    return False
def loadConfig():
    for configPath in CONFIG_PATH_LIST:
        if (readConfig(configPath)):
            return True
    return False
def getConfig(key, default=None):
    if config.has_section('ups'):
        if type(default) is int:
            return config['ups'].getint(key, default)
        elif type(default) is float:
            return config['ups'].getfloat(key, default)
        elif type(default) is bool:
            return config['ups'].getboolean(key, default)
        else:
            return config['ups'].get(key, default)
    return default
loadConfig()

UPS_CONFIG = {}
def buildConfig(key, default):
    UPS_CONFIG[key] = getConfig(key, default)

buildConfig('powerFailureToShutdownTime', 600)
buildConfig('shutdownVoltage', 3.80)
buildConfig('shutdownCmd', 'sudo shutdown -h now')
buildConfig('shutdownCountdown', 30)
buildConfig('loopInterval', 5)
buildConfig('logStatusInterval', 60)
buildConfig('autoPowerOn', 1)
buildConfig('batteryProtectionVoltage', 3.50)
buildConfig('samplePeriod', 2)


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
    if powerInputType and (upsStatus['inaBatteryCurrent'] < 0):
        log.warning("Illegal ups status: powerInputType[%s] inaBatteryCurrent[%.3f], force powerInputType to empty", powerInputType, upsStatus['inaBatteryCurrent'])
        powerInputType = ''
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
