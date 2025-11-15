#!/usr/bin/env python3
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, Gio, GLib
import subprocess
import threading
import os
import configparser
import json
import sys

# Önce yerel dizini kontrol et, sonra sistem dizinini
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(SCRIPT_DIR, "language")
SYSTEM_LANG_DIR = "/usr/share/fscheck/language"
SETTINGS_FILE = os.path.expanduser("~/.fscheck_settings.json")
LANGUAGES = {
    "turkish": "Türkçe",
    "english": "English"
}

def get_logo_path():
    # Önce yerel dizini kontrol et
    local_path = os.path.join(SCRIPT_DIR, "icons", "FSCheck.png")
    if os.path.exists(local_path):
        return local_path
    return "/usr/share/fscheck/icons/FSCheck.png"

def get_icon_path(icon_name):
    # Önce yerel dizini kontrol et
    local_path = os.path.join(SCRIPT_DIR, "icons", icon_name)
    if os.path.exists(local_path):
        return local_path
    return f"/usr/share/fscheck/icons/{icon_name}"

def load_translations(lang_code):
    translations = {}
    
    # Önce yerel dizini kontrol et
    lang_file = os.path.join(LANG_DIR, f"{lang_code}.ini")
    if not os.path.exists(lang_file):
        # Yerel dizinde yoksa sistem dizinini kontrol et
        lang_file = os.path.join(SYSTEM_LANG_DIR, f"{lang_code}.ini")
    
    config = configparser.ConfigParser()
    config.optionxform = str  # Anahtarların büyük/küçük harf durumunu korur
    
    if os.path.exists(lang_file):
        try:
            config.read(lang_file, encoding="utf-8")
            if "strings" in config:
                translations = dict(config["strings"])
                pass  # Başarıyla yüklendi
            else:
                pass  # 'strings' bölümü bulunamadı
        except Exception as e:
            pass  # Okuma hatası
    else:
        pass  # Dosya bulunamadı
    
    return translations

# Root kontrolünü kaldır, sadece gerektiğinde pkexec kullanır işini kolaylaştırır

