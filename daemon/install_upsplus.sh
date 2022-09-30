#!/bin/bash
# UPS Plus Daemon installation script

SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE[0]}") && pwd)

BIN_DIR="/usr/local/lib/upsplus"
SRV_DIR="/etc/systemd/system/"
CONF_DIR="/etc"

echo "Install daemon for Geeek Pi UPS Plus start..."

echo
echo "Enable i2c device..."
sudo raspi-config nonint do_i2c 0

# Install apt packages
echo
echo "Check & install apt packages..."

apt_package_check() {
    local pkg=$1
    local pkg_installed=`dpkg -l | awk '{print $2}' | grep ^$pkg$`
    if [[ "$pkg_installed" = "$pkg" ]]; then
        echo "Package $pkg has been installed"
    else
        echo "Package $pkg will be installed..."
        apt_pkgs+="$pkg"
    fi
}

apt_package_install() {
    apt_pkgs=$(echo "$apt_pkgs" | xargs)
    if [[ ! -z "$apt_pkgs" ]]; then
        echo "# sudo apt-get -qq update"
        sudo apt-get -qq update
        echo "# sudo apt-get -y -qq install $apt_pkgs"
        sudo apt-get -y -qq install $apt_pkgs
        if [[ $? -eq 0 ]]; then 
            echo "Package installtion succeed: $apt_pkgs"
        else
            echo "[ERROR] Package installtion failed: $apt_pkgs"
            echo "Please install the packages manually, then try again!"
            exit 1
        fi
    fi
}

apt_package_check python3
apt_package_check i2c-tools
apt_package_install

# Install python pip libraries
echo
echo "Check & install python pip libraries..."

pip_library_check() {
    local lib=$1
    local lib_installed=`sudo pip3 list | awk '{print $1}' | grep ^$lib$`
    if [[ "$lib_installed" = "$lib" ]]; then
        echo "Library $lib has been installed"
    else
        echo "Library $lib will be installed..."
        pip_libs+="$lib"
    fi
}

pip_library_install() {
    pip_libs=$(echo "$pip_libs" | xargs)
    if [[ ! -z "$pip_libs" ]]; then
        echo "# sudo pip3 install $pip_libs"
        sudo pip3 install $pip_libs
        if [[ $? -eq 0 ]]; then 
            echo "Library installtion succeed: $pip_libs"
        else
            echo "[ERROR] Library installtion failed: $pip_libs"
            echo "Please install the libraries manually, then try again!"
            exit 1
        fi
    fi
}

pip_library_check pi-ina219
pip_library_check smbus2
pip_library_install

echo

# Create script directory
echo "Create $BIN_DIR directory..."
sudo mkdir -p $BIN_DIR

# Copy script
echo "Copy daemon scripts into $BIN_DIR directory..."
sudo cp $SCRIPT_DIR/UpsPlusDevice.py $BIN_DIR
sudo cp $SCRIPT_DIR/UpsPlusDaemon.py $BIN_DIR
sudo chmod +x $BIN_DIR/*.py

# Copy conf file
echo "Copy conf file into $CONF_DIR/upsplus.conf ..."
sudo cp $SCRIPT_DIR/upsplus.conf $CONF_DIR

# Add service to systemd
echo "Add systemd service into $SRV_DIR/upsplus.service ..."
sudo cp $SCRIPT_DIR/upsplus.service $SRV_DIR
sudo systemctl daemon-reload
sudo systemctl restart upsplus
sudo systemctl enable upsplus

echo

# Check systemd service status
status=`sudo systemctl is-active upsplus`
if [[ "$status" = "active" ]]; then
    echo "Install daemon for Geeek Pi UPS Plus succeed"
    echo "To check daemon service logs: journalctl -n 100 -f -u upsplus"
    echo "                          or: tail -n 100 -f /var/log/upsplus.log"
else
    echo "[ERROR] Install daemon for Geeek Pi UPS Plus failed!"
fi

echo ""
echo "-----------------More Information--------------------"
echo "https://github.com/isjfk/upsplus"
echo "https://wiki.52pi.com/index.php/UPS_Plus_SKU:_EP-0136"
echo "https://github.com/geeekpi/upsplus.git"
echo "-----------------------------------------------------"
