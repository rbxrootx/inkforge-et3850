"""Retro graphical front end for the ET-3850 jailbreak workbench."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import et3850_mod as core


BG = "#080b1c"
PANEL = "#111932"
PANEL2 = "#15213d"
EDGE = "#2b4b70"
CYAN = "#51f4ef"
PINK = "#fb5ecc"
LIME = "#baff88"
TEXT = "#e9f8ff"
MUTED = "#91a9c5"
FONT = "Consolas"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("INKFORGE // ET-3850")
        self.root.configure(bg=BG)
        self.root.geometry("1130x760")
        self.root.minsize(960, 650)
        self.events: queue.Queue = queue.Queue()
        self.source = tk.StringVar(value=str(core.ROOT.parent.parent / "work" / "FWCJ61TL.rcx"))
        self.squashfs = tk.StringVar(value=str(core.ROOT.parent.parent / "work" / "telnet4_squashfs_1.img"))
        self.first_squashfs = tk.StringVar(value=str(core.ROOT.parent.parent / "work" / "telnet2_squashfs_0.img"))
        fresh_name = "inkforge_et3850_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".rcx"
        self.destination = tk.StringVar(value=str(core.ROOT.parent.parent / "work" / fresh_name))
        self.flash_image = tk.StringVar(value=str(core.ROOT.parent.parent / "work" / "telnet4_wifi_auth_candidate.rcx"))
        saved_host = core.ROOT.parent.parent / "work" / "printer_host.txt"
        self.host = tk.StringVar(value=saved_host.read_text(encoding="ascii").strip()
                                 if saved_host.is_file() else "")
        self.password_file = tk.StringVar(value=str(core.ROOT.parent.parent / "work" / "telnet_password.txt"))
        self.root_command = tk.StringVar(value="id")
        self.append_byte = tk.BooleanVar(value=True)
        self.patch_ipl = tk.BooleanVar(value=True)
        self.busy = False
        self.view_name = "OVERVIEW"
        self.side_buttons: dict[str, tk.Button] = {}
        self._build_shell()
        self.show("OVERVIEW")
        self.root.after(80, self._drain)
        self.refresh_device()

    def _build_shell(self):
        header = tk.Frame(self.root, bg=BG, height=88)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="◆  INKFORGE // ET-3850", bg=BG, fg=CYAN,
                 font=(FONT, 23, "bold")).pack(side="left", padx=24, pady=16)
        tk.Label(header, text="OWNER MOD KIT    ·    XB22Q5", bg=BG, fg=PINK,
                 font=(FONT, 10, "bold")).pack(side="right", padx=26)
        rule = tk.Frame(self.root, bg=CYAN, height=2)
        rule.pack(fill="x")
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True)
        side = tk.Frame(main, bg="#0d1229", width=188)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="MODULES", bg="#0d1229", fg=MUTED,
                 font=(FONT, 10, "bold")).pack(anchor="w", padx=20, pady=(26, 10))
        for name, glyph in (("OVERVIEW", "◇"), ("PATCH LAB", "✦"),
                            ("FLASH PATH", "◈"), ("SHELL", ">_"),
                            ("LCD THEME", "▧"), ("SESSION LOG", "≡")):
            button = tk.Button(side, text=f"{glyph}  {name}", command=lambda n=name: self.show(n),
                               anchor="w", relief="flat", bd=0, padx=18, pady=13,
                               bg="#0d1229", fg=MUTED, activebackground=PANEL2,
                               activeforeground=CYAN, font=(FONT, 11, "bold"), cursor="hand2")
            button.pack(fill="x", pady=1)
            self.side_buttons[name] = button
        tk.Label(side, text="USB / LINUX / PIXELS", bg="#0d1229", fg="#58718d",
                 font=(FONT, 9)).pack(side="bottom", pady=22)
        self.content = tk.Frame(main, bg=BG)
        self.content.pack(side="left", fill="both", expand=True, padx=24, pady=22)
        self.status = tk.Label(self.root, text="●  READY   /   no firmware sent", bg="#101a32",
                               fg=LIME, anchor="w", padx=22, pady=9, font=(FONT, 10))
        self.status.pack(fill="x")
        self.log_lines: list[str] = []

    def _clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _title(self, title: str, subtitle: str):
        tk.Label(self.content, text=title, bg=BG, fg=TEXT,
                 font=(FONT, 23, "bold")).pack(anchor="w")
        tk.Label(self.content, text=subtitle, bg=BG, fg=MUTED,
                 font=(FONT, 11), wraplength=850, justify="left").pack(anchor="w", pady=(4, 21))

    def _card(self, parent=None, title=None):
        parent = parent or self.content
        outer = tk.Frame(parent, bg=EDGE, padx=1, pady=1)
        outer.pack(fill="x", pady=(0, 13))
        inner = tk.Frame(outer, bg=PANEL, padx=18, pady=14)
        inner.pack(fill="both", expand=True)
        if title:
            tk.Label(inner, text=title, bg=PANEL, fg=CYAN,
                     font=(FONT, 12, "bold")).pack(anchor="w", pady=(0, 9))
        return inner

    def _line(self, parent, text, color=TEXT, size=11):
        tk.Label(parent, text=text, bg=PANEL, fg=color, font=(FONT, size),
                 anchor="w", justify="left", wraplength=770).pack(anchor="w", pady=2)

    def _button(self, parent, text, command, color=CYAN):
        b = tk.Button(parent, text=text, command=command, bg=PANEL2, fg=color,
                      activebackground=color, activeforeground=BG, relief="flat",
                      bd=0, padx=16, pady=9, font=(FONT, 10, "bold"), cursor="hand2")
        b.pack(side="left", padx=(0, 10), pady=(4, 0))
        return b

    def show(self, name: str):
        self.view_name = name
        for key, button in self.side_buttons.items():
            button.configure(bg=PANEL2 if key == name else "#0d1229",
                             fg=CYAN if key == name else MUTED)
        self._clear()
        getattr(self, "_page_" + name.lower().replace(" ", "_"))()

    def _page_overview(self):
        self._title("DEVICE DECK", "A real device view. Detection reads Windows metadata and does not send USB commands.")
        card = self._card(title="01 / PHYSICAL LINK")
        self.device_text = tk.StringVar(value="Checking Windows PnP and print queue...")
        tk.Label(card, textvariable=self.device_text, bg=PANEL, fg=TEXT, font=(FONT, 11),
                 justify="left", anchor="w", wraplength=750).pack(fill="x")
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w", pady=(12, 0))
        self._button(row, "REFRESH USB + QUEUE", self.refresh_device)
        self._button(row, "QUERY LIVE D4", self.query_usb_status, PINK)
        card = self._card(title="02 / WHAT THIS PRINTER RUNS")
        self._line(card, "Linux 4.4.27 / ARM / uClibc / SquashFS", LIME)
        self._line(card, "The active network software and Realtek Wi-Fi driver are inside the extracted firmware.")
        self._line(card, "A custom password-gated root shell is live on TCP 2323. Stock SSH has not been established.")
        card = self._card(title="03 / MISSION STATE")
        self._line(card, "PATCH  ›  custom startup and Wi-Fi arguments verified on the live printer", LIME)
        self._line(card, "USB     ›  D4 control and full data transfer observed", LIME)
        self._line(card, "SHELL   ›  TCP 2323 returned uid=0(root)", LIME)
        self._line(card, "PRINT   ›  cake IPP job completed; physical page confirmation pending", MUTED)

    def _file_row(self, parent, label, variable, save=False):
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED,
                 font=(FONT, 10, "bold")).pack(anchor="w", pady=(7, 2))
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x")
        entry = tk.Entry(row, textvariable=variable, bg="#080e22", fg=TEXT,
                         insertbackground=CYAN, relief="flat", font=(FONT, 10))
        entry.pack(side="left", fill="x", expand=True, ipady=7)
        def choose():
            value = filedialog.asksaveasfilename(defaultextension=".rcx") if save else filedialog.askopenfilename()
            if value:
                variable.set(value)
        self._button(row, "...", choose)

    def _page_patch_lab(self):
        self._title("PATCH LAB", "Build from your pinned stock RCX. The full build creates a private password, patches both filesystems, and writes a checked image plus manifest.")
        card = self._card(title="INPUT / OUTPUT")
        self._file_row(card, "PINNED XB22Q5 SOURCE RCX", self.source)
        self._file_row(card, "PRIVATE PASSWORD FILE", self.password_file, save=True)
        self._file_row(card, "REBUILT ROOT / LOGIN SQUASHFS", self.first_squashfs)
        self._file_row(card, "REBUILT Wi-Fi / TELNET SQUASHFS", self.squashfs)
        self._file_row(card, "CANDIDATE RCX OUTPUT", self.destination, save=True)
        opts = tk.Frame(card, bg=PANEL)
        opts.pack(anchor="w", pady=10)
        for text, variable in (("append one length-gate byte", self.append_byte),
                               ("apply offline first-IPL branch control", self.patch_ipl)):
            tk.Checkbutton(opts, text=text, variable=variable, bg=PANEL, fg=MUTED,
                           selectcolor=PANEL2, activebackground=PANEL, activeforeground=TEXT,
                           font=(FONT, 10)).pack(anchor="w")
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w")
        self._button(row, "INSPECT SOURCE", lambda: self.inspect_path(self.source.get()))
        self._button(row, "INSPECT CANDIDATE", lambda: self.inspect_path(self.destination.get()))
        self._button(row, "BUILD FULL MOD", self.build_full_mod, LIME)
        self._button(row, "BUILD OFFLINE PATCH", self.build_patch, PINK)
        card = self._card(title="REPORT")
        self.patch_report = tk.Text(card, height=13, bg="#080e22", fg=LIME, insertbackground=CYAN,
                                    relief="flat", font=(FONT, 10), wrap="word", padx=12, pady=10)
        self.patch_report.pack(fill="both", expand=True)
        self.patch_report.insert("end", "BUILD FULL MOD creates both patched filesystems and a private login from the pinned source.\n\nBUILD OFFLINE PATCH uses prebuilt filesystems. Neither action contacts the printer.")

    def _page_flash_path(self):
        self._title("FLASH PATH", "The custom image installed: its startup marker and patched Wi-Fi settings were observed live.")
        card = self._card(title="LOCAL TRANSPORT")
        self._line(card, "USBPRINT MI_01 returned the printer's XB22Q5 version and status.", LIME)
        self._line(card, "EPSON-CTRL carries fl / gm update commands; EPSON-DATA carries the RCX binary stream.")
        card = self._card(title="INSTALL GATES")
        for label, state in (("Physical USB link", "OBSERVED"),
                             ("CTRL version/status framing", "OBSERVED"),
                             ("Signed-stock DATA transfer", "OBSERVED"),
                             ("Recovery mode and restore", "OPEN"),
                             ("Custom image startup", "OBSERVED"),
                             ("Root shell on TCP 2323", "OBSERVED")):
            self._line(card, f"{label:<35} {state}", LIME if state == "OBSERVED" else PINK)
        card = self._card(title="CHECKED USB INSTALLER")
        self._file_row(card, "HASH-LOCKED RCX TO PREFLIGHT OR SEND", self.flash_image)
        self._line(card, "Pinned images or a fresh InkForge image with a matching local manifest pass preflight.", LIME)
        self._line(card, "The custom image fails normal signature verification. A device rejection or failed boot is possible.", PINK)
        self._line(card, "The photo replaces a blue-wave asset; the owner reports a white home screen, so its display target is unverified.", PINK)
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w", pady=(8, 0))
        self._button(row, "PREFLIGHT CANDIDATE", self.preflight_flash)
        self._button(row, "SEND TO ATTACHED PRINTER", self.send_flash, PINK)
        self.flash_result = tk.StringVar(value="No firmware sent in this session.")
        tk.Label(card, textvariable=self.flash_result, bg=PANEL, fg=LIME,
                 font=(FONT, 10), justify="left", wraplength=750).pack(anchor="w", pady=(12, 0))

    def _page_shell(self):
        self._title("ROOT CONSOLE", "Run commands as root on your installed ET3850MOD printer and inspect its Linux internals.")
        card = self._card(title="CONNECTIVITY")
        self._line(card, "PRINTER IP OR HOSTNAME", MUTED)
        entry = tk.Entry(card, textvariable=self.host, bg="#080e22", fg=TEXT,
                         insertbackground=CYAN, relief="flat", font=(FONT, 12))
        entry.pack(fill="x", ipady=8, pady=6)
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w")
        self._button(row, "CHECK TCP 22 / 23 / 2323", self.probe_services)
        self._button(row, "VERIFY ROOT WITH ID", self.verify_root, PINK)
        self._button(row, "INTERACTIVE TERMINAL", self.open_terminal, LIME)
        self.service_result = tk.StringVar(value="No address probed.")
        tk.Label(card, textvariable=self.service_result, bg=PANEL, fg=LIME,
                 font=(FONT, 11), justify="left").pack(anchor="w", pady=(12, 0))
        card = self._card(title="PRIVATE LOGIN")
        self._file_row(card, "PASSWORD FILE", self.password_file)
        card = self._card(title="COMMAND DECK")
        self._line(card, "Root command (runs on the printer)", MUTED)
        tk.Entry(card, textvariable=self.root_command, bg="#080e22", fg=TEXT,
                 insertbackground=CYAN, relief="flat", font=(FONT, 11)).pack(fill="x", ipady=8)
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w", pady=8)
        self._button(row, "RUN AS ROOT", self.run_root_command, LIME)
        self._button(row, "FILES", lambda: self._preset("pwd; ls -la /opt/nwsoc; df -h"))
        self._button(row, "PROCESSES", lambda: self._preset("ps"))
        row = tk.Frame(card, bg=PANEL)
        row.pack(anchor="w")
        self._button(row, "WIFI", lambda: self._preset("cat /sys/module/8723du/parameters/rtw_power_mgnt; cat /sys/module/8723du/parameters/rtw_enusbss; ifconfig wlan0"))
        self._button(row, "BOOT LOG", lambda: self._preset("dmesg | tail -n 80"))
        self._button(row, "FIRMWARE", lambda: self._preset("uname -a; cat /proc/mtd; mount; md5sum /opt/nwsoc/nwsoc"))
        self.root_result = tk.Text(card, height=11, bg="#080e22", fg=LIME,
                                   insertbackground=CYAN, relief="flat", font=(FONT, 10),
                                   wrap="word", padx=12, pady=10)
        self.root_result.pack(fill="both", expand=True, pady=(12, 0))
        self.root_result.insert("end", "Root session ready. Commands run over the private port 2323 login.\n")

    def _page_lcd_theme(self):
        self._title("LCD THEME", "The owner's photo was rebuilt into an offline 320×240 UI image. Device display is unverified.")
        try:
            from PIL import Image, ImageTk
            photo = core.ROOT.parent / "et3850-wallpaper-photo-preview.png"
            image = Image.open(photo if photo.exists() else core.ASSETS / "demoscene-wave-preview.png").convert("RGB")
            image.thumbnail((760, 365))
            self.preview = ImageTk.PhotoImage(image)
            tk.Label(self.content, image=self.preview, bg=BG).pack(anchor="w", pady=(0, 13))
        except (ImportError, OSError) as error:
            tk.Label(self.content, text=f"Preview unavailable: {error}", bg=BG, fg=PINK).pack(anchor="w")
        card = self._card(title="PIXEL STATUS")
        self._line(card, "Owner photo: exact original people, cropped to the 320×240 screen.", CYAN)
        self._line(card, "Verified offline: rebuilt CROM changes only the 22,014-byte wallpaper PNG.", LIME)
        self._line(card, "Custom Linux patch installed; LCD photo placement remains unverified.", PINK)

    def _page_session_log(self):
        self._title("SESSION LOG", "Live actions performed by this client during this session.")
        card = self._card(title="EVENTS")
        self.log_box = tk.Text(card, bg="#080e22", fg=LIME, relief="flat",
                               font=(FONT, 10), wrap="word", height=25, padx=12, pady=10)
        self.log_box.pack(fill="both", expand=True)
        self.log_box.insert("end", "\n".join(self.log_lines) or "No actions yet.")

    def _log(self, line):
        from datetime import datetime
        entry = f"[{datetime.now():%H:%M:%S}] {line}"
        self.log_lines.append(entry)
        if self.view_name == "SESSION LOG":
            self.log_box.insert("end", entry + "\n")
            self.log_box.see("end")
        self.status.configure(text="●  " + line[:110], fg=CYAN)

    def _run_background(self, label, task, callback):
        if self.busy:
            return
        self.busy = True
        self._log(label + " ...")
        def worker():
            try:
                self.events.put((callback, task(), None))
            except Exception as error:
                self.events.put((callback, None, error))
        threading.Thread(target=worker, daemon=True).start()

    def _drain(self):
        try:
            while True:
                callback, result, error = self.events.get_nowait()
                self.busy = False
                if error:
                    self._log(f"ERROR: {error}")
                    messagebox.showerror("ET-3850 workbench", str(error))
                else:
                    callback(result)
        except queue.Empty:
            pass
        self.root.after(80, self._drain)

    def refresh_device(self):
        def done(result):
            usb, queues, interfaces = result
            match = [x for x in usb if x.get("device_id", "").upper() == core.VID_PID]
            lines = [f"USB: {'ET-3850 composite device detected' if match else 'no exact VID/PID match'}"]
            for item in interfaces:
                if item.get("pipes"):
                    line = ", ".join(f"{p['endpoint']} {p['type']} {p['max_packet']}B" for p in item["pipes"])
                    lines.append(f"WinUSB MI_{item['interface']:02d}: {line}")
                    break
            else:
                if interfaces:
                    lines.append(f"WinUSB: descriptor open unavailable ({interfaces[0].get('error', 'unknown')})")
            lines += [f"Queue: {x.get('name')}  /  {x.get('port')}  /  {x.get('jobs')} jobs" for x in queues]
            if not queues:
                lines.append("Print queue: no ET-3850 queue found")
            self._log("USB/queue discovery complete")
            if self.view_name == "OVERVIEW":
                self.device_text.set("\n".join(lines))
        self._run_background("Reading USB and spooler", lambda: (core.usb_devices(), core.printer_queues(), core.usb_bulk_interface()), done)

    def query_usb_status(self):
        import subprocess
        import sys
        def task():
            process = subprocess.run([sys.executable, str(core.ROOT / "usb_d4.py")],
                                     capture_output=True, text=True, timeout=20)
            if process.returncode:
                detail = process.stderr.strip().splitlines()[-1] if process.stderr.strip() else "D4 query failed"
                return {"usb_status": "unavailable", "detail": detail,
                        "hint": "Check that the printer is connected and no other updater holds its USB interface."}
            return json.loads(process.stdout)
        def done(result):
            self._log("Live D4 identity/status query completed")
            if self.view_name == "OVERVIEW":
                self.device_text.set(json.dumps(result, indent=2))
        self._run_background("Reading live USB D4 status", task, done)

    def preflight_flash(self):
        from usb_update import transfer
        path = Path(self.flash_image.get())
        manifest = path.with_suffix(path.suffix + ".manifest.json")
        def done(result):
            self._log("Firmware transfer preflight completed")
            if self.view_name == "FLASH PATH":
                self.flash_result.set(json.dumps(result, indent=2))
        self._run_background("Checking exact firmware hash and records", lambda: transfer(path, manifest=manifest if manifest.exists() else None), done)

    def send_flash(self):
        from usb_update import transfer
        path = Path(self.flash_image.get())
        manifest = path.with_suffix(path.suffix + ".manifest.json")
        if not messagebox.askyesno("Send firmware to ET-3850", "This will enter firmware update mode and stream the selected image over USB. The printer may reboot. Send now?"):
            return
        def done(result):
            self._log("USB transfer ended; verify printer boot and services")
            if self.view_name == "FLASH PATH":
                self.flash_result.set(json.dumps(result, indent=2))
        self._run_background("Sending checked firmware over USB D4", lambda: transfer(path, True, manifest=manifest if manifest.exists() else None), done)

    def inspect_path(self, path):
        if not path:
            return
        def done(result):
            self._log(f"Offline RCX inspection: {Path(path).name}")
            if self.view_name == "PATCH LAB":
                self.patch_report.delete("1.0", "end")
                self.patch_report.insert("end", json.dumps(result, indent=2))
        self._run_background("Inspecting RCX", lambda: core.inspect_firmware(Path(path)), done)

    def build_patch(self):
        args = (Path(self.source.get()), Path(self.squashfs.get()), Path(self.destination.get()),
                self.append_byte.get(), self.patch_ipl.get(), Path(self.first_squashfs.get()))
        def done(result):
            self._log("Offline build completed" if result["returncode"] == 0 else "Offline build failed")
            if self.view_name == "PATCH LAB":
                self.patch_report.delete("1.0", "end")
                self.patch_report.insert("end", result["stdout"] + result["stderr"])
        self._run_background("Building candidate in local scratch", lambda: core.build_candidate(*args), done)

    def build_full_mod(self):
        from inkforge import build
        source = Path(self.source.get())
        output = Path(self.destination.get())
        password = Path(self.password_file.get())
        def task():
            notes = []
            result = build(source, output, password, notes.append)
            return {"build": result, "steps": notes}
        def done(result):
            self.flash_image.set(result["build"]["image"])
            self._log("Private mod image and manifest built offline")
            if self.view_name == "PATCH LAB":
                self.patch_report.delete("1.0", "end")
                self.patch_report.insert("end", json.dumps(result, indent=2))
        self._run_background("Building full InkForge mod", task, done)

    def probe_services(self):
        host = self.host.get().strip()
        if not host:
            messagebox.showinfo("Printer address needed", "Enter the printer IP address or hostname.")
            return
        def done(result):
            self._log(f"TCP 22/23/2323 probe completed for {host}")
            if self.view_name == "SHELL":
                self.service_result.set("\n".join(f"{key.upper()}: {value}" for key, value in result.items()))
        self._run_background("Checking SSH/Telnet reachability", lambda: core.tcp_services(host), done)

    def verify_root(self):
        host = self.host.get().strip()
        if not host:
            messagebox.showinfo("Printer address needed", "Enter the printer IP address or hostname.")
            return
        from mod_shell import connect
        password_file = Path(self.password_file.get())
        def done(result):
            self._log(f"Root shell ID query completed for {host}")
            if self.view_name == "SHELL":
                self.service_result.set(result["output"])
        self._run_background("Authenticating to ET3850MOD", lambda: connect(host, password_file, "id"), done)

    def _preset(self, command: str):
        self.root_command.set(command)
        self.run_root_command()

    def run_root_command(self):
        from mod_shell import connect
        host = self.host.get().strip()
        command = self.root_command.get().strip()
        password = Path(self.password_file.get())
        if not host or not command:
            messagebox.showinfo("Root console", "Enter a printer address and command.")
            return
        def done(result):
            self._log(f"Root command completed on {host}")
            if self.view_name == "SHELL":
                self.root_result.delete("1.0", "end")
                self.root_result.insert("end", result["output"])
        self._run_background("Running root command", lambda: connect(host, password, command), done)

    def open_terminal(self):
        host = self.host.get().strip()
        password = Path(self.password_file.get())
        if not host or not password.is_file():
            messagebox.showinfo("Interactive terminal", "Enter the printer address and choose a private password file.")
            return
        if not re.fullmatch(r"[A-Za-z0-9.:-]+", host):
            messagebox.showerror("Interactive terminal", "Use a plain IP address or hostname.")
            return
        private_work = (core.ROOT.parent.parent / "work").resolve()
        if password.resolve().parent != private_work or not re.fullmatch(r"[A-Za-z0-9._-]+", password.name):
            messagebox.showerror("Interactive terminal", "Choose a password file directly inside this project's private work directory.")
            return
        python = Path(sys.executable)
        if python.name.lower() == "pythonw.exe":
            python = python.with_name("python.exe")
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        command = subprocess.list2cmdline([str(python), str(core.ROOT / "et3850_mod.py"),
                                           "shell", host, "--password-file", str(password)])
        # cmd /K keeps the window open when the connection fails, so the actual
        # socket or authentication error remains visible instead of vanishing.
        subprocess.Popen('cmd.exe /S /K "' + command + '"', cwd=core.ROOT,
                         creationflags=flags)
        self._log(f"Interactive root terminal opened for {host}")


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    run()
