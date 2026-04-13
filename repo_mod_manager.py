import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import zipfile
import shutil
import threading
import urllib.request
import urllib.parse
import json
import io
import tempfile


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

TS_API = "https://thunderstore.io/api/experimental/package/"
TS_COMMUNITY = "repo"
PAGE_SIZE = 50

# ── 颜色主题 ──────────────────────────────────────────
BG     = "#f0f4fa"
PANEL  = "#ffffff"
ACCENT = "#1a6ed8"
GREEN  = "#1a8a4a"
RED    = "#c0392b"
FG     = "#1a2a3a"
DIM    = "#5a7a9a"
BAR    = "#dce8f5"


# ── 本地核心逻辑 ──────────────────────────────────────
def find_plugins_dir():
    for root in SEARCH_ROOTS:
        candidate = os.path.join(root, STEAM_SUB)
        if os.path.isdir(candidate):
            return candidate
    return None


def list_mods(plugins_dir):
    mods = []
    if not plugins_dir or not os.path.isdir(plugins_dir):
        return mods
    for entry in sorted(os.scandir(plugins_dir), key=lambda e: e.name.lower()):
        if entry.is_dir():
            mods.append({"name": entry.name, "path": entry.path, "kind": "文件夹"})
        elif entry.is_file() and entry.name.lower().endswith(".dll"):
            mods.append({"name": entry.name, "path": entry.path, "kind": ".dll"})
    return mods


def install_zip_from_path(zip_path, plugins_dir):
    if not zipfile.is_zipfile(zip_path):
        return False, "所选文件不是有效的 ZIP 压缩包。"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(plugins_dir)
        return True, f"已成功解压到:\n{plugins_dir}"
    except Exception as exc:
        return False, f"解压失败: {exc}"


def install_zip_from_bytes(data: bytes, plugins_dir: str):
    try:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, "r") as zf:
            zf.extractall(plugins_dir)
        return True, f"已成功安装到:\n{plugins_dir}"
    except Exception as exc:
        return False, f"解压失败: {exc}"


def delete_mod(mod_path):
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


