#!/bin/bash
# FSCheck Boot Service Installer

echo "Installing FSCheck boot repair service..."

# Betik dosyasını kopyala ve çalıştırılabilir yap
sudo cp fscheck-boot.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/fscheck-boot.sh

# Systemd servis dosyasını kopyala
sudo cp fscheck-boot.service /etc/systemd/system/

# Systemd'yi yeniden yükle ve servisi etkinleştir
sudo systemctl daemon-reload
sudo systemctl enable fscheck-boot.service

echo "FSCheck boot repair service installed and enabled successfully."
echo "The service will run on boot if /forcefsck file exists."