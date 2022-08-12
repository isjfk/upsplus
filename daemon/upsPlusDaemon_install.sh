#!/bin/bash
# UPS Plus Daemon installation script

SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE[0]}") && pwd)

# initializing init-functions.
. /lib/lsb/init-functions
sudo raspi-config nonint do_i2c 0

log_action_msg "Install UPS Plus Daemon..."
log_action_msg "More information can be found here:"
log_action_msg "-----------------------------------------------------"
log_action_msg "https://github.com/isjfk/upsplus"
log_action_msg "https://wiki.52pi.com/index.php/UPS_Plus_SKU:_EP-0136"
log_action_msg "-----------------------------------------------------"

# Package check and installation
install_pkgs()
{
	`sudo apt-get -qq update`
	`sudo apt-get -y -qq install sudo git i2c-tools`
}

log_action_msg "Start the software check..."
pkgs=`dpkg -l | awk '{print $2}' | egrep ^git$`
if [[ $pkgs = 'git' ]]; then
	log_success_msg "git has been installed."
else
	log_action_msg "Installing git package..."
	install_pkgs
	if [[ $? -eq 0 ]]; then 
	   log_success_msg "Package installation successfully."
	else
	   log_failure_msg "Package installation is failed,please install git package manually or check the repository"
	fi
fi	

# install pi-ina219 library.
ina_pkg=`pip3 list | grep ina |awk '{print $1}'`
if [[ $ina_pkg = 'pi-ina219' ]]; then
	log_success_msg "pi-ina219 library has been installed"
else
	log_action_msg "Installing pi-ina219 library..."
	pip3 install pi-ina219
	if [[ $? -eq 0 ]]; then
	   log_success_msg "pi-ina219 Installation successful."
	else
	   log_failure_msg "pi-ina219 installation failed!"
	   log_warning_msg "Please install it by manual: pip3 install pi-ina219"
	fi
fi
# install smbus2 library.
log_action_msg "Installing smbus2 library..."
pip3 install smbus2
if [[ $? -eq 0 ]]; then
        log_success_msg "smbus2 Installation successful."
else
    log_failure_msg "smbus2 installation failed!"
    log_warning_msg "Please install it by manual: pip3 install smbus2"
fi

# Create bin folder
log_action_msg "create $HOME/bin directory..."
/bin/mkdir -p $HOME/bin
export PATH=$PATH:$HOME/bin

# Copy daemon script.
cp $SCRIPT_DIR/upsPlusDaemon.py $HOME/bin/

# Add daemon script to crontab 
log_action_msg "Add into general crontab list."

(crontab -l 2>/dev/null; echo "* * * * * /usr/bin/python3 $HOME/bin/upsPlusDaemon.py") | crontab -
sudo systemctl restart cron

if [[ $? -eq 0 ]]; then
	log_action_msg "crontab has been created successful!"
else
	log_failure_msg "Create crontab failed!!"
	log_warning_msg "Please create crontab manually."
	log_action_msg "Usage: crontab -e"
fi 

# Testing and Greetings
if [[ -e $HOME/bin/upsPlusDaemon.py ]]; then 
    python3 $HOME/bin/upsPlusDaemon.py 
    if [[ $? -eq 0 ]]; then
        log_success_msg "UPS Plus Daemon Installation is Complete!"
        log_action_msg "-----------------More Information--------------------"
        log_action_msg "https://github.com/isjfk/upsplus"
        log_action_msg "https://wiki.52pi.com/index.php/UPS_Plus_SKU:_EP-0136"
        log_action_msg "-----------------------------------------------------"
    else
        log_failure_msg "!!!UPS Plus Daemon Installation is Incomplete!!!"
        log_action_msg "-----------------More Information--------------------"
        log_action_msg "https://github.com/isjfk/upsplus"
        log_action_msg "https://wiki.52pi.com/index.php/UPS_Plus_SKU:_EP-0136"
        log_action_msg "-----------------------------------------------------"
    fi 
fi 