# ── Thunderstore API ───────────────────────────────────
def ts_search(keyword: str, page_cursor: str = ""):
    params = {"community_identifier": TS_COMMUNITY, "page_size": PAGE_SIZE}
    if keyword.strip():
        params["search"] = keyword.strip()
    if page_cursor:
        params["cursor"] = page_cursor
    url = TS_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "REPO-MOD-Manager/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def ts_download(download_url: str, progress_cb=None) -> bytes:
    req = urllib.request.Request(download_url, headers={"User-Agent": "REPO-MOD-Manager/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        buf   = io.BytesIO()
        received = 0
        chunk = 16 * 1024
        while True:
            block = resp.read(chunk)
            if not block:
                break
            buf.write(block)
            received += len(block)
            if progress_cb:
                progress_cb(received, total)
        return buf.getvalue()


# ── 下载进度弹窗 ──────────────────────────────────────
class DownloadDialog(tk.Toplevel):
    """模态进度条弹窗，下载完成后自动关闭。"""
    def __init__(self, parent, title="正在下载…"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=BG)
        self.grab_set()  # 模态
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # 禁止手动关闭

        w, h = 360, 110
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

        self._label = tk.Label(self, text="准备下载…", bg=BG, fg=FG,
                               font=("Segoe UI", 9), pady=8)
        self._label.pack()

        bar_frame = tk.Frame(self, bg=BG, padx=20)
        bar_frame.pack(fill=tk.X)
        self._pct_var = tk.DoubleVar(value=0)
        style = ttk.Style(self)
        style.configure("dl.Horizontal.TProgressbar",
                        troughcolor=PANEL, background=ACCENT, thickness=18)
        self._bar = ttk.Progressbar(bar_frame, variable=self._pct_var,
                                    maximum=100, length=320,
                                    style="dl.Horizontal.TProgressbar")
        self._bar.pack()

        self._pct_label = tk.Label(self, text="0%", bg=BG, fg=DIM,
                                   font=("Segoe UI", 9), pady=6)
        self._pct_label.pack()

    def update_progress(self, received: int, total: int):
        if total > 0:
            pct = received / total * 100
            self._pct_var.set(pct)
            self._pct_label.config(text=f"{pct:.1f}%  ({received//1024} KB / {total//1024} KB)")
            self._bar.config(mode="determinate")
        else:
            self._bar.config(mode="indeterminate")
            self._bar.step(2)
            self._pct_label.config(text=f"{received//1024} KB 已接收")
        self._label.config(text="正在下载…")
        self.update_idletasks()

    def set_installing(self):
        self._label.config(text="正在解压安装…")
        self._pct_var.set(100)
        self._pct_label.config(text="")
        self.update_idletasks()


# ── 通用按钮工厂 ──────────────────────────────────────
def make_btn(parent, text, cmd, color):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=color, fg="#ffffff",
        activebackground=color, activeforeground="#ffffff",
        relief=tk.FLAT, font=("Segoe UI", 9, "bold"),
        padx=10, pady=5, cursor="hand2", bd=0,
    )


# ── 主窗口 ────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("REPO MOD 管理器")
        self.geometry("900x580")
        self.minsize(720, 460)
        self.configure(bg=BG)
        self.resizable(True, True)

        self.plugins_dir = tk.StringVar(value="正在扫描…")
        self.status_var   = tk.StringVar(value="就绪")
        self._mods        = []

        self._build_ui()
        threading.Thread(target=self._auto_scan, daemon=True).start()

    # ── UI 总装 ───────────────────────────────────────
    def _build_ui(self):
        # 顶部路径栏（共享）
        top = tk.Frame(self, bg=BG, pady=6)
        top.pack(fill=tk.X, padx=12)
        tk.Label(top, text="plugins 目录:", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        tk.Entry(
            top, textvariable=self.plugins_dir,
            bg=PANEL, fg=FG, insertbackground=FG,
            relief=tk.FLAT, font=("Segoe UI", 9), bd=4,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        make_btn(top, "浏览…", self._browse_dir, ACCENT).pack(side=tk.LEFT)

        # Notebook
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=FG,
                        fieldbackground=PANEL, rowheight=26, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=ACCENT,
                        foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG,
                        padding=[12, 5], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 0))

        tab_local  = tk.Frame(nb, bg=BG)
        tab_online = tk.Frame(nb, bg=BG)
        nb.add(tab_local,  text="  📂 已安装 MOD  ")
        nb.add(tab_online, text="  🌐 在线浏览安装  ")

        self._build_local_tab(tab_local)
        self._build_online_tab(tab_online)

        # 底部状态栏
        tk.Label(self, textvariable=self.status_var, bg=BAR, fg=DIM,
                 anchor=tk.W, font=("Segoe UI", 9), padx=8, pady=4
                 ).pack(fill=tk.X, side=tk.BOTTOM)

    # ── 标签页 1：本地已安装 ──────────────────────────
    def _build_local_tab(self, parent):
        btn_bar = tk.Frame(parent, bg=BG, pady=4)
        btn_bar.pack(fill=tk.X)
        make_btn(btn_bar, "📦 导入 ZIP 安装", self._install_local_zip, GREEN).pack(side=tk.LEFT, padx=(0, 8))
        make_btn(btn_bar, "🗑 删除选中 MOD",  self._delete_mod,        RED   ).pack(side=tk.LEFT, padx=(0, 8))
        make_btn(btn_bar, "🔄 刷新列表",       self._refresh_local,     ACCENT).pack(side=tk.LEFT)

        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)

        cols = ("name", "kind", "path")
        self.local_tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        self.local_tree.heading("name", text="MOD 名称")
        self.local_tree.heading("kind", text="类型")
        self.local_tree.heading("path", text="路径")
        self.local_tree.column("name", width=220, minwidth=120)
        self.local_tree.column("kind", width=70,  minwidth=60, anchor=tk.CENTER)
        self.local_tree.column("path", width=500, minwidth=200)

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.local_tree.yview)
        self.local_tree.configure(yscrollcommand=vsb.set)
        self.local_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # ── 标签页 2：在线 Thunderstore ───────────────────
    def _build_online_tab(self, parent):
        # 搜索栏
        search_bar = tk.Frame(parent, bg=BG, pady=4)
        search_bar.pack(fill=tk.X)
        tk.Label(search_bar, text="搜索:", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_bar, textvariable=self._search_var,
            bg=PANEL, fg=FG, insertbackground=FG,
            relief=tk.FLAT, font=("Segoe UI", 10), bd=4, width=30,
        )
        search_entry.pack(side=tk.LEFT, padx=(6, 6))
        search_entry.bind("<Return>", lambda _: self._ts_search_start())
        make_btn(search_bar, "🔍 搜索", self._ts_search_start, ACCENT).pack(side=tk.LEFT, padx=(0, 8))
        make_btn(search_bar, "⬅ 上一页", self._ts_prev_page, PANEL).pack(side=tk.LEFT, padx=(0, 4))
        self._page_label = tk.Label(search_bar, text="第 1 页", bg=BG, fg=DIM, font=("Segoe UI", 9))
        self._page_label.pack(side=tk.LEFT, padx=4)
        make_btn(search_bar, "下一页 ➡", self._ts_next_page, PANEL).pack(side=tk.LEFT, padx=(4, 0))

        # MOD 列表
        list_frame = tk.Frame(parent, bg=BG)
        list_frame.pack(fill=tk.BOTH, expand=True)

        ts_cols = ("name", "author", "version", "downloads", "desc")
        self.ts_tree = ttk.Treeview(list_frame, columns=ts_cols, show="headings", selectmode="browse")
        self.ts_tree.heading("name",      text="MOD 名称")
        self.ts_tree.heading("author",    text="作者")
        self.ts_tree.heading("version",   text="版本")
        self.ts_tree.heading("downloads", text="下载量")
        self.ts_tree.heading("desc",      text="简介")
        self.ts_tree.column("name",      width=180, minwidth=100)
        self.ts_tree.column("author",    width=110, minwidth=80)
        self.ts_tree.column("version",   width=70,  minwidth=60, anchor=tk.CENTER)
        self.ts_tree.column("downloads", width=80,  minwidth=60, anchor=tk.CENTER)
        self.ts_tree.column("desc",      width=380, minwidth=150)

        vsb2 = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.ts_tree.yview)
        self.ts_tree.configure(yscrollcommand=vsb2.set)
        self.ts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb2.pack(side=tk.RIGHT, fill=tk.Y)

        # 安装按钮
        bottom = tk.Frame(parent, bg=BG, pady=6)
        bottom.pack(fill=tk.X)
        make_btn(bottom, "⬇ 下载并安装选中 MOD", self._ts_install_selected, GREEN).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(bottom, text="（将自动解压到 plugins 目录）", bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)

        # 分页状态
        self._ts_cursor_stack = []   # 历史 cursor，用于"上一页"
        self._ts_next_cursor  = ""
        self._ts_current_page = 1
        self._ts_results      = []   # 当前页数据，含 download_url

    # ── 本地标签页逻辑 ────────────────────────────────
    def _auto_scan(self):
        found = find_plugins_dir()
        if found:
            self.plugins_dir.set(found)
            self._set_status(f"已自动定位: {found}")
        else:
            self.plugins_dir.set("")
            self._set_status("未自动找到 plugins 目录，请手动浏览选择。")
        self._refresh_local()

    def _browse_dir(self):
        d = filedialog.askdirectory(title="选择 BepInEx/plugins 目录")
        if d:
            self.plugins_dir.set(d.replace("/", "\\"))
            self._refresh_local()

    def _refresh_local(self):
        self.local_tree.delete(*self.local_tree.get_children())
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            self._set_status("plugins 目录无效，请重新选择。")
            return
        self._mods = list_mods(d)
        for mod in self._mods:
            self.local_tree.insert("", tk.END, values=(mod["name"], mod["kind"], mod["path"]))
        self._set_status(f"共找到 {len(self._mods)} 个 MOD。")

    def _install_local_zip(self):
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
        ok, msg = install_zip_from_path(zip_path, d)
        if ok:
            messagebox.showinfo("安装成功", msg)
            self._refresh_local()
        else:
            messagebox.showerror("安装失败", msg)

    def _delete_mod(self):
        sel = self.local_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选中一个 MOD。")
            return
        name, kind, path = self.local_tree.item(sel[0])["values"]
        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除以下 MOD 吗？\n\n名称：{name}\n类型：{kind}\n路径：{path}\n\n此操作不可恢复！",
        ):
            return
        ok, msg = delete_mod(path)
        if ok:
            self._set_status(f"已删除: {name}")
            self._refresh_local()
        else:
            messagebox.showerror("删除失败", msg)

    # ── 在线标签页逻辑 ────────────────────────────────
    def _ts_search_start(self):
        self._ts_cursor_stack.clear()
        self._ts_next_cursor  = ""
        self._ts_current_page = 1
        self._ts_fetch(cursor="")

    def _ts_next_page(self):
        if not self._ts_next_cursor:
            return
        self._ts_cursor_stack.append(self._ts_next_cursor)
        self._ts_current_page += 1
        self._ts_fetch(cursor=self._ts_next_cursor)

    def _ts_prev_page(self):
        if self._ts_current_page <= 1:
            return
        self._ts_cursor_stack.pop()  # 当前页 cursor
        prev = self._ts_cursor_stack[-1] if self._ts_cursor_stack else ""
        self._ts_current_page -= 1
        self._ts_fetch(cursor=prev, push_stack=False)

    def _ts_fetch(self, cursor: str, push_stack: bool = True):
        self._set_status("正在从 Thunderstore 获取数据…")
        kw = self._search_var.get()
        threading.Thread(target=self._ts_fetch_worker, args=(kw, cursor), daemon=True).start()

    def _ts_fetch_worker(self, keyword: str, cursor: str):
        try:
            data = ts_search(keyword, cursor)
        except Exception as exc:
            self.after(0, lambda: self._set_status(f"请求失败: {exc}"))
            return
        self.after(0, lambda: self._ts_populate(data))

    def _ts_populate(self, data: dict):
        self.ts_tree.delete(*self.ts_tree.get_children())
        self._ts_results.clear()
        self._ts_next_cursor = ""

        # 解析 next cursor
        next_url = data.get("next", "")
        if next_url:
            parsed = urllib.parse.urlparse(next_url)
            qs     = urllib.parse.parse_qs(parsed.query)
            self._ts_next_cursor = qs.get("cursor", [""])[0]

        results = data.get("results", [])
        # 只保留属于 REPO 社区的包
        repo_results = []
        for pkg in results:
            listings = pkg.get("community_listings", [])
            if any(l.get("community") == TS_COMMUNITY for l in listings):
                repo_results.append(pkg)

        for pkg in repo_results:
            latest  = pkg.get("latest", {})
            name    = pkg.get("name", "")
            author  = pkg.get("namespace", "")
            version = latest.get("version_number", "")
            dl_cnt  = latest.get("downloads", 0)
            desc    = latest.get("description", "")[:80]
            dl_url  = latest.get("download_url", "")
            self._ts_results.append({"name": name, "author": author, "download_url": dl_url})
            self.ts_tree.insert("", tk.END, values=(name, author, version, dl_cnt, desc))

        self._page_label.config(text=f"第 {self._ts_current_page} 页")
        self._set_status(f"找到 {len(repo_results)} 个 REPO MOD（第 {self._ts_current_page} 页）")

    def _ts_install_selected(self):
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showwarning("警告", "请先设置有效的 plugins 目录。")
            return
        sel = self.ts_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选中一个 MOD。")
            return
        idx = self.ts_tree.index(sel[0])
        if idx >= len(self._ts_results):
            return
        pkg      = self._ts_results[idx]
        name     = pkg["name"]
        dl_url   = pkg["download_url"]
        if not dl_url:
            messagebox.showerror("错误", "该 MOD 无可用下载链接。")
            return
        if not messagebox.askyesno("确认安装", f"确定要下载并安装以下 MOD 吗？\n\n{pkg['author']}-{name}"):
            return
        dlg = DownloadDialog(self, title=f"安装 {name}")
        self._set_status(f"正在下载 {name}…")
        threading.Thread(
            target=self._ts_download_worker,
            args=(name, dl_url, d, dlg),
            daemon=True,
        ).start()

    def _ts_download_worker(self, name: str, dl_url: str, plugins_dir: str, dlg: "DownloadDialog"):
        def on_progress(received, total):
            self.after(0, lambda: dlg.update_progress(received, total))
        try:
            data = ts_download(dl_url, progress_cb=on_progress)
        except Exception as exc:
            self.after(0, dlg.destroy)
            self.after(0, lambda: messagebox.showerror("下载失败", str(exc)))
            self.after(0, lambda: self._set_status("下载失败。"))
            return
        self.after(0, dlg.set_installing)
        ok, msg = install_zip_from_bytes(data, plugins_dir)
        self.after(0, dlg.destroy)
        if ok:
            self.after(0, lambda: self._set_status(f"✅ {name} 安装完成"))
            self.after(0, self._refresh_local)
        else:
            self.after(0, lambda: messagebox.showerror("安装失败", msg))
            self.after(0, lambda: self._set_status("安装失败。"))

    def _set_status(self, text: str):
        self.status_var.set(text)


# ── 入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
