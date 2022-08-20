#!/usr/bin/env python3

import time
import logging
import smbus2
from ina219 import INA219

log = logging.getLogger('UPS')

class UpsPlusDevice:

    def __init__(self, config={}):
        self.config = config

        _setDefault(self.config, 'bus', 0x1)
        _setDefault(self.config, 'outputAddress', 0x40)
        _setDefault(self.config, 'outputShuntOhms', 0.00725)
        _setDefault(self.config, 'batteryAddress', 0x45)
        _setDefault(self.config, 'batteryShuntOhms', 0.005)
        _setDefault(self.config, 'upsAddress', 0x17)

        self.inaOutput = INA219(self.config['outputShuntOhms'], busnum=self.config['bus'], address=self.config['outputAddress'])
        self.inaOutput.configure()

        self.inaBattery = INA219(self.config['batteryShuntOhms'], busnum=self.config['bus'], address=self.config['batteryAddress'])
        self.inaBattery.configure()

        self.bus = smbus2.SMBus(self.config['bus'])

    def getPowerInput(self):
        return self.__invokeWithRetry(self.__getPowerInput, "read UPS power input status")

    def getStatus(self):
        return self.__invokeWithRetry(self.__getStatus, "read UPS status")

    def __invokeWithRetry(self, func, desc):
        retryCount = 0
        retryMax = 10
        while (retryCount < retryMax):
            try:
                return func()
            except Exception as e:
                log.exception("Error %s", desc)
                retryCount += 1
                if retryCount < retryMax:
                    log.info("Retry %s for %d time...", desc, retryCount)
                    time.sleep(2)
                else:
                    log.info("Abort %s after %d retries", desc, retryCount)
                    raise e

    def __getPowerInput(self):
        ups = {}

        # Initialize with empty prefix so we don't have to use differnt register address offset on parse data
        buf = [ 0x0 ] * 0x07
        # Read registers 0x07 - 0x0A
        buf.extend(self.readRegister(0x07, 0x4))

        ups['typecVoltage'] = round(float(buf[0x08] << 8 | buf[0x07]) / 1000, 2)
        ups['microUsbVoltage'] = round(float(buf[0x0A] << 8 | buf[0x09]) / 1000, 2)

        return ups

    def __getStatus(self):
        ups = {}

        ups['inaOutputVoltage'] = round(self.inaOutput.voltage(), 2)
        ups['inaOutputCurrent'] = round(self.inaOutput.current() / 1000, 3)
        ups['inaOutputPower'] = round(self.inaOutput.power() / 1000, 3)

        ups['inaBatteryVoltage'] = round(self.inaBattery.voltage(), 2)
        ups['inaBatteryCurrent'] = round(self.inaBattery.current() / 1000, 3)
        ups['inaBatteryPower'] = round(self.inaBattery.power() / 1000, 3)

        # Read all registers
        buf = self.readRegister(0x0, 0xFF)

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

    def setBatteryProtectionVoltage(self, value):
        self.writeRegister(0x11, [ value & 0xFF, (value >> 8) & 0xFF ])
        log.info("Set UPS battery projection voltage to %d", value & 0xFFFF)

    def setSamplePeriod(self, value):
        self.writeRegister(0x15, [ value & 0xFF, (value >> 8) & 0xFF ])
        log.info("Set UPS sample period to %d", value & 0xFFFF)

    def setShutdownCountdown(self, value):
        self.writeRegister(0x18, value)
        log.info("Set UPS shutdown countdown to %d", value)

    def setAutoPowerOn(self, value):
        self.writeRegister(0x19, value)
        log.info("Set UPS auto power on to %d", value)

    def setRestartCountdown(self, value):
        self.writeRegister(0x1A, value)
        log.info("Set UPS restart countdown to %d", value)

    def readRegister(self, register, length=1):
        retryCount = 0
        retryMax = 10
        while (retryCount < retryMax):
            try:
                return self.__readRegister(register, length)
            except Exception as e:
                log.exception("Error read UPS register[%d] length[%d]", register, length)
                retryCount += 1
                if retryCount < retryCount:
                    log.info("Retry read UPS register[%d] length[%d] for %d time...", register, length, retryCount)
                    time.sleep(2)
                else:
                    log.info("Abort read UPS register[%d] length[%d] after %d retries", register, length, retryCount)
                    raise e

    def __readRegister(self, register, length):
        if length == 1:
            return self.bus.read_byte_data(self.config['upsAddress'], register)
        else:
            datas = []
            offset = 0
            while offset < length:
                datas.extend(self.bus.read_i2c_block_data(self.config['upsAddress'], register + offset, min(length - offset, 32)))
                offset += min(length - offset, 32)
            return datas

    def writeRegister(self, register, datas):
        retryCount = 0
        retryMax = 10
        while (retryCount < retryMax):
            try:
                return self.__writeRegister(register, datas)
            except Exception as e:
                log.exception("Error write UPS register[%d] values[%s]", register, _formatList2HexStr(datas))
                retryCount += 1
                if retryCount < retryMax:
                    log.info("Retry write UPS register[%d] values[%s] for %d time...", register, _formatList2HexStr(datas), retryCount)
                    time.sleep(2)
                else:
                    log.info("Abort write UPS register[%d] values[%s] after %d retries", register, _formatList2HexStr(datas), retryCount)
                    raise e

    def __writeRegister(self, register, datas):
        if type(datas) is not list:
            return self.bus.write_byte_data(self.config['upsAddress'], register, datas)
        else:
            offset = 0
            length = len(datas)
            while offset < length:
                self.bus.write_i2c_block_data(self.config['upsAddress'], register + offset, datas[offset : min(length - offset, 32)])
                offset += min(length - offset, 32)



def get(config={}):
    return UpsPlusDevice(config)

class DataOutOfRangeError(Exception):
    pass

def _setDefault(dict, key, value):
    if not dict.get(key):
        dict[key] = value

def _formatList2HexStr(list):
    buf = ""
    for item in list:
        if len(buf):
            buf += " "
        buf += "%02X" % item
    return buf