class ExtFSCheckTool(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="org.shampuan.ExtFSCheckTool")
        self.window = None
        self.disk_combo = None
        self.examine_btn = None
        self.repair_btn = None
        self.status_label = None
        self.disks = []
        self.translations = {}
        self.lang_code = self.get_saved_language()
        self.set_language(self.lang_code)
        self.refresh_timer = None
        self.logo_click_count = 0
        self.easter_egg_shown = False
        self.btrfs_available = self.check_btrfs_tools()

    def get_saved_language(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
                    lang = settings.get('language')
                    if lang in LANGUAGES:
                        return lang
        except:
            pass
        return "english"

    def save_language(self, lang_code):
        try:
            settings = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    settings = json.load(f)
            settings['language'] = lang_code
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f)
        except:
            pass

    def set_language(self, lang_code):
        self.lang_code = lang_code
        self.translations = load_translations(lang_code)
        self.save_language(lang_code)

    def t(self, key):
        return self.translations.get(key, key)
    
    def check_btrfs_tools(self):
        """BTRFS araçlarının kurulu olup olmadığını kontrol et"""
        try:
            subprocess.run(["btrfs", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def center_window(self, window):
        """Pencereyi ekranın ortasına yerleştir"""
        display = Gdk.Display.get_default()
        if display:
            monitor = display.get_monitors().get_item(0)
            if monitor:
                geometry = monitor.get_geometry()
                window_width, window_height = window.get_default_size()
                x = (geometry.width - window_width) // 2
                y = (geometry.height - window_height) // 2

    def do_activate(self):
        if not self.window:
            self.window = Gtk.ApplicationWindow(application=self)
            self.window.set_title(self.t("FS Check GUI"))
            self.window.set_default_size(500, 600)
            self.window.set_resizable(False)
            
            # Pencereyi ekranın ortasında başlat - GTK4 için CSS kullan
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b"""
                window {
                    margin: auto;
                }
                .equal-button {
                    min-width: 110px;
                    min-height: 36px;
                }
                .equal-button:hover {
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }
            """)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            
            # Uygulama ikonunu ayarla
            logo_path = get_logo_path()
            if os.path.exists(logo_path):
                try:
                    # GTK4 için ikon ayarlama
                    self.set_icon_name("FSCheck")
                    # Pencere ikonu ayarlama
                    icon_texture = Gdk.Texture.new_from_filename(logo_path)
                    self.window.set_icon_name("FSCheck")
                except Exception as e:
                    pass  # İkon yüklenemezse sessizce devam et

            # Üst menü ve ikonlar
            header = Gtk.HeaderBar()
            header.set_title_widget(Gtk.Label(label=self.t("FS Check GUI")))

            # Dil seçimi butonu (🌐)
            lang_btn = Gtk.Button(label="🌐")
            lang_btn.connect("clicked", self.on_language_clicked)
            header.pack_start(lang_btn)

            # Hakkında ikonu ve tıklama ile açılan dialog
            about_btn = Gtk.Button(label="ℹ️")
            about_btn.connect("clicked", self.show_about_dialog)
            header.pack_start(about_btn)
            self.window.set_titlebar(header)

            # Ana kutu
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
            self.window.set_child(vbox)

            # Program logosu başlık ile combobox arasında (Easter egg için tıklanabilir) logoya 5 kez tıkla gör :-)
            logo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            logo_box.set_halign(Gtk.Align.CENTER)
            
            # Logo butonunu tıklanabilir yap
            self.logo_btn = Gtk.Button()
            self.logo_btn.set_has_frame(False)  # Çerçevesiz buton
            logo = Gtk.Image.new_from_file(get_logo_path())
            logo.set_pixel_size(96)
            self.logo_btn.set_child(logo)
            self.logo_btn.connect("clicked", self.on_logo_clicked)
            
            logo_box.append(self.logo_btn)
            vbox.append(logo_box)

            # Disk seçim ve ikon (combobox boydan boya) otomatik liste yenileme
            disk_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            disk_label = Gtk.Label(label=self.t("Device") + ":")
            disk_label.set_halign(Gtk.Align.END)
            disk_row.append(disk_label)
            self.disk_combo = Gtk.ComboBoxText()
            self.disk_combo.set_hexpand(True)
            self.disk_combo.set_size_request(-1, -1)
            disk_row.append(self.disk_combo)
            disk_row.set_halign(Gtk.Align.FILL)
            vbox.append(disk_row)

            # İncele ve Onar butonları sağda
            button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            button_box.set_halign(Gtk.Align.END)
            self.examine_btn = Gtk.Button()
            self.examine_btn.set_child(self._icon_with_label(get_icon_path("examine.png"), self.t("Examine")))
            self.examine_btn.connect("clicked", self.on_examine_clicked)
            self.examine_btn.add_css_class("equal-button")
            self.repair_btn = Gtk.Button()
            self.repair_btn.set_child(self._icon_with_label(get_icon_path("repair.png"), self.t("Repair")))
            self.repair_btn.connect("clicked", self.on_repair_clicked)
            self.repair_btn.add_css_class("equal-button")
            button_box.append(self.examine_btn)
            button_box.append(self.repair_btn)
            vbox.append(button_box)

            # İşlem durumu (kaydırılabilir metin alanı)
            status_label = Gtk.Label(label=self.t("Operation status") + ":")
            status_label.set_halign(Gtk.Align.START)
            vbox.append(status_label)
            
            # ScrolledWindow ile otomatik kaydırma çubukları
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_hexpand(True)
            scrolled.set_vexpand(True)
            scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            
            # TextView kullan (Label yerine)
            self.status_view = Gtk.TextView()
            self.status_view.set_editable(False)
            self.status_view.set_monospace(True)
            self.status_view.set_wrap_mode(Gtk.WrapMode.WORD)
            
            # Siyah arka plan, beyaz yazı
            self.status_buffer = self.status_view.get_buffer()
            self.status_buffer.set_text(self.t("You can select a disk and start the process."))
            
            scrolled.set_child(self.status_view)
            vbox.append(scrolled)

            # BTRFS araçları kontrolü
            if not self.btrfs_available:
                self.show_btrfs_warning()
            
            # Diskleri yükle
            self.load_disks()
            
            # Otomatik yenileme timer'ı başlat
            self.start_auto_refresh()

        self.window.present()

    def on_language_clicked(self, btn):
        # Dil seçimi için popover menü
        self.lang_popover = Gtk.Popover.new()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        for code, name in LANGUAGES.items():
            lang_btn = Gtk.Button(label=name)
            lang_btn.connect("clicked", self.on_language_selected, code)
            box.append(lang_btn)
        self.lang_popover.set_child(box)
        self.lang_popover.set_parent(btn)
        self.lang_popover.popup()

    def on_language_selected(self, btn, lang_code):
        self.lang_popover.popdown()
        self.set_language(lang_code)
        self.retranslate_ui()

    def retranslate_ui(self):
        # Timer'ı durdur
        if self.refresh_timer:
            GLib.source_remove(self.refresh_timer)
        # Pencereyi yeniden oluştur
        self.window.destroy()
        self.window = None
        self.do_activate()

    def _make_menu_button(self, label):
        btn = Gtk.MenuButton()
        btn.set_child(Gtk.Label(label=label))
        return btn

    def _icon_with_label(self, icon_path, text):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        img = Gtk.Image.new_from_file(icon_path)
        box.append(img)
        box.append(Gtk.Label(label=text))
        return box

    def load_disks(self):
        # Sistemdeki ext2/3/4 ve BTRFS disk bölümlerini bul
        self.disks = []
        self.disk_combo.remove_all()
        try:
            # Sistemde bağlı olan aygıtları bul (örn. kök disk)
            system_devices = set()
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        dev, mnt, fstype = parts[0], parts[1], parts[2]
                        if dev.startswith("/dev/") and mnt == "/":
                            system_devices.add(dev)

            # lsblk ile tüm ext2/3/4 ve BTRFS partisyonları bul
            result = subprocess.run(
                ["lsblk", "-P", "-o", "NAME,TYPE,FSTYPE,MOUNTPOINT,SIZE,LABEL"],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                props = {}
                for item in line.strip().split():
                    if "=" not in item:
                        continue
                    try:
                        key, val = item.split("=", 1)
                        props[key] = val.strip('"')
                    except ValueError:
                        continue
                
                # Desteklenen dosya sistemleri: ext2/3/4 ve BTRFS
                if (
                    props.get("TYPE") in ["part", "disk"]
                    and props.get("FSTYPE") in ["ext2", "ext3", "ext4", "btrfs"]
                    and not props.get("NAME", "").startswith("loop")
                    and props.get("SIZE", "0B") != "0B"
                ):
                    devpath = "/dev/" + props["NAME"]
                    fs_type = props.get("FSTYPE", "ext4")
                    is_system = devpath in system_devices or props.get("MOUNTPOINT") == "/"
                    self.disks.append((devpath, fs_type, is_system))

            if not self.disks:
                self.disk_combo.append_text(self.t("No external disk found"))
                self.disk_combo.set_active(0)
                self.examine_btn.set_sensitive(False)
                self.repair_btn.set_sensitive(False)
            else:
                # Disk bilgilerini göster
                result2 = subprocess.run(
                    ["lsblk", "-P", "-o", "NAME,TYPE,FSTYPE,SIZE,LABEL"],
                    capture_output=True, text=True
                )
                disk_info = {}
                for line in result2.stdout.splitlines():
                    if not line.strip():
                        continue
                    props = {}
                    for item in line.strip().split():
                        if "=" not in item:
                            continue
                        try:
                            key, val = item.split("=", 1)
                            props[key] = val.strip('"')
                        except ValueError:
                            continue
                    if props.get("NAME"):
                        devpath = "/dev/" + props["NAME"]
                        for disk_path, disk_fstype, is_system in self.disks:
                            if disk_path == devpath:
                                size = props.get("SIZE", "")
                                fstype = props.get("FSTYPE", disk_fstype)
                                label = props.get("LABEL", "")
                                system_tag = " [SYSTEM]" if is_system else ""
                                if label:
                                    disk_info[devpath] = f"{label} - {devpath} ({fstype}, {size}){system_tag}"
                                else:
                                    disk_info[devpath] = f"{devpath} ({fstype}, {size}){system_tag}"
                                break
                
                for disk_path, disk_fstype, is_system in self.disks:
                    display_name = disk_info.get(disk_path, f"{disk_path} ({disk_fstype})")
                    self.disk_combo.append_text(display_name)
                self.disk_combo.set_active(0)
                self.examine_btn.set_sensitive(True)
                self.repair_btn.set_sensitive(True)
        except Exception as e:
            self.disk_combo.append_text(self.t("Could not read disks"))
            self.disk_combo.set_active(0)
            self.examine_btn.set_sensitive(False)
            self.repair_btn.set_sensitive(False)
            self.update_status_text(f'{self.t("Error")}: {e}')

    def get_selected_disk(self):
        idx = self.disk_combo.get_active()
        if idx < 0 or idx >= len(self.disks):
            return None, None, False
        return self.disks[idx]

    def on_examine_clicked(self, btn):
        disk_info = self.get_selected_disk()
        if not disk_info[0]:
            self.update_status_text(self.t("Please select a disk."))
            return
        disk_path, fs_type, is_system = disk_info
        self.run_fsck(disk_path, fs_type, is_system, check_only=True)

    def on_repair_clicked(self, btn):
        disk_info = self.get_selected_disk()
        if not disk_info[0]:
            self.update_status_text(self.t("Please select a disk."))
            return
        disk_path, fs_type, is_system = disk_info
        if is_system:
            self.show_system_repair_dialog(disk_path, fs_type)
        else:
            self.run_fsck(disk_path, fs_type, is_system, check_only=False)

    def show_system_repair_dialog(self, disk_path, fs_type):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE
        )
        
        if self.lang_code == "turkish":
            dialog.set_markup(
                f'<span size="large" weight="bold">⚠️ Sistem Diski Onarımı</span>\n\n'
                f'Seçilen disk ({disk_path}) sistem diskidir.\n'
                f'Güvenlik nedeniyle onarım yeniden başlatmada yapılacaktır.\n\n'
                f'<b>Sistem yeniden başlatılsın mı?</b>'
            )
        else:
            dialog.set_markup(
                f'<span size="large" weight="bold">⚠️ System Disk Repair</span>\n\n'
                f'Selected disk ({disk_path}) is a system disk.\n'
                f'For safety, repair will be performed on reboot.\n\n'
                f'<b>Restart system now?</b>'
            )
        
        dialog.add_button(self.t("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(self.t("Apply"), Gtk.ResponseType.OK)
        
        dialog.connect("response", self.on_system_repair_response, disk_path, fs_type)
        dialog.present()
    
    def on_system_repair_response(self, dialog, response, disk_path, fs_type):
        dialog.destroy()
        if response == Gtk.ResponseType.OK:
            self.schedule_boot_fsck(disk_path, fs_type)
    
    def schedule_boot_fsck(self, disk_path, fs_type):
        try:
            if fs_type == "btrfs":
                self.update_status_text(self.t("BTRFS system disk repair on boot is not supported yet."))
                return
            
            subprocess.run(["pkexec", "touch", "/forcefsck"], check=True)
            
            self.update_status_text(
                f'{self.t("Boot fsck scheduled for")} {disk_path}\n'
                f'{self.t("System will restart now.")}')
            
            GLib.timeout_add_seconds(3, self.restart_system)
            
        except subprocess.CalledProcessError as e:
            self.update_status_text(f'{self.t("Error scheduling boot fsck")}: {e}')
    
    def restart_system(self):
        try:
            subprocess.run(["pkexec", "systemctl", "reboot"])
        except:
            try:
                subprocess.run(["pkexec", "reboot"])
            except:
                self.update_status_text(self.t("Could not restart system. Please restart manually."))
        return False

    def run_fsck(self, disk, fs_type, is_system, check_only=True):
        self.examine_btn.set_sensitive(False)
        
        if is_system and not check_only:
            self.update_status_text(self.t("System disk repair requires reboot. Use repair dialog."))
            self.examine_btn.set_sensitive(True)
            return
            
        if fs_type == "btrfs":
            if not self.btrfs_available:
                self.update_status_text(self.t("BTRFS tools not available. Please install btrfs-progs package."))
                self.examine_btn.set_sensitive(True)
                return
            if check_only:
                # BTRFS için sadece kontrol
                cmd = ["pkexec", "btrfs", "check", "--readonly", disk]
            else:
                # BTRFS onarım için önce diski bağlantısını kes, sonra onar, tekrar bağla
                self.repair_mounted_btrfs_disk(disk)
                return
        else:
            # ext2/3/4 için e2fsck kullan
            if check_only:
                # Sadece okuma için -n kullan (bağlı dosya sistemlerinde çalışır)
                cmd = ["pkexec", "/sbin/e2fsck", "-n", disk]
            else:
                # Onarım için önce diski bağlantısını kes, sonra onar, tekrar bağla
                self.repair_mounted_disk(disk)
                return
        
        action_text = self.t("examine started") if check_only else self.t("repair started")
        self.update_status_text(f'{disk} {action_text}...\n{self.t("Please wait.")}')
        
        def worker():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                output_lines = []
                for line in iter(proc.stdout.readline, ''):
                    output_lines.append(line.rstrip())
                    current_output = "\n".join(output_lines[-20:])  # Son 20 satırı göster
                    GLib.idle_add(self.update_status_text, current_output)
                
                proc.wait()
                
                if proc.returncode == 0:
                    final_msg = self.t("Operation completed successfully.")
                else:
                    final_msg = f"{self.t('Operation completed with exit code')}: {proc.returncode}"
                
                final_output = "\n".join(output_lines) + "\n\n" + final_msg
                GLib.idle_add(self.update_status_text, final_output)
                
            except Exception as e:
                GLib.idle_add(self.update_status_text, f'{self.t("Error")}: {e}')
            finally:
                GLib.idle_add(self.examine_btn.set_sensitive, True)
        
        threading.Thread(target=worker, daemon=True).start()

    def start_auto_refresh(self):
        # Her 3 saniyede bir disk listesini kontrol et
        self.refresh_timer = GLib.timeout_add_seconds(3, self.auto_refresh_disks)

    def auto_refresh_disks(self):
        # Mevcut disk listesini kaydet
        old_disks = self.disks.copy()
        
        # Yeni disk listesini al
        self.load_disks()
        
        # Eğer disk listesi değiştiyse kullanıcıya bildir
        if old_disks != self.disks:
            if len(self.disks) > len(old_disks):
                self.update_status_text(self.t("New disk detected. List updated."))
            elif len(self.disks) < len(old_disks):
                self.update_status_text(self.t("Disk removed. List updated."))
        
        return True  # Timer'ı devam ettir

    def on_logo_clicked(self, btn):
        """Easter egg: Atatürk sözü göster"""
        self.logo_click_count += 1
        
        if self.logo_click_count >= 5 and not self.easter_egg_shown:
            self.easter_egg_shown = True
            self.show_easter_egg()
            
    def show_easter_egg(self):
        """Atatürk'ten ilham verici söz göster"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK
        )
        
        if self.lang_code == "turkish":
            dialog.set_markup(
                '<span size="large" weight="bold">🇹🇷 Mustafa Kemal ATATÜRK</span>\n\n'
                '<i>"Hayatta en hakîkî mürşit ilimdir, fendir."</i>\n\n'
                '<small>Bu program TÜRK bilimi ve teknolojisinin bir ürünüdür.</small>'
            )
        else:
            dialog.set_markup(
                '<span size="large" weight="bold">🇹🇷 Mustafa Kemal ATATÜRK</span>\n\n'
                '<i>"The truest guide in life is science and knowledge."</i>\n\n'
                '<small>This program is a product of TURK science and technology.</small>'
            )
        
        dialog.present()
        dialog.connect("response", self.on_easter_egg_closed)
    
    def on_easter_egg_closed(self, dialog, response):
        """Easter egg dialogu kapatıldığında sayacı sıfırla"""
        dialog.destroy()
        self.logo_click_count = 0
        self.easter_egg_shown = False
    
    def show_btrfs_warning(self):
        """BTRFS araçları kurulu değilse uyarı göster"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK
        )
        
        if self.lang_code == "turkish":
            dialog.set_markup(
                '<span size="large" weight="bold">⚠️ BTRFS Araçları Bulunamadı</span>\n\n'
                'BTRFS disklerini tarayabilmek için btrfs-progs paketinin kurulu olması gerekir.\n\n'
                '<b>Kurulum için:</b>\n'
                '• Ubuntu/Debian: <tt>sudo apt install btrfs-progs</tt>\n'
                '• Fedora: <tt>sudo dnf install btrfs-progs</tt>\n'
                '• Arch: <tt>sudo pacman -S btrfs-progs</tt>'
            )
        else:
            dialog.set_markup(
                '<span size="large" weight="bold">⚠️ BTRFS Tools Not Found</span>\n\n'
                'To scan BTRFS disks, btrfs-progs package must be installed.\n\n'
                '<b>Installation:</b>\n'
                '• Ubuntu/Debian: <tt>sudo apt install btrfs-progs</tt>\n'
                '• Fedora: <tt>sudo dnf install btrfs-progs</tt>\n'
                '• Arch: <tt>sudo pacman -S btrfs-progs</tt>'
            )
        
        dialog.present()
        dialog.connect("response", lambda d, r: d.destroy())

    def repair_mounted_disk(self, disk):
        def worker():
            try:
                # Tek pkexec çağrısıyla tüm işlemleri yap
                GLib.idle_add(self.update_status_text, f'{disk} {self.t("repair started")}...')
                
                # Bash script ile tüm işlemleri tek seferde yap
                script = f"""
                # Disk bağlı mı kontrol et
                if mount | grep -q "{disk}"; then
                    echo "Unmounting {disk}..."
                    umount "{disk}" || exit 1
                    REMOUNT=1
                else
                    echo "Disk not mounted, proceeding..."
                    REMOUNT=0
                fi
                
                # Onarım yap
                echo "Starting repair..."
                /sbin/e2fsck -f -y "{disk}"
                REPAIR_EXIT=$?
                
                # Eğer başlangıçta bağlıysa tekrar bağla
                if [ "$REMOUNT" = "1" ]; then
                    echo "Remounting {disk}..."
                    mount "{disk}"
                fi
                
                exit $REPAIR_EXIT
                """
                
                repair_proc = subprocess.Popen(
                    ["pkexec", "bash", "-c", script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                output_lines = []
                for line in iter(repair_proc.stdout.readline, ''):
                    output_lines.append(line.rstrip())
                    current_output = "\n".join(output_lines[-15:])
                    GLib.idle_add(self.update_status_text, current_output)
                
                repair_proc.wait()
                
                # Sonuç mesajı
                if repair_proc.returncode == 0:
                    final_msg = self.t("Repair completed successfully.")
                else:
                    final_msg = f"{self.t('Repair completed with exit code')}: {repair_proc.returncode}"
                
                final_output = "\n".join(output_lines) + "\n\n" + final_msg
                GLib.idle_add(self.update_status_text, final_output)
                
            except Exception as e:
                GLib.idle_add(self.update_status_text, f'{self.t("Error")}: {e}')
            finally:
                GLib.idle_add(self.examine_btn.set_sensitive, True)
        
        threading.Thread(target=worker, daemon=True).start()

    def repair_mounted_btrfs_disk(self, disk):
        def worker():
            try:
                GLib.idle_add(self.update_status_text, f'{disk} BTRFS {self.t("repair started")}...')
                
                # BTRFS onarım script'i
                script = f"""
                # Disk bağlı mı kontrol et
                if mount | grep -q "{disk}"; then
                    echo "Unmounting {disk}..."
                    umount "{disk}" || exit 1
                    REMOUNT=1
                else
                    echo "Disk not mounted, proceeding..."
                    REMOUNT=0
                fi
                
                # BTRFS onarım yap
                echo "Starting BTRFS repair..."
                btrfs check --repair "{disk}"
                REPAIR_EXIT=$?
                
                # Eğer başlangıçta bağlıysa tekrar bağla
                if [ "$REMOUNT" = "1" ]; then
                    echo "Remounting {disk}..."
                    mount "{disk}"
                fi
                
                exit $REPAIR_EXIT
                """
                
                repair_proc = subprocess.Popen(
                    ["pkexec", "bash", "-c", script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                
                output_lines = []
                for line in iter(repair_proc.stdout.readline, ''):
                    output_lines.append(line.rstrip())
                    current_output = "\n".join(output_lines[-15:])
                    GLib.idle_add(self.update_status_text, current_output)
                
                repair_proc.wait()
                
                # Sonuç mesajı
                if repair_proc.returncode == 0:
                    final_msg = self.t("BTRFS repair completed successfully.")
                else:
                    final_msg = f"{self.t('BTRFS repair completed with exit code')}: {repair_proc.returncode}"
                
                final_output = "\n".join(output_lines) + "\n\n" + final_msg
                GLib.idle_add(self.update_status_text, final_output)
                
            except Exception as e:
                GLib.idle_add(self.update_status_text, f'{self.t("Error")}: {e}')
            finally:
                GLib.idle_add(self.examine_btn.set_sensitive, True)
        
        threading.Thread(target=worker, daemon=True).start()

    def update_status_text(self, text):
        self.status_buffer.set_text(text)
        # Otomatik olarak en alta kaydır
        mark = self.status_buffer.get_insert()
        self.status_view.scroll_mark_onscreen(mark)

    def show_about_dialog(self, button):
        about = Gtk.AboutDialog()
        about.set_transient_for(self.window)
        about.set_modal(True)
        about.set_program_name(self.t("ExtFS Check Tool"))
        about.set_version("1.0.0")
        about.set_comments(self.t("Ext format disks check and repair tool.") + "\n\n" + self.t("Design: A.Serhat KILIÇOĞLU (shampuan)\nCode: Fatih Önder (CekToR)"))
        about.set_website("https://github.com/shampuan")
        about.set_authors([self.t("A.Serhat KILIÇOĞLU\nFatih ÖNDER")])
        about.set_license_type(Gtk.License.GPL_3_0)
        about.set_copyright(self.t("GPL/GNU Copyright © 2025 A.Serhat KILIÇOĞLU"))
        about.set_logo(Gtk.Image.new_from_file(get_logo_path()).get_paintable())
        about.present()

if __name__ == "__main__":
    app = ExtFSCheckTool()
    app.run()
