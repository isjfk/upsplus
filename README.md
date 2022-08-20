# UPS Plus Daemon
Customized daemon script for UPS Plus from GeeekPi.

## Features
* Shutdown on power failure
  * Shutdown OS after x minutes
  * Shutdown OS on low battery voltage
  * Power off UPS after shutdown OS
* Auto start on power resume
* UPS full status log
  * Log file is rolling on day basis
  * Old log files exceed upper limit are deleted
* Data check & retry on read/write UPS status register

## Prerequisite
The script should be work on Raspbian 32bit & 64bit. I test it only on OctoPi which is based on Raspbian 32bit.

Before installtion, be sure you have following packages installed:
* Git

Install these packages by (if you don't have them installed):
```bash
apt install git
```

## Installtion
The UPS Plus daemon script can be installed by:
```bash
cd ~
git clone https://github.com/isjfk/upsplus.git
cd ~/upsplus/daemon
bash install_upsplus.sh
```
* The daemon script will be copied into: /usr/local/lib/upsplus
* The systemd script will be copied into: /etc/systemd/system/upsplus.service
* Log will be saved into: /var/log/upsplus.log


## Configuration
Change configuration by edit the configuration file:
```bash
vim /etc/upsplus.conf
```

## Uninstall
To uninstall the daemon as well as all related files
```bash
cd ~/upsplus/daemon
bash uninstall_upsplus.sh
```

## About UPS Plus
![UPS Plus](./docs/res/UPS_V2_1.jpg) ![UPS Plus](./docs/res/UPS_V2_2.jpg) ![UPS Plus](./docs/res/UPS_V2_3.jpg)
