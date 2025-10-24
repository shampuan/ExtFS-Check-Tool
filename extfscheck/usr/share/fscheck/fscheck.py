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

LANG_DIR = "/usr/share/fscheck/language"
SETTINGS_FILE = os.path.expanduser("~/.fscheck_settings.json")
LANGUAGES = {
    "turkish": "Türkçe",
    "english": "English"
}

def get_logo_path():
    return "/usr/share/fscheck/icons/FSCheck.png"

def get_icon_path(icon_name):
    return f"/usr/share/fscheck/icons/{icon_name}"

def load_translations(lang_code):
    translations = {}
    lang_file = os.path.join(LANG_DIR, f"{lang_code}.ini")
    config = configparser.ConfigParser()
    config.optionxform = str  # Anahtarların saklama kutusudur bu bea
    if os.path.exists(lang_file):
        config.read(lang_file, encoding="utf-8")
        if "strings" in config:
            translations = dict(config["strings"])
    return translations

# Root kontrolünü kaldır, sadece gerektiğinde pkexec kullanır işini kolaylaştırcak

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

            # Program logosu başlık ile spinbox arasında (Easter egg için tıklanabilir) analogoya 5 kez tıkla gör :-)
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

            # Muayene ve Onar butonları sağda
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

            # Uyarı
            warning = Gtk.Label(
                label="⚠️ " + self.t("Be careful before you start. Irreversible results may occur for your disk."),
                wrap=True
            )
            warning.set_margin_top(8)
            warning.set_margin_bottom(0)
            warning.set_css_classes(["warning"])
            vbox.append(warning)

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
        # Sistemdeki ext4 disk bölümlerini bul
        self.disks = []
        self.disk_combo.remove_all()
        try:
            # Sistemde bağlı olan ext4 aygıtlarını bul (örn. kök disk)
            system_devices = set()
            with open("/proc/mounts") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 3:
                        dev, mnt, fstype = parts[0], parts[1], parts[2]
                        if dev.startswith("/dev/") and mnt == "/":
                            system_devices.add(dev)

            # lsblk ile tüm ext4 partisyonları bul
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
                
                # Daha geniş kriter: part veya disk tipinde, ext2/3/4 dosya sistemli
                if (
                    props.get("TYPE") in ["part", "disk"]
                    and props.get("FSTYPE") in ["ext2", "ext3", "ext4"]
                    and not props.get("NAME", "").startswith("loop")
                    and props.get("SIZE", "0B") != "0B"
                ):
                    devpath = "/dev/" + props["NAME"]
                    # Sadece kök dosya sistemini hariç tut
                    if devpath not in system_devices and props.get("MOUNTPOINT") != "/":
                        size_info = props.get("SIZE", "")
                        fs_type = props.get("FSTYPE", "ext4")
                        display_name = f"{devpath} ({fs_type}, {size_info})"
                        self.disks.append(devpath)

            if not self.disks:
                self.disk_combo.append_text(self.t("No external ext4 disk found"))
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
                        if devpath in self.disks:
                            size = props.get("SIZE", "")
                            fstype = props.get("FSTYPE", "ext4")
                            label = props.get("LABEL", "")
                            if label:
                                disk_info[devpath] = f"{label} - {devpath} ({fstype}, {size})"
                            else:
                                disk_info[devpath] = f"{devpath} ({fstype}, {size})"
                
                for d in self.disks:
                    display_name = disk_info.get(d, d)
                    self.disk_combo.append_text(display_name)
                self.disk_combo.set_active(0)
                self.examine_btn.set_sensitive(True)
                self.repair_btn.set_sensitive(True)  # Onar butonu her zaman aktif
        except Exception as e:
            self.disk_combo.append_text(self.t("Could not read disks"))
            self.disk_combo.set_active(0)
            self.examine_btn.set_sensitive(False)
            self.repair_btn.set_sensitive(False)
            self.update_status_text(f'{self.t("Error")}: {e}')

    def get_selected_disk(self):
        idx = self.disk_combo.get_active()
        if idx < 0 or idx >= len(self.disks):
            return None
        return self.disks[idx]

    def on_examine_clicked(self, btn):
        disk = self.get_selected_disk()
        if not disk:
            self.update_status_text(self.t("Please select a disk."))
            return
        self.run_fsck(disk, check_only=True)

    def on_repair_clicked(self, btn):
        disk = self.get_selected_disk()
        if not disk:
            self.update_status_text(self.t("Please select a disk."))
            return
        self.run_fsck(disk, check_only=False)

    def run_fsck(self, disk, check_only=True):
        # Sadece examine butnunu devre dışı bırak, repair butonu her zaman aktf
        self.examine_btn.set_sensitive(False)
        
        # ext2/3/4 için e2fsck kullan - her iki durumda da root yetkileri gereklir
        if check_only:
            # Sadece okuma için -n kullan (bağlı dosya sistemlerinde çalışır)
            cmd = ["pkexec", "/sbin/e2fsck", "-n", disk]
        else:
            # Onarım için önce diski bağlantısını kes, sonra onar, tekrar bağla
            self.repair_mounted_disk(disk)
            return
        
        self.update_status_text(f'{disk} {self.t("examine started") if check_only else self.t("repair started")}...\n{self.t("Please wait.")}')
        
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
                    escaped_output = current_output.replace("<", "&lt;").replace(">", "&gt;")
                    GLib.idle_add(self.update_status_text, current_output)
                
                proc.wait()
                
                if proc.returncode == 0:
                    final_msg = self.t("Operation completed successfully.")
                else:
                    final_msg = f"{self.t('Operation completed with exit code')}: {proc.returncode}"
                
                final_output = "\n".join(output_lines) + "\n\n" + final_msg
                escaped_final = final_output.replace("<", "&lt;").replace(">", "&gt;")
                GLib.idle_add(self.update_status_text, final_output)
                
            except Exception as e:
                GLib.idle_add(self.update_status_text, f'{self.t("Error")}: {e}')
            finally:
                GLib.idle_add(self.examine_btn.set_sensitive, True)
                # Muayene sırasında repair butonu zaten aktif kalacak
        
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
