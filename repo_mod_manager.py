import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import zipfile
import shutil
import threading
import urllib.request
import urllib.parse
import json
import io
import tempfile
import ssl

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# ── 配置文件（与 exe / 脚本同目录）──────────────────────
def _app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_app_dir(), "config.json")

def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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

TS_API    = "https://thunderstore.io/c/repo/api/v1/package/"
PAGE_SIZE = 20

# ── 颜色主题 ──────────────────────────────────────────
BG        = "#f0f4fa"
PANEL     = "#ffffff"
ACCENT    = "#1a6ed8"
GREEN     = "#1a8a4a"
RED       = "#c0392b"
FG        = "#1a2a3a"
DIM       = "#5a7a9a"
BAR       = "#dce8f5"
BTN_LIGHT = "#5ba3e8"  # 淡蓝按钮色


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
_icon_cache: dict = {}  # url -> PhotoImage，避免重复下载


def translate_to_zh(text: str) -> str:
    """调用 Google 免费翻译接口将英文翻译为中文。"""
    if not text.strip():
        return text
    params = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text})
    url = "https://translate.googleapis.com/translate_a/single?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode())
    return "".join(seg[0] for seg in data[0] if seg[0])


_BATCH_SEP = " |||| "

def translate_batch(texts: list) -> list:
    """一次请求翻译多条文本，返回等长结果列表。"""
    if not texts:
        return []
    n = len(texts)
    # 清理文本：截断并去掉内部可能存在的分隔符
    cleaned = [(t[:200].replace("||||", "") if t and t.strip() else " ") for t in texts]
    joined = _BATCH_SEP.join(cleaned)
    params = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": joined})
    url = "https://translate.googleapis.com/translate_a/single?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode())
    translated = "".join(seg[0] for seg in data[0] if seg[0])
    # |||| 是纯符号，Google 翻译会原样保留
    parts = translated.split("||||")
    # 补齐到原长度
    while len(parts) < n:
        parts.append("")
    return [p.strip() for p in parts[:n]]


_ts_all: list = []   # 全量包缓存


