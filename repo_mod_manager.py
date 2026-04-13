import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import zipfile
import shutil
import threading


# ── 常量 ──────────────────────────────────────────────
STEAM_SUB = r"Steam\steamapps\common\REPO\BepInEx\plugins"
SEARCH_ROOTS = [
    r"C:\Program Files (x86)",
    r"C:\Program Files",
    r"D:\Program Files (x86)",
    r"D:\Program Files",
    r"D:\SteamLibrary",
    r"E:\Program Files (x86)",
    r"E:\Program Files",
    r"E:\SteamLibrary",
    r"F:\Program Files (x86)",
    r"F:\Program Files",
    r"F:\SteamLibrary",
]


# ── 核心逻辑 ──────────────────────────────────────────
def find_plugins_dir():
    """扫描常见 Steam 目录，返回 plugins 文件夹路径；未找到返回 None。"""
    for root in SEARCH_ROOTS:
        candidate = os.path.join(root, STEAM_SUB)
        if os.path.isdir(candidate):
            return candidate
    return None


def list_mods(plugins_dir):
    """
    列出 plugins 目录下所有子文件夹和顶层 .dll 文件。
    返回 list[dict]，每项含 name / path / kind。
    """
    mods = []
    if not plugins_dir or not os.path.isdir(plugins_dir):
        return mods
    for entry in sorted(os.scandir(plugins_dir), key=lambda e: e.name.lower()):
        if entry.is_dir():
            mods.append({"name": entry.name, "path": entry.path, "kind": "文件夹"})
        elif entry.is_file() and entry.name.lower().endswith(".dll"):
            mods.append({"name": entry.name, "path": entry.path, "kind": ".dll"})
    return mods


def install_zip(zip_path, plugins_dir):
    """
    将 ZIP 压缩包解压到 plugins_dir。
    返回 (success: bool, message: str)。
    """
    if not zipfile.is_zipfile(zip_path):
        return False, "所选文件不是有效的 ZIP 压缩包。"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(plugins_dir)
        return True, f"已成功解压到:\n{plugins_dir}"
    except Exception as exc:
        return False, f"解压失败: {exc}"


def delete_mod(mod_path):
    """
    安全删除单个 MOD（文件夹或 .dll 文件）。
    返回 (success: bool, message: str)。
    """
    try:
        if os.path.isdir(mod_path):
            shutil.rmtree(mod_path)
        elif os.path.isfile(mod_path):
            os.remove(mod_path)
        else:
            return False, "路径不存在，可能已被手动删除。"
        return True, "删除成功。"
    except Exception as exc:
        return False, f"删除失败: {exc}"


# ── 界面 ──────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("REPO MOD 管理器")
        self.geometry("780x520")
        self.minsize(640, 420)
        self.configure(bg="#1e1e2e")
        self.resizable(True, True)

        self.plugins_dir = tk.StringVar(value="正在扫描…")
        self._mods = []

        self._build_ui()
        # 扫描放在后台线程，避免启动时卡顿
        threading.Thread(target=self._auto_scan, daemon=True).start()

    # ── UI 构建 ────────────────────────────────────────
    def _build_ui(self):
        BG = "#1e1e2e"
        PANEL = "#2a2a3e"
        ACCENT = "#7c5cbf"
        FG = "#cdd6f4"
        DIM = "#6c7086"

        # 顶部路径栏
        top = tk.Frame(self, bg=BG, pady=6)
        top.pack(fill=tk.X, padx=12)

        tk.Label(top, text="plugins 目录:", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        tk.Entry(
            top,
            textvariable=self.plugins_dir,
            bg=PANEL,
            fg=FG,
            insertbackground=FG,
            relief=tk.FLAT,
            font=("Segoe UI", 9),
            bd=4,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        self._btn(top, "浏览…", self._browse_dir, ACCENT).pack(side=tk.LEFT)

        # 操作按钮栏
        btn_bar = tk.Frame(self, bg=BG, pady=4)
        btn_bar.pack(fill=tk.X, padx=12)
        self._btn(btn_bar, "📦 导入 ZIP 安装 MOD", self._install_mod, "#4c8a5c").pack(side=tk.LEFT, padx=(0, 8))
        self._btn(btn_bar, "🗑 删除选中 MOD", self._delete_mod, "#a3404a").pack(side=tk.LEFT, padx=(0, 8))
        self._btn(btn_bar, "🔄 刷新列表", self._refresh, ACCENT).pack(side=tk.LEFT)

        # MOD 列表
        frame = tk.Frame(self, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 0))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=PANEL,
            foreground=FG,
            fieldbackground=PANEL,
            rowheight=26,
            font=("Segoe UI", 10),
        )
        style.configure("Treeview.Heading", background=ACCENT, foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])

        cols = ("name", "kind", "path")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name", text="MOD 名称")
        self.tree.heading("kind", text="类型")
        self.tree.heading("path", text="路径")
        self.tree.column("name", width=220, minwidth=120)
        self.tree.column("kind", width=70, minwidth=60, anchor=tk.CENTER)
        self.tree.column("path", width=440, minwidth=200)

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = tk.Label(
            self,
            textvariable=self.status_var,
            bg="#11111b",
            fg=DIM,
            anchor=tk.W,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    @staticmethod
    def _btn(parent, text, cmd, color):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=color,
            fg="#ffffff",
            activebackground=color,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=5,
            cursor="hand2",
            bd=0,
        )

    # ── 逻辑方法 ───────────────────────────────────────
    def _auto_scan(self):
        found = find_plugins_dir()
        if found:
            self.plugins_dir.set(found)
            self._set_status(f"已自动定位: {found}")
        else:
            self.plugins_dir.set("")
            self._set_status("未自动找到 plugins 目录，请手动浏览选择。")
        self._refresh()

    def _browse_dir(self):
        d = filedialog.askdirectory(title="选择 BepInEx/plugins 目录")
        if d:
            self.plugins_dir.set(d.replace("/", "\\"))
            self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            self._set_status("plugins 目录无效，请重新选择。")
            return
        self._mods = list_mods(d)
        for mod in self._mods:
            self.tree.insert("", tk.END, values=(mod["name"], mod["kind"], mod["path"]))
        count = len(self._mods)
        self._set_status(f"共找到 {count} 个 MOD。")

    def _install_mod(self):
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showwarning("警告", "请先设置有效的 plugins 目录。")
            return
        zip_path = filedialog.askopenfilename(
            title="选择 MOD 压缩包 (.zip)",
            filetypes=[("ZIP 压缩包", "*.zip"), ("所有文件", "*.*")],
        )
        if not zip_path:
            return
        ok, msg = install_zip(zip_path, d)
        if ok:
            messagebox.showinfo("安装成功", msg)
            self._refresh()
        else:
            messagebox.showerror("安装失败", msg)

    def _delete_mod(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选中一个 MOD。")
            return
        item = self.tree.item(sel[0])
        name, kind, path = item["values"]
        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除以下 MOD 吗？\n\n名称：{name}\n类型：{kind}\n路径：{path}\n\n此操作不可恢复！",
        ):
            return
        ok, msg = delete_mod(path)
        if ok:
            self._set_status(f"已删除: {name}")
            self._refresh()
        else:
            messagebox.showerror("删除失败", msg)

    def _set_status(self, text):
        self.status_var.set(text)


# ── 入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
