#!/bin/bash
# FSCheck Boot Repair Script
# Bu betik sistem başlangıcında kök dosya sistemini onarır

LOGFILE="/var/log/fscheck-boot.log"
FLAGFILE="/forcefsck"

# Log fonksiyonu
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
}

# Eğer /forcefsck dosyası varsa fsck çalıştır
if [ -f "$FLAGFILE" ]; then
    log_message "FSCheck boot repair started"
    
    # Kök dosya sistemini salt okunur olarak yeniden mount et
    mount -o remount,ro /
    
    # fsck çalıştır
    log_message "Running fsck -f -y on root filesystem"
    /sbin/fsck -f -y / >> "$LOGFILE" 2>&1
    FSCK_EXIT=$?
    
    # Sonucu logla
    if [ $FSCK_EXIT -eq 0 ]; then
        log_message "fsck completed successfully"
    else
        log_message "fsck completed with exit code: $FSCK_EXIT"
    fi
    
    # Kök dosya sistemini okuma-yazma olarak yeniden mount et
    mount -o remount,rw /
    
    # Flag dosyasını sil
    rm -f "$FLAGFILE"
    log_message "FSCheck boot repair finished, flag file removed"
fi