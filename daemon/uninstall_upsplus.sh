#!/bin/bash
# UPS Plus Daemon uninstallation script

SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE[0]}") && pwd)

BIN_DIR="/usr/local/lib/upsplus"
SRV_DIR="/etc/systemd/system/"
CONF_DIR="/etc"

echo "Uninstall daemon for Geeek Pi UPS Plus start..."

echo
echo "Stop systemd service..."
sudo systemctl stop upsplus

# Remove script directory
echo "Remove $BIN_DIR directory..."
sudo rm -rf $BIN_DIR

# Remove conf file
echo "Remove conf file $CONF_DIR/upsplus.conf ..."
sudo rm $CONF_DIR/upsplus.conf

# Remove service from systemd
echo "Remove systemd service $SRV_DIR/upsplus.service ..."
sudo rm $SRV_DIR/upsplus.service
sudo systemctl daemon-reload

# Remove log file
echo "Remove log file /var/log/upsplus.log* ..."
sudo rm /var/log/upsplus.log*

echo
echo "Uninstall daemon for Geeek Pi UPS Plus finished"

echo ""
echo "-----------------More Information--------------------"
echo "https://github.com/isjfk/upsplus"
echo "https://wiki.52pi.com/index.php/UPS_Plus_SKU:_EP-0136"
echo "https://github.com/geeekpi/upsplus.git"
echo "-----------------------------------------------------"