def ts_fetch_all() -> list:
    """一次性担取并缓存全量 REPO 包。"""
    global _ts_all
    req = urllib.request.Request(TS_API, headers={"User-Agent": "REPO-MOD-Manager/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        _ts_all = json.loads(resp.read().decode())
    return _ts_all


def ts_get_page(keyword: str, page: int) -> dict:
    """在本地缓存中搜索并分页，返回 {results, page, total_pages, total}。"""
    kw = keyword.strip().lower()
    if kw:
        filtered = [
            p for p in _ts_all
            if kw in p.get("name", "").lower()
            or kw in p.get("owner", "").lower()
            or kw in (p.get("versions") or [{}])[0].get("description", "").lower()
        ]
    else:
        filtered = _ts_all
    total       = len(filtered)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page        = max(1, min(page, total_pages))
    start       = (page - 1) * PAGE_SIZE
    return {
        "results":     filtered[start: start + PAGE_SIZE],
        "page":        page,
        "total_pages": total_pages,
        "total":       total,
    }


def ts_download(download_url: str, progress_cb=None) -> bytes:
    req = urllib.request.Request(download_url, headers={"User-Agent": "REPO-MOD-Manager/1.0"})
    with urllib.request.urlopen(req, timeout=60, context=_SSL_CTX) as resp:
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


# ── MOD 详情弹窗 ──────────────────────────────────────
class ModDetailDialog(tk.Toplevel):
    """双击列表项后弹出的 MOD 详情窗口，含图标、描述、依赖和安装按钮。"""

    ICON_SIZE = 128

    def __init__(self, parent, pkg: dict, install_cb):
        super().__init__(parent)
        self.title(f"{pkg['author']}-{pkg['name']}")
        self.configure(bg=BG)
        self.resizable(True, True)
        self._install_cb = install_cb
        self._img_ref    = None  # 防止 GC

        w, h = 560, 460
        px = parent.winfo_rootx() + (parent.winfo_width()  - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")
        self.minsize(440, 360)

        self._build(pkg)
        # 异步加载图标
        if pkg.get("icon"):
            threading.Thread(target=self._load_icon, args=(pkg["icon"],), daemon=True).start()

    def _build(self, pkg: dict):
        # 顶部：图标 + 基本信息
        top = tk.Frame(self, bg=BG, pady=12, padx=16)
        top.pack(fill=tk.X)

        # 图标占位
        self._icon_label = tk.Label(
            top, bg=PANEL, width=self.ICON_SIZE, height=self.ICON_SIZE,
            text="加载中…", fg=DIM, font=("Segoe UI", 8),
            relief=tk.FLAT,
        )
        self._icon_label.pack(side=tk.LEFT, padx=(0, 16))
        self._icon_label.config(width=self.ICON_SIZE, height=self.ICON_SIZE)

        # 右侧文字信息
        info = tk.Frame(top, bg=BG)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(info, text=pkg["name"], bg=BG, fg=FG,
                 font=("Segoe UI", 14, "bold"), anchor=tk.W).pack(fill=tk.X)
        tk.Label(info, text=f"作者：{pkg['author']}    版本：{pkg['version']}",
                 bg=BG, fg=DIM, font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X, pady=(2, 0))
        tk.Label(info, text=f"下载量：{pkg['downloads']}    评分：{pkg['rating_score']}",
                 bg=BG, fg=DIM, font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X)
        if pkg.get("website_url"):
            tk.Label(info, text=f"主页：{pkg['website_url']}",
                     bg=BG, fg=ACCENT, font=("Segoe UI", 9), anchor=tk.W,
                     cursor="hand2").pack(fill=tk.X, pady=(2, 0))

        # 分隔线
        tk.Frame(self, bg=BAR, height=1).pack(fill=tk.X, padx=16)

        # 描述
        desc_frame = tk.Frame(self, bg=BG, padx=16, pady=8)
        desc_frame.pack(fill=tk.BOTH, expand=True)

        desc_header = tk.Frame(desc_frame, bg=BG)
        desc_header.pack(fill=tk.X)
        tk.Label(desc_header, text="简介", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(side=tk.LEFT)
        self._trans_btn = make_label_btn(
            desc_header, "🌐 翻译为中文", self._do_translate, BTN_LIGHT, font_size=8,
        )
        self._trans_btn.pack(side=tk.LEFT, padx=(8, 0))
        self._orig_desc = pkg.get("description", "")

        self._desc_text = tk.Text(
            desc_frame, bg=PANEL, fg=FG, font=("Segoe UI", 9),
            relief=tk.FLAT, wrap=tk.WORD, height=6, bd=4,
            state=tk.NORMAL,
        )
        self._desc_text.insert(tk.END, self._orig_desc or "（无简介）")
        self._desc_text.config(state=tk.DISABLED)
        self._desc_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # 依赖
        deps = pkg.get("dependencies", [])
        if deps:
            tk.Label(desc_frame, text=f"依赖（{len(deps)} 个）", bg=BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(fill=tk.X, pady=(8, 0))
            dep_box = tk.Text(
                desc_frame, bg=PANEL, fg=DIM, font=("Segoe UI", 8),
                relief=tk.FLAT, wrap=tk.WORD, height=3, bd=4,
                state=tk.NORMAL,
            )
            dep_box.insert(tk.END, "\n".join(deps))
            dep_box.config(state=tk.DISABLED)
            dep_box.pack(fill=tk.X, pady=(2, 0))

        # 底部按钮
        btn_bar = tk.Frame(self, bg=BAR, pady=8, padx=16)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)
        make_btn(btn_bar, "⬇ 下载并安装", self._on_install, GREEN).pack(side=tk.LEFT)
        make_btn(btn_bar, "关闭", self.destroy, BTN_LIGHT).pack(side=tk.RIGHT)

        # 弹窗显示后自动翻译简介
        self.after(100, self._do_translate)

    def _on_install(self):
        self.destroy()
        self._install_cb()

    def _do_translate(self):
        self._trans_btn.config(text="翻译中…")
        self._trans_btn.unbind("<Button-1>")
        threading.Thread(target=self._translate_worker, daemon=True).start()

    def _translate_worker(self):
        try:
            zh = translate_to_zh(self._orig_desc)
        except Exception as exc:
            zh = f"（翻译失败：{exc}）"
        self.after(0, lambda: self._show_translation(zh))

    def _show_translation(self, zh: str):
        self._desc_text.config(state=tk.NORMAL)
        self._desc_text.delete("1.0", tk.END)
        self._desc_text.insert(tk.END, zh)
        self._desc_text.config(state=tk.DISABLED)
        self._trans_btn.config(text="🔄 显示原文")
        self._trans_btn.bind("<Button-1>", lambda e: self._show_original())

    def _show_original(self):
        self._desc_text.config(state=tk.NORMAL)
        self._desc_text.delete("1.0", tk.END)
        self._desc_text.insert(tk.END, self._orig_desc or "（无简介）")
        self._desc_text.config(state=tk.DISABLED)
        self._trans_btn.config(text="🌐 翻译为中文")
        self._trans_btn.bind("<Button-1>", lambda e: self._do_translate())

    def _load_icon(self, url: str):
        try:
            req  = urllib.request.Request(url, headers={"User-Agent": "REPO-MOD-Manager/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                raw = resp.read()
            import base64
            # 用 tkinter 的 PhotoImage 加载 PNG（tkinter 内置支持）
            b64 = base64.b64encode(raw).decode()
            img = tk.PhotoImage(data=b64)
            # 缩放到 ICON_SIZE
            iw, ih = img.width(), img.height()
            scale = max(1, max(iw, ih) // self.ICON_SIZE)
            img = img.subsample(scale, scale)
            self._img_ref = img
            self.after(0, lambda: self._icon_label.config(image=img, text="", width=0, height=0))
        except Exception:
            self.after(0, lambda: self._icon_label.config(text="图标\n加载失败"))


# ── 通用按钮工厂 ──────────────────────────────────────
def make_btn(parent, text, cmd, color):
    # 非强调色一律替换为 BTN_LIGHT
    if color not in (ACCENT, GREEN, RED):
        color = BTN_LIGHT
    lbl = tk.Label(
        parent, text=text, bg=color, fg="#ffffff",
        font=("Segoe UI", 9, "bold"),
        padx=10, pady=5, cursor="hand2",
    )
    lbl.bind("<Button-1>", lambda e: cmd())
    lbl.bind("<Enter>",    lambda e: lbl.config(bg=_darken(color)))
    lbl.bind("<Leave>",    lambda e: lbl.config(bg=color))
    return lbl


def _darken(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{int(r*0.82):02x}{int(g*0.82):02x}{int(b*0.82):02x}"


def make_label_btn(parent, text, cmd, color, font_size=8):
    """Label 模拟按钮，在 macOS 上颜色完全可控。"""
    lbl = tk.Label(
        parent, text=text, bg=color, fg="#ffffff",
        font=("Segoe UI", font_size, "bold"),
        padx=8, pady=4, cursor="hand2",
    )
    lbl.bind("<Button-1>", lambda e: cmd())
    lbl.bind("<Enter>",    lambda e: lbl.config(bg=_darken(color)))
    lbl.bind("<Leave>",    lambda e: lbl.config(bg=color))
    return lbl


# ── 主窗口 ────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("REPO MOD 管理器")
        self.geometry("900x580")
        self.minsize(720, 460)
        self.configure(bg=BG)
        self.resizable(True, True)

        cfg = load_config()
        self.plugins_dir = tk.StringVar(value=cfg.get("plugins_dir", "正在扫描…"))
        self.status_var   = tk.StringVar(value="就绪")
        self._mods        = []

        self._build_ui()
        # 若配置中已有路径则跳过自动扫描，否则后台扫描
        if cfg.get("plugins_dir"):
            self._set_status(f"已从配置加载路径: {cfg['plugins_dir']}")
            threading.Thread(target=self._refresh_local, daemon=True).start()
        else:
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
        nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed(nb, tab_online))

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
            relief=tk.FLAT, font=("Segoe UI", 10), bd=4, width=28,
        )
        search_entry.pack(side=tk.LEFT, padx=(6, 6))
        search_entry.bind("<Return>", lambda _: self._ts_search_start())
        make_btn(search_bar, "🔍 搜索", self._ts_search_start, ACCENT).pack(side=tk.LEFT, padx=(0, 6))
        make_btn(search_bar, "⬅ 上一页", self._ts_prev_page, BTN_LIGHT).pack(side=tk.LEFT, padx=(0, 2))
        self._page_label = tk.Label(search_bar, text="第 1 页", bg=BG, fg=DIM, font=("Segoe UI", 9))
        self._page_label.pack(side=tk.LEFT, padx=4)
        make_btn(search_bar, "下一页 ➡", self._ts_next_page, BTN_LIGHT).pack(side=tk.LEFT, padx=(2, 0))
        self._trans_list_btn = make_btn(search_bar, "🌐 翻译", self._translate_list, BTN_LIGHT)
        self._trans_list_btn.pack(side=tk.LEFT, padx=(6, 0))

        # 卡片滚动区
        grid_outer = tk.Frame(parent, bg=BG)
        grid_outer.pack(fill=tk.BOTH, expand=True)
        self._card_canvas = tk.Canvas(grid_outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(grid_outer, orient=tk.VERTICAL, command=self._card_canvas.yview)
        self._card_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._card_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._card_frame = tk.Frame(self._card_canvas, bg=BG)
        self._card_canvas_win = self._card_canvas.create_window((0, 0), window=self._card_frame, anchor="nw")
        self._card_frame.bind("<Configure>", self._on_card_frame_configure)
        self._card_canvas.bind("<Configure>", self._on_card_canvas_configure)
        self._card_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._card_canvas.bind("<Button-4>",   self._on_mousewheel)
        self._card_canvas.bind("<Button-5>",   self._on_mousewheel)
        self._card_frame.bind("<MouseWheel>",  self._on_mousewheel)
        self._card_frame.bind("<Button-4>",    self._on_mousewheel)
        self._card_frame.bind("<Button-5>",    self._on_mousewheel)

        # 加载中占位提示
        self._loading_label = tk.Label(
            self._card_frame, text="⏳ 正在拉取 MOD 列表，请稍候…",
            bg=BG, fg=DIM, font=("Segoe UI", 13), pady=40,
        )
        self._loading_label.pack(expand=True)

        # 分页状态
        self._ts_page        = 1
        self._ts_total_pages = 1
        self._ts_fetched     = False
        self._ts_translated  = False
        self._ts_results     = []
        self._card_img_refs: list = []
        self._installed_names: set = set()  # 本地已安装包名集合（小写）

    # ── 本地标签页逻辑 ────────────────────────────────
    def _auto_scan(self):
        found = find_plugins_dir()
        if found:
            self.plugins_dir.set(found)
            save_config({"plugins_dir": found})
            self._set_status(f"已自动定位: {found}")
        else:
            self.plugins_dir.set("")
            self._set_status("未自动找到 plugins 目录，请手动浏览选择。")
        self._refresh_local()

    def _browse_dir(self):
        d = filedialog.askdirectory(title="选择 BepInEx/plugins 目录")
        if d:
            path = d.replace("/", "\\")
            self.plugins_dir.set(path)
            save_config({"plugins_dir": path})
            self._refresh_local()

    def _refresh_local(self):
        self.local_tree.delete(*self.local_tree.get_children())
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            self._set_status("plugins 目录无效，请重新选择。")
            return
        self._mods = list_mods(d)
        # 更新已安装名称集合（去掉 .dll 后缀，转小写）
        self._installed_names = {
            os.path.splitext(m["name"])[0].lower() for m in self._mods
        }
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
    # ── 卡片区辅助 ────────────────────────────────────
    def _on_card_frame_configure(self, event=None):
        self._card_canvas.configure(scrollregion=self._card_canvas.bbox("all"))

    def _on_card_canvas_configure(self, event=None):
        self._card_canvas.itemconfig(self._card_canvas_win, width=event.width)
        # 窗口宽度变化时重新布局卡片列数
        if self._ts_results:
            self._relayout_cards()

    def _on_mousewheel(self, event):
        if event.num == 4:
            self._card_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._card_canvas.yview_scroll(1, "units")
        else:
            # macOS 触摸板 delta 单位是像素，除以 4 使滚动更平滑
            self._card_canvas.yview_scroll(int(-1 * (event.delta / 4)), "units")

    def _bind_scroll(self, widget):
        """\u9012归绑定 widget 及其全部子组件的滚轮事件。"""
        widget.bind("<MouseWheel>", self._on_mousewheel)
        widget.bind("<Button-4>",   self._on_mousewheel)
        widget.bind("<Button-5>",   self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_scroll(child)

    def _on_tab_changed(self, nb, tab_online):
        if str(nb.select()) == str(tab_online):
            if not self._ts_fetched:
                self._set_status("正在拉取 REPO MOD 列表（首次需要约10秒）…")
                threading.Thread(target=self._ts_fetch_all_worker, daemon=True).start()

    def _relayout_cards(self):
        CARD_W = 220
        cw = self._card_canvas.winfo_width() or 860
        cols = max(1, cw // (CARD_W + 12))
        cards = self._card_frame.winfo_children()
        for idx, card in enumerate(cards):
            row, col = divmod(idx, cols)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._card_frame.grid_columnconfigure(col, weight=1)

    def _ts_show_detail(self, pkg):
        ModDetailDialog(self, pkg, install_cb=lambda: self._ts_do_install(pkg))

    def _ts_search_start(self):
        self._ts_page = 1
        if not self._ts_fetched:
            self._set_status("正在担取 REPO MOD 列表（首次需要约10秒）…")
            threading.Thread(target=self._ts_fetch_all_worker, daemon=True).start()
        else:
            self._ts_render_page()

    def _ts_next_page(self):
        if self._ts_page >= self._ts_total_pages:
            return
        self._ts_page += 1
        self._ts_render_page()

    def _ts_prev_page(self):
        if self._ts_page <= 1:
            return
        self._ts_page -= 1
        self._ts_render_page()

    def _ts_fetch_all_worker(self):
        try:
            ts_fetch_all()
        except Exception as exc:
            msg = str(exc)
            self.after(0, lambda: self._set_status(f"拉取失败: {msg}"))
            return
        self._ts_fetched = True
        self.after(0, self._ts_render_page)

    def _ts_render_page(self):
        kw   = self._search_var.get()
        data = ts_get_page(kw, self._ts_page)
        self._ts_page        = data["page"]
        self._ts_total_pages = data["total_pages"]
        self._ts_render(data)
        if self._ts_translated:
            self._set_trans_list_btn("🔄 原文", self._restore_list)
            # 翻译模式下，找出当前页尚未翻译的条目，异步翻译
            untranslated = [
                (i, p["name"], p.get("description", ""))
                for i, p in enumerate(self._ts_results)
                if p.get("_raw_pkg") is not None and "zh_name" not in p["_raw_pkg"]
            ]
            if untranslated:
                self._set_trans_list_btn("翻译中…", None)
                threading.Thread(
                    target=self._translate_list_worker,
                    args=(untranslated,),
                    daemon=True,
                ).start()
        else:
            self._set_trans_list_btn("🌐 翻译", self._translate_list)

    def _ts_render(self, data: dict):
        self._ts_results.clear()
        self._card_img_refs.clear()

        for w in self._card_frame.winfo_children():
            w.destroy()

        CARD_W = 220
        IMG_H  = 150
        cw     = self._card_canvas.winfo_width() or 860
        COLS   = max(1, cw // (CARD_W + 12))

        for idx, pkg in enumerate(data.get("results", [])):
            versions = pkg.get("versions") or []
            latest   = versions[0] if versions else {}
            name    = pkg.get("name", "")
            author  = pkg.get("owner", "")
            version = latest.get("version_number", "")
            dl_cnt  = latest.get("downloads", 0)
            desc    = latest.get("description", "")
            dl_url  = latest.get("download_url", "")
            icon    = latest.get("icon", "")
            deps    = latest.get("dependencies", [])
            website = latest.get("website_url", "")
            rating  = pkg.get("rating_score", 0)
            cats    = pkg.get("categories", [])
            # 优先使用已缓存的翻译结果
            disp_name = pkg.get("zh_name", name) if self._ts_translated else name
            disp_desc = pkg.get("zh_desc", desc) if self._ts_translated else desc
            self._ts_results.append({
                "name": name, "author": author, "version": version,
                "download_url": dl_url, "icon": icon,
                "description": desc, "dependencies": deps,
                "website_url": website, "rating_score": rating,
                "downloads": dl_cnt, "categories": cats,
                "_raw_pkg": pkg,  # 指向 _ts_all 原始对象
            })
            disp_name = disp_name  # 绑定到局部变量供下方使用
            disp_desc = disp_desc

            row, col = divmod(idx, COLS)
            _pkg = self._ts_results[-1]

            card = tk.Frame(self._card_frame, bg=PANEL, bd=0,
                            highlightthickness=1, highlightbackground="#d0dce8",
                            width=CARD_W, cursor="hand2")
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self._card_frame.grid_columnconfigure(col, weight=1)

            # 图片区
            img_frame = tk.Frame(card, bg="#c8d8e8", height=IMG_H, width=CARD_W)
            img_frame.pack(fill=tk.X)
            img_frame.pack_propagate(False)
            img_lbl = tk.Label(img_frame, bg="#c8d8e8", text="", cursor="hand2")
            img_lbl.place(relx=0.5, rely=0.5, anchor="center")
            # 已安装徽标
            if name.lower() in self._installed_names or \
               f"{author.lower()}-{name.lower()}" in self._installed_names:
                tk.Label(img_frame, text="✓ 已安装",
                         bg=GREEN, fg="#ffffff",
                         font=("Segoe UI", 8, "bold"), padx=6, pady=2,
                         ).place(relx=1.0, rely=0.0, anchor="ne")

            # 文字区
            info = tk.Frame(card, bg=PANEL, padx=8, pady=6)
            info.pack(fill=tk.BOTH, expand=True)

            meta_row = tk.Frame(info, bg=PANEL)
            meta_row.pack(fill=tk.X)
            tk.Label(meta_row, text=f"⬇ {dl_cnt:,}", bg=PANEL, fg=DIM,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)
            tk.Label(meta_row, text=f"  👍 {rating}", bg=PANEL, fg=DIM,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)

            name_lbl = tk.Label(info, text=disp_name, bg=PANEL, fg=FG,
                                font=("Segoe UI", 10, "bold"),
                                anchor=tk.W, wraplength=CARD_W - 20, justify=tk.LEFT)
            name_lbl.pack(fill=tk.X, pady=(2, 0))

            tk.Label(info, text=f"By {author}", bg=PANEL, fg=ACCENT,
                     font=("Segoe UI", 8), anchor=tk.W).pack(fill=tk.X)

            desc_lbl = tk.Label(info, text=disp_desc[:120], bg=PANEL, fg=DIM,
                                font=("Segoe UI", 8), anchor=tk.W,
                                wraplength=CARD_W - 20, justify=tk.LEFT)
            desc_lbl.pack(fill=tk.X, pady=(4, 0))

            if cats:
                tag_row = tk.Frame(info, bg=PANEL)
                tag_row.pack(fill=tk.X, pady=(4, 0))
                for cat in cats[:3]:
                    tk.Label(tag_row, text=cat, bg=BAR, fg=DIM,
                             font=("Segoe UI", 7), padx=4, pady=1).pack(side=tk.LEFT, padx=(0, 3))

            btn_row = tk.Frame(info, bg=PANEL)
            btn_row.pack(fill=tk.X, pady=(6, 2))
            make_label_btn(btn_row, "⬇ 安装",
                           lambda p=_pkg: self._ts_do_install(p),
                           BTN_LIGHT).pack(side=tk.LEFT)

            for w in (card, img_frame, img_lbl, info, name_lbl, desc_lbl, btn_row):
                w.bind("<Button-1>", lambda e, p=_pkg: self._ts_show_detail(p))

            self._bind_scroll(card)

            if icon:
                threading.Thread(
                    target=self._load_card_icon,
                    args=(img_lbl, img_frame, icon, IMG_H),
                    daemon=True,
                ).start()

        self._page_label.config(text=f"第 {self._ts_page} / {self._ts_total_pages} 页")
        total = len(_ts_all)
        self._set_status(f"共 {total} 个 MOD，第 {self._ts_page}/{self._ts_total_pages} 页，每页 {PAGE_SIZE} 条")
        self._card_canvas.yview_moveto(0)
        self._card_frame.update_idletasks()
        self._card_canvas.configure(scrollregion=self._card_canvas.bbox("all"))

    def _load_card_icon(self, lbl, frame, url, img_h):
        import base64
        global _icon_cache
        if url not in _icon_cache:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "REPO-MOD-Manager/1.0"})
                with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:
                    raw = resp.read()
                b64 = base64.b64encode(raw).decode()
                img = tk.PhotoImage(data=b64)
                iw, ih = img.width(), img.height()
                scale = max(1, max(iw, ih) // img_h)
                img = img.subsample(scale, scale)
                _icon_cache[url] = img
            except Exception:
                return
        img = _icon_cache[url]
        self._card_img_refs.append(img)
        self.after(0, lambda: self._set_card_image(lbl, frame, img))

    def _set_card_image(self, lbl, frame, img):
        try:
            lbl.config(image=img)
            frame.config(bg=PANEL)
        except Exception:
            pass

    def _set_trans_list_btn(self, text: str, cmd):
        self._trans_list_btn.config(text=text)
        self._trans_list_btn.unbind("<Button-1>")
        if cmd:
            self._trans_list_btn.bind("<Button-1>", lambda e: cmd())

    def _translate_list(self):
        if not self._ts_results:
            return
        self._set_trans_list_btn("翻译中…", None)
        self._set_status("正在翻译当前页，请稍候…")
        items = [(i, p["name"], p.get("description", "")) for i, p in enumerate(self._ts_results)]
        threading.Thread(target=self._translate_list_worker, args=(items,), daemon=True).start()

    def _translate_list_worker(self, items: list):
        indices = [i for i, _, _ in items]
        names   = [n for _, n, _ in items]
        descs   = [d for _, _, d in items]
        try:
            zh_names = translate_batch(names)
        except Exception:
            zh_names = names
        try:
            zh_descs = translate_batch(descs)
        except Exception:
            zh_descs = descs
        results = list(zip(indices, zh_names, zh_descs))
        self.after(0, lambda: self._apply_list_translation(results))

    def _apply_list_translation(self, results: list):
        # 回写翻译结果到 _ts_all 原始对象
        for idx, zh_name, zh_desc in results:
            if idx >= len(self._ts_results):
                continue
            raw_pkg = self._ts_results[idx].get("_raw_pkg")
            if raw_pkg is not None:
                raw_pkg["zh_name"] = zh_name
                raw_pkg["zh_desc"] = zh_desc
        self._ts_translated = True
        # 重新渲染当前页（会直接使用已缓存的译文）
        self._ts_render_page()
        self._set_status("翻译完成")

    def _restore_list(self):
        # 清除 _ts_all 中的翻译缓存
        for pkg in _ts_all:
            pkg.pop("zh_name", None)
            pkg.pop("zh_desc", None)
        self._ts_translated = False
        self._ts_render_page()
        self._set_status("已恢复原文")

    def _ts_do_install(self, pkg: dict):
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showwarning("警告", "请先设置有效的 plugins 目录。")
            return
        name   = pkg["name"]
        dl_url = pkg["download_url"]
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
            if self._ts_fetched:
                self.after(0, self._ts_render_page)
        else:
            self.after(0, lambda: messagebox.showerror("安装失败", msg))
            self.after(0, lambda: self._set_status("安装失败。"))

    def _set_status(self, text: str):
        self.status_var.set(text)


# ── 入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
