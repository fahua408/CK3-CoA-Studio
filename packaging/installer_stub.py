"""Lightweight native Windows Setup Wizard for CK3 CoA Studio."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_NAME = "CK3 CoA Studio"
APP_TITLE = "十字军之王3纹章生成工坊"
APP_VERSION = "1.0.0"
MAIN_EXE = "CK3-CoA-Studio.exe"


def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent / name


def create_shortcut(lnk_path: Path, target_exe: Path, work_dir: Path, icon_path: Path) -> None:
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{str(lnk_path).replace("'", "''")}'); "
        f"$s.TargetPath = '{str(target_exe).replace("'", "''")}'; "
        f"$s.WorkingDirectory = '{str(work_dir).replace("'", "''")}'; "
        f"$s.IconLocation = '{str(icon_path).replace("'", "''")}'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class InstallerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_TITLE} v{APP_VERSION} 安装向导")
        self.root.geometry("540x380")
        self.root.resizable(False, False)
        self.root.configure(bg="#14161B")

        ico = resource_path("app_icon.ico")
        if ico.is_file():
            try:
                self.root.iconbitmap(str(ico))
            except Exception:
                pass

        local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        default_dir = str(Path(local_app) / "Programs" / "CK3-CoA-Studio")

        self.dir_var = tk.StringVar(value=default_dir)
        self.desktop_var = tk.BooleanVar(value=True)
        self.startmenu_var = tk.BooleanVar(value=True)
        self.launch_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="准备就绪，点击「立即安装」开始安装。")
        self._installing = False

        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Gold.Horizontal.TProgressbar", troughcolor="#1E222B", background="#D4AF37")

        # Header
        header = tk.Frame(self.root, bg="#1A1D24", height=74)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=f"🛡 {APP_TITLE} v{APP_VERSION}",
            bg="#1A1D24",
            fg="#E8C766",
            font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(anchor="w", padx=20, pady=(12, 2))
        tk.Label(
            header,
            text="CK3 纹章图片管理 · 1:1 正方形截图与编辑 · TXT 一键生成与复制",
            bg="#1A1D24",
            fg="#9CA3AF",
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", padx=20)

        body = tk.Frame(self.root, bg="#14161B")
        body.pack(fill="both", expand=True, padx=22, pady=16)

        tk.Label(
            body,
            text="安装位置:",
            bg="#14161B",
            fg="#EAE4D7",
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w")

        path_row = tk.Frame(body, bg="#14161B")
        path_row.pack(fill="x", pady=(6, 12))
        self.dir_entry = tk.Entry(
            path_row,
            textvariable=self.dir_var,
            bg="#111318",
            fg="#F2ECE0",
            insertbackground="#E8C766",
            relief="flat",
            font=("Microsoft YaHei UI", 9),
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.browse_btn = tk.Button(
            path_row,
            text="浏览...",
            command=self._choose_dir,
            bg="#242934",
            fg="#EAE4D7",
            activebackground="#2E3544",
            relief="flat",
            padx=12,
            pady=4,
        )
        self.browse_btn.pack(side="right")

        opts = [
            ("创建桌面快捷方式", self.desktop_var),
            ("创建开始菜单快捷方式", self.startmenu_var),
            ("安装完成后立即启动程序", self.launch_var),
        ]
        for text, var in opts:
            cb = tk.Checkbutton(
                body,
                text=text,
                variable=var,
                bg="#14161B",
                fg="#EAE4D7",
                selectcolor="#242934",
                activebackground="#14161B",
                activeforeground="#EAE4D7",
                font=("Microsoft YaHei UI", 9),
            )
            cb.pack(anchor="w", pady=2)

        self.progress = ttk.Progressbar(
            body,
            orient="horizontal",
            mode="determinate",
            style="Gold.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(18, 6))

        tk.Label(
            body,
            textvariable=self.status_var,
            bg="#14161B",
            fg="#B6B0A2",
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")

        footer = tk.Frame(self.root, bg="#14161B")
        footer.pack(fill="x", padx=22, pady=(0, 18))

        self.cancel_btn = tk.Button(
            footer,
            text="取消",
            command=self.root.destroy,
            bg="#242934",
            fg="#EAE4D7",
            relief="flat",
            padx=16,
            pady=6,
        )
        self.cancel_btn.pack(side="right", padx=(8, 0))

        self.install_btn = tk.Button(
            footer,
            text="立即安装",
            command=self._start_install,
            bg="#C99E32",
            fg="#121418",
            activebackground="#DFB544",
            relief="flat",
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=20,
            pady=6,
        )
        self.install_btn.pack(side="right")

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get())
        if chosen:
            target = Path(chosen)
            if target.name.lower() != "ck3-coa-studio":
                target = target / "CK3-CoA-Studio"
            self.dir_var.set(str(target))

    def _start_install(self) -> None:
        if self._installing:
            return
        payload = resource_path("app_payload.zip")
        if not payload.is_file():
            messagebox.showerror("错误", "安装包缺少核心数据 (app_payload.zip)。")
            return

        install_dir = Path(self.dir_var.get().strip())
        if not str(install_dir):
            messagebox.showwarning("提示", "请选择有效的安装目录。")
            return

        self._installing = True
        self.install_btn.config(state="disabled")
        self.browse_btn.config(state="disabled")
        self.dir_entry.config(state="disabled")
        self.cancel_btn.config(state="disabled")

        threading.Thread(
            target=self._do_install,
            args=(payload, install_dir),
            daemon=True,
        ).start()

    def _do_install(self, payload: Path, install_dir: Path) -> None:
        try:
            install_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(payload, "r") as zf:
                members = zf.infolist()
                total = max(1, len(members))
                for idx, member in enumerate(members, 1):
                    zf.extract(member, install_dir)
                    if idx % 10 == 0 or idx == total:
                        pct = int(idx * 100 / total)
                        self.root.after(
                            0,
                            lambda p=pct, name=member.filename: self._update_progress(
                                p, f"正在解压 ({p}%): {name[:48]}"
                            ),
                        )

            exe_path = install_dir / MAIN_EXE
            ico_path = install_dir / "_internal" / "assets" / "app_icon.ico"
            if not ico_path.is_file():
                ico_path = exe_path

            # Write simple uninstaller script
            uninst = install_dir / "uninstall.bat"
            uninst.write_text(
                f'@echo off\r\n'
                f'echo 正在卸载 {APP_TITLE}...\r\n'
                f'rmdir /s /q "{install_dir}"\r\n'
                f'echo 卸载完成。\r\n',
                encoding="utf-8",
            )

            if self.desktop_var.get():
                self.root.after(0, lambda: self.status_var.set("正在创建桌面快捷方式..."))
                desktop = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
                create_shortcut(desktop / f"{APP_TITLE}.lnk", exe_path, install_dir, ico_path)

            if self.startmenu_var.get():
                self.root.after(0, lambda: self.status_var.set("正在创建开始菜单快捷方式..."))
                appdata = os.environ.get("APPDATA", "")
                if appdata:
                    sm_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_TITLE
                    create_shortcut(sm_dir / f"{APP_TITLE}.lnk", exe_path, install_dir, ico_path)

            self.root.after(0, lambda: self._finish_ok(exe_path))
        except Exception as exc:
            self.root.after(0, lambda: self._finish_err(str(exc)))

    def _update_progress(self, pct: int, msg: str) -> None:
        self.progress["value"] = pct
        self.status_var.set(msg)

    def _finish_ok(self, exe_path: Path) -> None:
        self.progress["value"] = 100
        self.status_var.set("安装完成！")
        if self.launch_var.get() and exe_path.is_file():
            subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
        else:
            messagebox.showinfo("安装完成", f"{APP_TITLE} 已安装至:\n{exe_path.parent}")
        self.root.destroy()

    def _finish_err(self, err: str) -> None:
        self._installing = False
        self.install_btn.config(state="normal")
        self.browse_btn.config(state="normal")
        self.dir_entry.config(state="normal")
        self.cancel_btn.config(state="normal")
        self.status_var.set("安装失败。")
        messagebox.showerror("安装失败", err)


def main() -> None:
    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
