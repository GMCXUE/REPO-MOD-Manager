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


# ── 配置文件（存放到系统 AppData 目录）──────────────────────
def _config_dir() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(appdata, "REPOModManager")
    os.makedirs(d, exist_ok=True)
    return d

CONFIG_FILE = os.path.join(_config_dir(), "config.json")

def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(data: dict):
    try:
        cfg = load_config()
        cfg.update(data)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── 常量 ──────────────────────────────────────────────
TS_API    = "https://thunderstore.io/c/repo/api/v1/package/"
PAGE_SIZE = 20

# ── 多语言字典 ─────────────────────────────────────────
_STRINGS: dict = {
    # 顶部路径栏
    "game_dir":           {"zh": "游戏目录:", "zh-tw": "遊戲目錄:", "en": "Game Dir:", "ja": "ゲームフォルダ:", "fr": "Dossier jeu:", "ru": "Папка игры:", "es": "Dir. juego:"},
    "plugins_dir":        {"zh": "plugins 目录:", "zh-tw": "plugins 目錄:", "en": "Plugins Dir:", "ja": "pluginsフォルダ:", "fr": "Dossier plugins:", "ru": "Папка plugins:", "es": "Dir. plugins:"},
    "browse":             {"zh": "浏览…", "zh-tw": "瀏覽…", "en": "Browse…", "ja": "参照…", "fr": "Parcourir…", "ru": "Обзор…", "es": "Buscar…"},
    "install_bepinex":    {"zh": "⬇ 安装 BepInEx", "zh-tw": "⬇ 安裝 BepInEx", "en": "⬇ Install BepInEx", "ja": "⬇ BepInEx導入", "fr": "⬇ Installer BepInEx", "ru": "⬇ Установить BepInEx", "es": "⬇ Instalar BepInEx"},
    "launch_game":        {"zh": "🎮\n启动游戏", "zh-tw": "🎮\n啟動遊戲", "en": "🎮\nLaunch", "ja": "🎮\n起動", "fr": "🎮\nLancer", "ru": "🎮\nЗапуск", "es": "🎮\nIniciar"},
    # 标签页
    "tab_local":          {"zh": "  📂 已安装 MOD  ", "zh-tw": "  📂 已安裝 MOD  ", "en": "  📂 Installed MODs  ", "ja": "  📂 導入済みMOD  ", "fr": "  📂 MODs installés  ", "ru": "  📂 Установленные  ", "es": "  📂 MODs instalados  "},
    "tab_online":         {"zh": "  🌐 在线浏览安装  ", "zh-tw": "  🌐 線上瀏覽安裝  ", "en": "  🌐 Browse & Install  ", "ja": "  🌐 オンライン  ", "fr": "  🌐 Parcourir & Installer  ", "ru": "  🌐 Обзор и установка  ", "es": "  🌐 Ver e instalar  "},
    # 本地标签页
    "import_zip":         {"zh": "📦 导入 ZIP 安装", "zh-tw": "📦 匯入 ZIP 安裝", "en": "📦 Import ZIP", "ja": "📦 ZIPインポート", "fr": "📦 Importer ZIP", "ru": "📦 Импорт ZIP", "es": "📦 Importar ZIP"},
    "refresh":            {"zh": "🔄 刷新列表", "zh-tw": "🔄 重新整理", "en": "🔄 Refresh", "ja": "🔄 更新", "fr": "🔄 Actualiser", "ru": "🔄 Обновить", "es": "🔄 Actualizar"},
    "delete":             {"zh": "🗑 删除", "zh-tw": "🗑 刪除", "en": "🗑 Delete", "ja": "🗑 削除", "fr": "🗑 Supprimer", "ru": "🗑 Удалить", "es": "🗑 Eliminar"},
    "confirm_delete":     {"zh": "确认删除", "zh-tw": "確認刪除", "en": "Confirm Delete", "ja": "削除確認", "fr": "Confirmer la suppression", "ru": "Подтвердить удаление", "es": "Confirmar eliminación"},
    "confirm_delete_msg": {"zh": "确定要删除以下 MOD 吗？\n\n名称：{name}\n路径：{path}\n\n此操作不可恢复！",
                           "zh-tw": "確定要刪除以下 MOD 嗎？\n\n名稱：{name}\n路徑：{path}\n\n此操作無法復原！",
                           "en": "Delete this MOD?\n\nName: {name}\nPath: {path}\n\nThis cannot be undone!",
                           "ja": "このMODを削除しますか？\n\n名前：{name}\nパス：{path}\n\nこの操作は元に戻せません！",
                           "fr": "Supprimer ce MOD ?\n\nNom : {name}\nChemin : {path}\n\nCette action est irréversible !",
                           "ru": "Удалить этот MOD?\n\nИмя: {name}\nПуть: {path}\n\nЭто действие необратимо!",
                           "es": "¿Eliminar este MOD?\n\nNombre: {name}\nRuta: {path}\n\n¡Esta acción es irreversible!"},
    "delete_ok":          {"zh": "已删除: {name}", "zh-tw": "已刪除: {name}", "en": "Deleted: {name}", "ja": "削除しました: {name}", "fr": "Supprimé : {name}", "ru": "Удалено: {name}", "es": "Eliminado: {name}"},
    "delete_fail":        {"zh": "删除失败", "zh-tw": "刪除失敗", "en": "Delete Failed", "ja": "削除失敗", "fr": "Échec de la suppression", "ru": "Ошибка удаления", "es": "Error al eliminar"},
    "folder":             {"zh": "文件夹", "zh-tw": "資料夾", "en": "Folder", "ja": "フォルダ", "fr": "Dossier", "ru": "Папка", "es": "Carpeta"},
    "dll":                {"zh": ".dll", "zh-tw": ".dll", "en": ".dll", "ja": ".dll", "fr": ".dll", "ru": ".dll", "es": ".dll"},
    "mods_found":         {"zh": "共找到 {n} 个 MOD。", "zh-tw": "共找到 {n} 個 MOD。", "en": "Found {n} MOD(s).", "ja": "{n} 個のMODが見つかりました。", "fr": "{n} MOD(s) trouvé(s).", "ru": "Найдено MOD: {n}.", "es": "Se encontraron {n} MOD(s)."},
    "invalid_plugins":    {"zh": "plugins 目录无效，请重新选择。", "zh-tw": "plugins 目錄無效，請重新選擇。", "en": "Invalid plugins directory.", "ja": "pluginsフォルダが無効です。再選択してください。", "fr": "Dossier plugins invalide.", "ru": "Неверная папка plugins.", "es": "Directorio plugins no válido."},
    # 在线标签页
    "search":             {"zh": "搜索:", "zh-tw": "搜尋:", "en": "Search:", "ja": "検索:", "fr": "Recherche :", "ru": "Поиск:", "es": "Buscar:"},
    "search_btn":         {"zh": "🔍 搜索", "zh-tw": "🔍 搜尋", "en": "🔍 Search", "ja": "🔍 検索", "fr": "🔍 Chercher", "ru": "🔍 Найти", "es": "🔍 Buscar"},
    "chinese_mods":       {"zh": "🇨🇳 中文 MOD", "zh-tw": "🇨🇳 中文 MOD", "en": "🇨🇳 Chinese MOD", "ja": "🇨🇳 中国語MOD", "fr": "🇨🇳 MODs chinois", "ru": "🇨🇳 Китайские MOD", "es": "🇨🇳 MODs chinos"},
    "prev_page":          {"zh": "⬅ 上一页", "zh-tw": "⬅ 上一頁", "en": "⬅ Prev", "ja": "⬅ 前へ", "fr": "⬅ Préc.", "ru": "⬅ Назад", "es": "⬅ Ant."},
    "next_page":          {"zh": "下一页 ➡", "zh-tw": "下一頁 ➡", "en": "Next ➡", "ja": "次へ ➡", "fr": "Suiv. ➡", "ru": "Вперёд ➡", "es": "Sig. ➡"},
    "page_label":         {"zh": "第 {p} 页", "zh-tw": "第 {p} 頁", "en": "Page {p}", "ja": "{p} ページ", "fr": "Page {p}", "ru": "Стр. {p}", "es": "Pág. {p}"},
    "translate_btn":      {"zh": "🌐 翻译", "zh-tw": "🌐 翻譯", "en": "🌐 Translate", "ja": "🌐 翻訳", "fr": "🌐 Traduire", "ru": "🌐 Перевод", "es": "🌐 Traducir"},
    "sort_options":       {"zh": ["最后更新", "最新", "下载最多", "评分最高"],
                           "zh-tw": ["最後更新", "最新", "下載最多", "評分最高"],
                           "en": ["Last Updated", "Newest", "Most Downloaded", "Top Rated"],
                           "ja": ["最終更新", "最新", "DL数順", "高評価"],
                           "fr": ["Dernière MàJ", "Nouveaux", "Plus téléchargés", "Mieux notés"],
                           "ru": ["Обновлённые", "Новые", "Популярные", "Топ рейтинга"],
                           "es": ["Últ. actualiz.", "Más nuevos", "Más descargados", "Mejor valorados"]},
    "install_btn":        {"zh": "⬇ 下载并安装", "zh-tw": "⬇ 下載並安裝", "en": "⬇ Install", "ja": "⬇ インストール", "fr": "⬇ Installer", "ru": "⬇ Установить", "es": "⬇ Instalar"},
    "installed_badge":    {"zh": "✅ 已安装", "zh-tw": "✅ 已安裝", "en": "✅ Installed", "ja": "✅ 導入済み", "fr": "✅ Installé", "ru": "✅ Установлен", "es": "✅ Instalado"},
    "downloads":          {"zh": "⬇ {n}", "zh-tw": "⬇ {n}", "en": "⬇ {n}", "ja": "⬇ {n}", "fr": "⬇ {n}", "ru": "⬇ {n}", "es": "⬇ {n}"},
    # 状态消息
    "ready":              {"zh": "就绪", "zh-tw": "就緒", "en": "Ready", "ja": "準備完了", "fr": "Prêt", "ru": "Готово", "es": "Listo"},
    "auto_found":         {"zh": "已自动定位: {p}", "zh-tw": "已自動定位: {p}", "en": "Auto-detected: {p}", "ja": "自動検出: {p}", "fr": "Détecté auto. : {p}", "ru": "Авто-обнаружено: {p}", "es": "Detectado auto.: {p}"},
    "not_found":          {"zh": "未自动找到 plugins 目录，请手动浏览选择。",
                           "zh-tw": "未自動找到 plugins 目錄，請手動瀏覽選擇。",
                           "en": "plugins dir not found. Please select manually.",
                           "ja": "pluginsフォルダが見つかりません。手動で選択してください。",
                           "fr": "Dossier plugins introuvable. Sélectionnez manuellement.",
                           "ru": "Папка plugins не найдена. Выберите вручную.",
                           "es": "No se encontró plugins. Seleccione manualmente."},
    "loading_list":       {"zh": "正在获取 REPO MOD 列表（首次需要约10秒）…",
                           "zh-tw": "正在獲取 REPO MOD 列表（首次需要約10秒）…",
                           "en": "Loading MOD list (first time ~10s)…",
                           "ja": "MODリストを取得中（初回は約10秒）…",
                           "fr": "Chargement de la liste MOD (~10s)…",
                           "ru": "Загрузка списка MOD (~10 сек)…",
                           "es": "Cargando lista de MODs (~10s)…"},
    "fetch_fail":         {"zh": "拉取失败: {e}", "zh-tw": "拉取失敗: {e}", "en": "Fetch failed: {e}", "ja": "取得失敗: {e}", "fr": "Échec : {e}", "ru": "Ошибка загрузки: {e}", "es": "Error: {e}"},
    "launch_steam":       {"zh": "正在通过 Steam 启动游戏…", "zh-tw": "正在透過 Steam 啟動遊戲…", "en": "Launching via Steam…", "ja": "Steam経由で起動中…", "fr": "Lancement via Steam…", "ru": "Запуск через Steam…", "es": "Iniciando via Steam…"},
    "launch_exe":         {"zh": "正在启动: {f}", "zh-tw": "正在啟動: {f}", "en": "Launching: {f}", "ja": "起動中: {f}", "fr": "Lancement : {f}", "ru": "Запуск: {f}", "es": "Iniciando: {f}"},
    "no_exe":             {"zh": "游戏目录中没有找到可执行文件。", "zh-tw": "遊戲目錄中沒有找到可執行檔。", "en": "No executable found in game directory.", "ja": "実行ファイルが見つかりません。", "fr": "Aucun exécutable trouvé.", "ru": "Исполняемый файл не найден.", "es": "No se encontró ejecutable."},
    "warn_no_gamedir":    {"zh": "请先设置有效的游戏目录。", "zh-tw": "請先設定有效的遊戲目錄。", "en": "Please set a valid game directory first.", "ja": "有効なゲームフォルダを設定してください。", "fr": "Veuillez d'abord définir un dossier de jeu valide.", "ru": "Сначала укажите папку с игрой.", "es": "Configure primero el directorio del juego."},
    "bepinex_confirm":    {"zh": "将从 Thunderstore 下载 BepInExPack 并安装到游戏目录。\n确定继续？",
                           "zh-tw": "將從 Thunderstore 下載 BepInExPack 並安裝到遊戲目錄。\n確定繼續？",
                           "en": "Download BepInExPack from Thunderstore and install to game directory?\nContinue?",
                           "ja": "ThunderstoreからBepInExPackをダウンロードしてゲームフォルダにインストールします。\n続行しますか？",
                           "fr": "Télécharger BepInExPack depuis Thunderstore et l'installer ?\nContinuer ?",
                           "ru": "Скачать BepInExPack с Thunderstore и установить в папку игры?\nПродолжить?",
                           "es": "¿Descargar BepInExPack desde Thunderstore e instalar?\n¿Continuar?"},
    "bepinex_confirm_title": {"zh": "确认安装", "zh-tw": "確認安裝", "en": "Confirm Install", "ja": "インストール確認", "fr": "Confirmer l'installation", "ru": "Подтвердить установку", "es": "Confirmar instalación"},
    "bepinex_downloading": {"zh": "正在下载 BepInExPack…", "zh-tw": "正在下載 BepInExPack…", "en": "Downloading BepInExPack…", "ja": "BepInExPackをダウンロード中…", "fr": "Téléchargement de BepInExPack…", "ru": "Загрузка BepInExPack…", "es": "Descargando BepInExPack…"},
    "bepinex_ok":         {"zh": "✅ BepInEx 安装完成！请先运行一次游戏再关闭，然后即可安装 MOD。",
                           "zh-tw": "✅ BepInEx 安裝完成！請先運行一次遊戲再關閉，然後即可安裝 MOD。",
                           "en": "✅ BepInEx installed! Run the game once then close it, then install MODs.",
                           "ja": "✅ BepInEx導入完了！ゲームを一度起動して閉じてからMODを導入してください。",
                           "fr": "✅ BepInEx installé ! Lancez le jeu une fois, fermez-le, puis installez les MODs.",
                           "ru": "✅ BepInEx установлен! Запустите игру один раз, закройте, затем устанавливайте MOD.",
                           "es": "✅ BepInEx instalado. Ejecute el juego una vez, ciérrelo y luego instale MODs."},
    "bepinex_fail":       {"zh": "BepInEx 安装失败：{e}", "zh-tw": "BepInEx 安裝失敗：{e}", "en": "BepInEx install failed: {e}", "ja": "BepInEx導入失敗：{e}", "fr": "Échec BepInEx : {e}", "ru": "Ошибка BepInEx: {e}", "es": "Error BepInEx: {e}"},
    "install_fail_title": {"zh": "安装失败", "zh-tw": "安裝失敗", "en": "Install Failed", "ja": "インストール失敗", "fr": "Échec installation", "ru": "Ошибка установки", "es": "Error de instalación"},
    "install_ok":         {"zh": "✅ {name} 安装完成（共安装 {n} 个包）",
                           "zh-tw": "✅ {name} 安裝完成（共安裝 {n} 個套件）",
                           "en": "✅ {name} installed ({n} package(s))",
                           "ja": "✅ {name} 導入完了（{n} 個）",
                           "fr": "✅ {name} installé ({n} paquet(s))",
                           "ru": "✅ {name} установлен ({n} пакет(ов))",
                           "es": "✅ {name} instalado ({n} paquete(s))"},
    "config_loaded":      {"zh": "已从配置加载路径: {p}", "zh-tw": "已從設定載入路徑: {p}", "en": "Loaded path from config: {p}", "ja": "設定からパスを読み込みました: {p}", "fr": "Chemin chargé : {p}", "ru": "Путь загружен: {p}", "es": "Ruta cargada: {p}"},
    # 设置
    "language":           {"zh": "语言:", "zh-tw": "語言:", "en": "Language:", "ja": "言語:", "fr": "Langue :", "ru": "Язык:", "es": "Idioma:"},
    "lang_restart":       {"zh": "语言已保存，重启后生效。", "zh-tw": "語言已儲存，重啟後生效。", "en": "Language saved. Restart to apply.", "ja": "言語を保存しました。再起動後に反映されます。", "fr": "Langue sauvegardée.", "ru": "Язык сохранён.", "es": "Idioma guardado."},
    # 窗口标题
    "window_title":       {"zh": "REPOKit — REPO MOD 管理器", "zh-tw": "REPOKit — REPO MOD 管理器", "en": "REPOKit — REPO MOD Manager", "ja": "REPOKit — REPO MOD マネージャー", "fr": "REPOKit — Gestionnaire de MODs REPO", "ru": "REPOKit — Менеджер MOD REPO", "es": "REPOKit — Gestor de MODs REPO"},
    # 详情弹窗
    "detail_close":       {"zh": "关闭", "zh-tw": "關閉", "en": "Close", "ja": "閉じる", "fr": "Fermer", "ru": "Закрыть", "es": "Cerrar"},
    "detail_deps":        {"zh": "依赖:", "zh-tw": "依賴:", "en": "Dependencies:", "ja": "依存:", "fr": "Dépendances :", "ru": "Зависимости:", "es": "Dependencias:"},
    "detail_version":     {"zh": "版本:", "zh-tw": "版本:", "en": "Version:", "ja": "バージョン:", "fr": "Version :", "ru": "Версия:", "es": "Versión:"},
    "detail_author":      {"zh": "作者:", "zh-tw": "作者:", "en": "Author:", "ja": "作者:", "fr": "Auteur :", "ru": "Автор:", "es": "Autor:"},
    "detail_downloads":   {"zh": "下载:", "zh-tw": "下載:", "en": "Downloads:", "ja": "DL数:", "fr": "Téléch. :", "ru": "Загрузок:", "es": "Descargas:"},
    "detail_translate":   {"zh": "🌐 翻译为中文", "zh-tw": "🌐 翻譯為中文", "en": "🌐 Translate", "ja": "🌐 翻訳", "fr": "🌐 Traduire", "ru": "🌐 Перевести", "es": "🌐 Traducir"},
    "translating":        {"zh": "翻译中…", "zh-tw": "翻譯中…", "en": "Translating…", "ja": "翻訳中…", "fr": "Traduction…", "ru": "Перевод…", "es": "Traduciendo…"},
    "no_desc":            {"zh": "（无简介）", "zh-tw": "（無簡介）", "en": "(No description)", "ja": "（説明なし）", "fr": "(Pas de description)", "ru": "(Нет описания)", "es": "(Sin descripción)"},
    "warn_title":         {"zh": "警告", "zh-tw": "警告", "en": "Warning", "ja": "警告", "fr": "Avertissement", "ru": "Предупреждение", "es": "Advertencia"},
    "confirm_title":      {"zh": "确认", "zh-tw": "確認", "en": "Confirm", "ja": "確認", "fr": "Confirmer", "ru": "Подтвердить", "es": "Confirmar"},
}

_LANG: str = load_config().get("lang", "zh")

def t(key: str, **kwargs) -> str:
    """根据当前语言返回对应文字，支持 {变量} 格式化。"""
    s = _STRINGS.get(key, {}).get(_LANG, _STRINGS.get(key, {}).get("zh", key))
    return s.format(**kwargs) if kwargs else s

# ── 颜色主题 ──────────────────────────────────────────────────────
BG        = "#eef2f8"
PANEL     = "#ffffff"
ACCENT    = "#2563eb"
GREEN     = "#16a34a"
RED       = "#dc2626"
FG        = "#0f172a"
DIM       = "#64748b"
BAR       = "#cbd5e1"
BTN_LIGHT = "#3b82f6"  # 淡蓝按钮色
CARD_BDR  = "#e2e8f0"  # 卡片边框色
HOVER_BG  = "#f1f5fd"  # 卡片悬停色
TAG_BG    = "#dbeafe"  # 标签背景色
TAG_FG    = "#1d4ed8"  # 标签文字色
IMG_PH    = "#dde6f0"  # 图片占位背景色


# ── 本地核心逻辑 ──────────────────────────────────────
_GAME_SUBPATH = os.path.join("steamapps", "common", "REPO", "BepInEx", "plugins")

def _get_steam_library_paths() -> list:
    """读取 Steam libraryfolders.vdf，返回所有 Steam 库根目录列表。"""
    candidates = []
    # 默认 Steam 安装位置
    default_roots = [
        r"C:\Program Files (x86)\Steam",
        r"C:\Program Files\Steam",
    ]
    # 从注册表读取 Steam 实际安装路径（仅 Windows）
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\WOW6432Node\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "InstallPath")
        winreg.CloseKey(key)
        default_roots.insert(0, steam_path)
    except Exception:
        pass

    for steam_root in default_roots:
        vdf_path = os.path.join(steam_root, "steamapps", "libraryfolders.vdf")
        if not os.path.isfile(vdf_path):
            continue
        candidates.append(steam_root)
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if '"path"' in line.lower():
                        parts = line.split('"')
                        # 格式: "path"  "D:\\SteamLibrary"
                        path_val = parts[-2] if len(parts) >= 2 else ""
                        path_val = path_val.replace("\\\\", "\\")
                        if os.path.isdir(path_val):
                            candidates.append(path_val)
        except Exception:
            pass
        break  # 找到第一个有效 vdf 即可
    return candidates


def find_plugins_dir() -> str:
    """在所有 Steam 库路径中查找 REPO 的 plugins 目录。"""
    for lib in _get_steam_library_paths():
        candidate = os.path.join(lib, _GAME_SUBPATH)
        if os.path.isdir(candidate):
            return candidate
    return ""


def list_mods(plugins_dir):
    mods = []
    if not plugins_dir or not os.path.isdir(plugins_dir):
        return mods
    for entry in sorted(os.scandir(plugins_dir), key=lambda e: e.name.lower()):
        if entry.is_dir():
            # 查找文件夹内的 icon.png
            icon_path = os.path.join(entry.path, "icon.png")
            icon = icon_path if os.path.isfile(icon_path) else ""
            mods.append({"name": entry.name, "path": entry.path, "kind": "文件夹", "icon": icon})
        elif entry.is_file() and entry.name.lower().endswith(".dll"):
            mods.append({"name": entry.name, "path": entry.path, "kind": ".dll", "icon": ""})
    return mods


def _extract_zip(zf: zipfile.ZipFile, plugins_dir: str, pkg_name: str = ""):
    """
    从 ZipFile 对象中提取内容到 plugins_dir。
    优先级：
    1. 若 ZIP 内含 BepInEx/plugins/ 路径，只提取该路径下的文件到 plugins_dir。
    2. 否则，将所有内容提取到 plugins_dir/<pkg_name>/ 子目录（用包名创建文件夹）。
    """
    names = zf.namelist()
    prefix = ""
    for n in names:
        if "bepinex/plugins/" in n.lower():
            # 找到标准路径的前缀（大小写不敏感）
            idx = n.lower().index("bepinex/plugins/")
            prefix = n[:idx + len("bepinex/plugins/")]
            break

    if prefix:
        # 只提取 BepInEx/plugins/ 下的内容
        for member in names:
            if not member.startswith(prefix):
                continue
            rel = member[len(prefix):]
            if not rel or rel.endswith("/"):
                continue
            dest = os.path.join(plugins_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as dst:
                dst.write(src.read())
    else:
        # 无标准路径结构，用包名创建文件夹包装
        if pkg_name:
            target = os.path.join(plugins_dir, pkg_name)
        else:
            target = plugins_dir
        os.makedirs(target, exist_ok=True)
        zf.extractall(target)


def install_zip_from_path(zip_path, plugins_dir):
    if not zipfile.is_zipfile(zip_path):
        return False, "所选文件不是有效的 ZIP 压缩包。"
    try:
        pkg_name = os.path.splitext(os.path.basename(zip_path))[0]
        with zipfile.ZipFile(zip_path, "r") as zf:
            _extract_zip(zf, plugins_dir, pkg_name)
        return True, f"已成功解压到:\n{plugins_dir}"
    except Exception as exc:
        return False, f"解压失败: {exc}"


def install_zip_from_bytes(data: bytes, plugins_dir: str, pkg_name: str = ""):
    try:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, "r") as zf:
            _extract_zip(zf, plugins_dir, pkg_name)
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


def _scale_image_to_fill(raw: bytes, target_h: int) -> "tk.PhotoImage":
    """将图片字节缩放到目标高度并返回 PhotoImage，优先用 PIL 精确缩放。"""
    try:
        from PIL import Image, ImageTk
        import io
        pil_img = Image.open(io.BytesIO(raw)).convert("RGBA")
        w, h = pil_img.size
        scale = target_h / h
        new_w = max(1, int(w * scale))
        pil_img = pil_img.resize((new_w, target_h), Image.LANCZOS)
        return ImageTk.PhotoImage(pil_img)
    except ImportError:
        import base64
        b64 = base64.b64encode(raw).decode()
        img = tk.PhotoImage(data=b64)
        iw, ih = img.width(), img.height()
        if ih > 0:
            scale = max(1, ih // target_h)
            img = img.subsample(scale, scale)
        return img


_BATCH_SEP = " |||| "


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


def translate_batch(texts: list) -> list:
    """一次请求批量翻译多条文本，用 |||| 分隔，返回等长结果列表。"""
    if not texts:
        return []
    n = len(texts)
    cleaned = [(t[:200].replace("||||", "") if t and t.strip() else " ") for t in texts]
    joined = _BATCH_SEP.join(cleaned)
    params = urllib.parse.urlencode({"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": joined})
    url = "https://translate.googleapis.com/translate_a/single?" + params
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
        data = json.loads(resp.read().decode())
    translated = "".join(seg[0] for seg in data[0] if seg[0])
    parts = translated.split("||||")
    while len(parts) < n:
        parts.append("")
    return [p.strip() for p in parts[:n]]


_ts_all: list = []   # 全量包缓存


def ts_fetch_all() -> list:
    """一次性担取并缓存全量 REPO 包。"""
    global _ts_all
    req = urllib.request.Request(TS_API, headers={"User-Agent": "REPOKit/1.0"})
    with urllib.request.urlopen(req, timeout=30, context=_SSL_CTX) as resp:
        _ts_all = json.loads(resp.read().decode())
    return _ts_all


# sort key -> (attr_getter, reverse)
_SORT_OPTIONS = [
    ("最后更新", "last_updated"),
    ("最新",     "date_created"),
    ("下载最多", "downloads"),
    ("评分最高", "rating_score"),
]
_SORT_KEYS = {label: key for label, key in _SORT_OPTIONS}


def ts_get_page(keyword: str, page: int, sort: str = "最后更新") -> dict:
    """在本地缓存中搜索、排序并分页。"""
    kw = keyword.strip().lower()
    if kw:
        filtered = [
            p for p in _ts_all
            if kw in p.get("name", "").lower()
            or kw in p.get("owner", "").lower()
            or kw in (p.get("versions") or [{}])[0].get("description", "").lower()
        ]
    else:
        filtered = list(_ts_all)
    sort_key = _SORT_KEYS.get(sort, "last_updated")
    if sort_key in ("downloads",):
        filtered.sort(key=lambda p: (p.get("versions") or [{}])[0].get("downloads", 0), reverse=True)
    elif sort_key == "rating_score":
        filtered.sort(key=lambda p: p.get("rating_score", 0), reverse=True)
    elif sort_key == "date_created":
        filtered.sort(key=lambda p: p.get("date_created", ""), reverse=True)
    else:  # last_updated
        filtered.sort(key=lambda p: p.get("last_updated", ""), reverse=True)
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
    req = urllib.request.Request(download_url, headers={"User-Agent": "REPOKit/1.0"})
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
        import webbrowser

        # ── 底部按钮（先 pack，side=BOTTOM）──────────────
        btn_bar = tk.Frame(self, bg=BAR, pady=8, padx=16)
        btn_bar.pack(fill=tk.X, side=tk.BOTTOM)
        make_btn(btn_bar, "⬇ 下载并安装", self._on_install, GREEN).pack(side=tk.LEFT)
        make_btn(btn_bar, "关闭", self.destroy, BTN_LIGHT).pack(side=tk.RIGHT)
        if pkg.get("website_url"):
            url = pkg["website_url"]
            make_label_btn(btn_bar, "🔗 主页", lambda u=url: webbrowser.open(u),
                           BTN_LIGHT, font_size=9).pack(side=tk.LEFT, padx=(8, 0))
        ts_url = f"https://thunderstore.io/c/repo/p/{pkg.get('author','')}/{pkg.get('name','')}/"
        make_label_btn(btn_bar, "🌩 Thunderstore",
                       lambda u=ts_url: webbrowser.open(u),
                       BTN_LIGHT, font_size=9).pack(side=tk.LEFT, padx=(8, 0))

        # ── 主体可滚动区 ──────────────────────────────────
        body_outer = tk.Frame(self, bg=BG)
        body_outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(body_outer, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(body_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        body = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canvas.bind(seq, lambda e: canvas.yview_scroll(
                -1 if (e.delta > 0 if e.num == "??" else e.num == 4) else 1, "units"))

        # ── 顶部：图标 + 基本信息 ─────────────────────────
        top = tk.Frame(body, bg=BG, pady=12, padx=16)
        top.pack(fill=tk.X)

        self._icon_label = tk.Label(
            top, bg=PANEL, width=self.ICON_SIZE, height=self.ICON_SIZE,
            text="…", fg=DIM, font=("Segoe UI", 8), relief=tk.FLAT,
        )
        self._icon_label.pack(side=tk.LEFT, padx=(0, 16))

        info = tk.Frame(top, bg=BG)
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 名称
        tk.Label(info, text=pkg.get("name", ""), bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold"), anchor=tk.W).pack(fill=tk.X)
        # 作者
        tk.Label(info, text=f"作者：{pkg.get('author', '')}",
                 bg=BG, fg=ACCENT, font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X, pady=(2, 0))
        # 版本
        tk.Label(info, text=f"版本：{pkg.get('version', '')}",
                 bg=BG, fg=DIM, font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X)
        # 下载量 + 评分
        tk.Label(info,
                 text=f"⬇ 下载量：{pkg.get('downloads', 0):,}    👍 评分：{pkg.get('rating_score', 0)}",
                 bg=BG, fg=DIM, font=("Segoe UI", 9), anchor=tk.W).pack(fill=tk.X)

        # 分类标签
        cats = pkg.get("categories", [])
        if cats:
            cat_row = tk.Frame(info, bg=BG)
            cat_row.pack(fill=tk.X, pady=(4, 0))
            for cat in cats:
                tk.Label(cat_row, text=cat, bg=BAR, fg=DIM,
                         font=("Segoe UI", 8), padx=6, pady=2).pack(side=tk.LEFT, padx=(0, 4))

        # 主页链接（可点击）
        if pkg.get("website_url"):
            url = pkg["website_url"]
            lbl = tk.Label(info, text=f"🔗 {url}", bg=BG, fg=ACCENT,
                           font=("Segoe UI", 8), anchor=tk.W, cursor="hand2")
            lbl.pack(fill=tk.X, pady=(4, 0))
            lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        # 分隔线
        tk.Frame(body, bg=BAR, height=1).pack(fill=tk.X, padx=16, pady=(0, 4))

        # ── 简介 ─────────────────────────────────────────
        desc_frame = tk.Frame(body, bg=BG, padx=16, pady=4)
        desc_frame.pack(fill=tk.X)

        desc_header = tk.Frame(desc_frame, bg=BG)
        desc_header.pack(fill=tk.X)
        tk.Label(desc_header, text="📄 简介", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(side=tk.LEFT)
        self._trans_btn = make_label_btn(
            desc_header, "🌐 翻译为中文", self._do_translate, BTN_LIGHT, font_size=8)
        self._trans_btn.pack(side=tk.LEFT, padx=(8, 0))

        self._orig_desc = pkg.get("description", "")
        self._desc_text = tk.Text(
            desc_frame, bg=PANEL, fg=FG, font=("Segoe UI", 9),
            relief=tk.FLAT, wrap=tk.WORD, height=6, bd=4, state=tk.NORMAL,
        )
        self._desc_text.insert(tk.END, self._orig_desc or "（无简介）")
        self._desc_text.config(state=tk.DISABLED)
        self._desc_text.pack(fill=tk.X, pady=(4, 0))

        # ── 版本历史 ──────────────────────────────────────
        raw_pkg = pkg.get("_raw_pkg") or {}
        versions = raw_pkg.get("versions") or []
        if versions:
            tk.Frame(body, bg=BAR, height=1).pack(fill=tk.X, padx=16, pady=(8, 4))
            ver_frame = tk.Frame(body, bg=BG, padx=16, pady=4)
            ver_frame.pack(fill=tk.X)
            tk.Label(ver_frame, text=f"🕓 版本历史（共 {len(versions)} 个版本）",
                     bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(fill=tk.X)
            ver_list = tk.Frame(ver_frame, bg=PANEL, padx=4, pady=4)
            ver_list.pack(fill=tk.X, pady=(4, 0))
            for v in versions:
                vnum  = v.get("version_number", "")
                vdl   = v.get("downloads", 0)
                vdate = v.get("date_created", "")[:10]
                vurl  = v.get("download_url", "")
                is_latest = (v is versions[0])

                row = tk.Frame(ver_list, bg=PANEL, pady=3)
                row.pack(fill=tk.X)

                badge_text = "最新" if is_latest else ""
                if badge_text:
                    tk.Label(row, text=badge_text, bg=GREEN, fg="#fff",
                             font=("Segoe UI", 7, "bold"), padx=4, pady=1).pack(side=tk.LEFT, padx=(0, 6))

                tk.Label(row, text=vnum, bg=PANEL, fg=FG,
                         font=("Segoe UI", 9, "bold"), width=10, anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=vdate, bg=PANEL, fg=DIM,
                         font=("Segoe UI", 8), width=12, anchor=tk.W).pack(side=tk.LEFT)
                tk.Label(row, text=f"⬇ {vdl:,}", bg=PANEL, fg=DIM,
                         font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 8))

                if vurl:
                    lbl = tk.Label(row, text="🔗 下载链接", bg=PANEL, fg=ACCENT,
                                   font=("Segoe UI", 8), cursor="hand2")
                    lbl.pack(side=tk.LEFT, padx=(0, 6))
                    lbl.bind("<Button-1>", lambda e, u=vurl: webbrowser.open(u))

                    make_label_btn(row, "⬇ 安装此版本",
                                   lambda u=vurl: self._install_version(u),
                                   BTN_LIGHT, font_size=8).pack(side=tk.LEFT)

                if v is not versions[-1]:
                    tk.Frame(ver_list, bg=BAR, height=1).pack(fill=tk.X, padx=4)

        # ── 依赖 ──────────────────────────────────────────
        deps = pkg.get("dependencies", [])
        if deps:
            tk.Frame(body, bg=BAR, height=1).pack(fill=tk.X, padx=16, pady=(8, 4))
            dep_frame = tk.Frame(body, bg=BG, padx=16, pady=4)
            dep_frame.pack(fill=tk.X)
            tk.Label(dep_frame, text=f"🔗 依赖（{len(deps)} 个）",
                     bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(fill=tk.X)
            dep_box = tk.Text(
                dep_frame, bg=PANEL, fg=DIM, font=("Segoe UI", 8),
                relief=tk.FLAT, wrap=tk.WORD, height=min(4, len(deps)), bd=4, state=tk.NORMAL,
            )
            dep_box.insert(tk.END, "\n".join(f"  • {d}" for d in deps))
            dep_box.config(state=tk.DISABLED)
            dep_box.pack(fill=tk.X, pady=(4, 0))

        # ── 下载链接 ──────────────────────────────────────
        dl_url = pkg.get("download_url", "")
        if dl_url:
            tk.Frame(body, bg=BAR, height=1).pack(fill=tk.X, padx=16, pady=(8, 4))
            dl_frame = tk.Frame(body, bg=BG, padx=16, pady=4)
            dl_frame.pack(fill=tk.X)
            tk.Label(dl_frame, text="📦 下载链接", bg=BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), anchor=tk.W).pack(fill=tk.X)
            lbl = tk.Label(dl_frame, text=dl_url, bg=BG, fg=ACCENT,
                           font=("Segoe UI", 8), anchor=tk.W, cursor="hand2", wraplength=480)
            lbl.pack(fill=tk.X, pady=(2, 0))
            lbl.bind("<Button-1>", lambda e, u=dl_url: webbrowser.open(u))

        # 弹窗显示后自动翻译简介
        self.after(100, self._do_translate)

    def _on_install(self):
        self.destroy()
        self._install_cb()

    def _install_version(self, download_url: str):
        """安装指定版本（直接用传入的 download_url）。"""
        self.destroy()
        self._install_cb(override_url=download_url)

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
            req  = urllib.request.Request(url, headers={"User-Agent": "REPOKit/1.0"})
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
        self.title(t("window_title"))
        self.geometry("900x580")
        self.minsize(720, 460)
        self.configure(bg=BG)
        self.resizable(True, True)

        cfg = load_config()
        self.plugins_dir = tk.StringVar(value=cfg.get("plugins_dir", "正在扫描…"))
        self.game_dir    = tk.StringVar(value=cfg.get("game_dir", ""))
        self.status_var   = tk.StringVar(value=t("ready"))
        self._mods        = []

        self._build_ui()
        # 若配置中已有路径则跳过自动扫描，否则后台扫描
        if cfg.get("plugins_dir"):
            self._set_status(t("config_loaded", p=cfg['plugins_dir']))
            threading.Thread(target=self._refresh_local, daemon=True).start()
        else:
            threading.Thread(target=self._auto_scan, daemon=True).start()

    # ── UI 总装 ───────────────────────────────────────
    def _build_ui(self):
        # 顶部区：左侧两行路径 + 右侧大号启动按钮
        header = tk.Frame(self, bg=BG, pady=4)
        header.pack(fill=tk.X, padx=12)

        # 右侧：启动游戏大按钮
        launch_btn = tk.Label(
            header, text=t("launch_game"),
            bg=GREEN, fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
            padx=14, pady=8, cursor="hand2",
            justify=tk.CENTER,
        )
        launch_btn.pack(side=tk.RIGHT, padx=(10, 0))
        launch_btn.bind("<Button-1>", lambda e: self._launch_game())
        launch_btn.bind("<Enter>",    lambda e: launch_btn.config(bg=_darken(GREEN)))
        launch_btn.bind("<Leave>",    lambda e: launch_btn.config(bg=GREEN))

        # 左侧：两行路径
        rows = tk.Frame(header, bg=BG)
        rows.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 第一行：游戏根目录
        row1 = tk.Frame(rows, bg=BG, pady=2)
        row1.pack(fill=tk.X)
        tk.Label(row1, text=t("game_dir"), bg=BG, fg=DIM, font=("Segoe UI", 9), width=9, anchor=tk.E).pack(side=tk.LEFT)
        tk.Entry(
            row1, textvariable=self.game_dir,
            bg=PANEL, fg=FG, insertbackground=FG,
            relief=tk.FLAT, font=("Segoe UI", 9), bd=4,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        make_btn(row1, t("browse"), self._browse_game_dir, ACCENT).pack(side=tk.LEFT, padx=(0, 6))
        make_btn(row1, t("install_bepinex"), self._install_bepinex, GREEN).pack(side=tk.LEFT)

        # 第二行：plugins 目录
        row2 = tk.Frame(rows, bg=BG, pady=2)
        row2.pack(fill=tk.X)
        tk.Label(row2, text=t("plugins_dir"), bg=BG, fg=DIM, font=("Segoe UI", 9), width=9, anchor=tk.E).pack(side=tk.LEFT)
        tk.Entry(
            row2, textvariable=self.plugins_dir,
            bg=PANEL, fg=FG, insertbackground=FG,
            relief=tk.FLAT, font=("Segoe UI", 9), bd=4,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        make_btn(row2, t("browse"), self._browse_dir, ACCENT).pack(side=tk.LEFT)

        # 顶部分隔线
        tk.Frame(self, bg=BAR, height=1).pack(fill=tk.X)

        # Notebook & ttk 样式
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=FG,
                        fieldbackground=PANEL, rowheight=48, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=ACCENT,
                        foreground="#ffffff", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#dde6f4", foreground=DIM,
                        padding=[14, 6], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background=BAR,
                        troughcolor=BG, borderwidth=0, arrowsize=13)
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                        foreground=FG, selectbackground=ACCENT, selectforeground="#fff")

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 0))

        tab_local  = tk.Frame(nb, bg=BG)
        tab_online = tk.Frame(nb, bg=BG)
        nb.add(tab_local,  text=t("tab_local"))
        nb.add(tab_online, text=t("tab_online"))

        # 语言切换下拉框：叠加在 Notebook Tab 行右侧（place 定位）
        _LANG_DISPLAY = {"zh": "中文", "zh-tw": "繁體中文", "en": "English", "ja": "日本語", "fr": "Français", "ru": "Русский", "es": "Español"}
        _LANG_CODE    = {v: k for k, v in _LANG_DISPLAY.items()}
        self._lang_display_map = _LANG_CODE
        self._lang_var = tk.StringVar(value=_LANG_DISPLAY.get(_LANG, "中文"))
        lang_cb = ttk.Combobox(
            nb, textvariable=self._lang_var,
            values=list(_LANG_DISPLAY.values()), state="readonly", width=9, font=("Segoe UI", 8),
        )
        lang_cb.place(relx=1.0, rely=0, anchor="ne", y=4)
        lang_cb.bind("<<ComboboxSelected>>", lambda _: self._switch_lang())

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
        make_btn(btn_bar, t("import_zip"), self._install_local_zip, GREEN).pack(side=tk.LEFT, padx=(0, 8))
        make_btn(btn_bar, t("refresh"),     self._refresh_local,     ACCENT).pack(side=tk.LEFT)

        # 卡片滚动区
        grid_outer = tk.Frame(parent, bg=BG)
        grid_outer.pack(fill=tk.BOTH, expand=True)
        self._local_canvas = tk.Canvas(grid_outer, bg=BG, highlightthickness=0)
        self._local_canvas.pack(fill=tk.BOTH, expand=True)
        self._local_card_frame = tk.Frame(self._local_canvas, bg=BG)
        self._local_canvas_win = self._local_canvas.create_window((0, 0), window=self._local_card_frame, anchor="nw")
        self._local_card_frame.bind("<Configure>", lambda e: self._local_canvas.configure(
            scrollregion=self._local_canvas.bbox("all")))
        self._local_canvas.bind("<Configure>", lambda e: self._local_canvas.itemconfig(
            self._local_canvas_win, width=e.width))
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._local_canvas.bind(seq, self._on_mousewheel)
            self._local_card_frame.bind(seq, self._on_mousewheel)
        self._local_img_refs: dict = {}  # path -> PhotoImage
        self._local_selected: dict = {}  # 当前选中的 mod {name, kind, path}

    # ── 标签页 2：在线 Thunderstore ───────────────────
    def _build_online_tab(self, parent):
        # 搜索栏
        search_bar = tk.Frame(parent, bg=BG, pady=4)
        search_bar.pack(fill=tk.X)
        tk.Label(search_bar, text=t("search"), bg=BG, fg=DIM, font=("Segoe UI", 9)).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_bar, textvariable=self._search_var,
            bg=PANEL, fg=FG, insertbackground=FG,
            relief=tk.FLAT, font=("Segoe UI", 10), bd=4, width=28,
        )
        search_entry.pack(side=tk.LEFT, padx=(6, 6))
        search_entry.bind("<Return>", lambda _: self._ts_search_start())
        make_btn(search_bar, t("search_btn"),   self._ts_search_start,   ACCENT).pack(side=tk.LEFT, padx=(0, 6))
        make_btn(search_bar, t("chinese_mods"),  self._ts_filter_chinese, BTN_LIGHT).pack(side=tk.LEFT, padx=(0, 6))
        # 排序下拉框
        self._sort_var = tk.StringVar(value="评分最高")
        sort_cb = ttk.Combobox(
            search_bar, textvariable=self._sort_var,
            values=[label for label, _ in _SORT_OPTIONS],
            state="readonly", width=10, font=("Segoe UI", 9),
        )
        sort_cb.pack(side=tk.LEFT, padx=(0, 6))
        sort_cb.bind("<<ComboboxSelected>>", lambda _: self._ts_sort_changed())
        make_btn(search_bar, t("prev_page"), self._ts_prev_page, BTN_LIGHT).pack(side=tk.LEFT, padx=(0, 2))
        self._page_label = tk.Label(search_bar, text=t("page_label", p=1), bg=BG, fg=DIM, font=("Segoe UI", 9))
        self._page_label.pack(side=tk.LEFT, padx=4)
        make_btn(search_bar, t("next_page"), self._ts_next_page, BTN_LIGHT).pack(side=tk.LEFT, padx=(2, 0))
        self._trans_list_btn = make_btn(search_bar, t("translate_btn"), self._translate_list, BTN_LIGHT)
        self._trans_list_btn.pack(side=tk.LEFT, padx=(6, 0))

        # 卡片滚动区
        grid_outer = tk.Frame(parent, bg=BG)
        grid_outer.pack(fill=tk.BOTH, expand=True)
        self._card_canvas = tk.Canvas(grid_outer, bg=BG, highlightthickness=0)
        self._card_canvas.pack(fill=tk.BOTH, expand=True)
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
        self._render_gen: int = 0             # 渲染代次，用于丢弃过期翻译回调

    # ── 本地标签页逻辑 ────────────────────────────────
    def _auto_scan(self):
        found = find_plugins_dir()
        if found:
            self.plugins_dir.set(found)
            save_config({"plugins_dir": found})
            # 自动推断游戏根目录：plugins → BepInEx → 游戏根
            game_root = os.path.dirname(os.path.dirname(found))
            if os.path.isdir(game_root) and not self.game_dir.get().strip():
                self.game_dir.set(game_root)
                save_config({"game_dir": game_root})
            self._set_status(t("auto_found", p=found))
        else:
            self.plugins_dir.set("")
            self._set_status(t("not_found"))
        self._refresh_local()

    def _launch_game(self):
        game_dir = self.game_dir.get().strip()
        if not game_dir or not os.path.isdir(game_dir):
            messagebox.showwarning(t("warn_title"), t("warn_no_gamedir"))
            return
        # 优先通过 Steam 协议启动（Steam AppID: 3241660 for R.E.P.O.）
        try:
            import subprocess
            subprocess.Popen(["cmd", "/c", "start", "steam://rungameid/3241660"])
            self._set_status(t("launch_steam"))
            return
        except Exception:
            pass
        # 回退：直接找 .exe 启动
        exes = [f for f in os.listdir(game_dir) if f.lower().endswith(".exe")
                and "uninstall" not in f.lower() and "crash" not in f.lower()]
        if not exes:
            messagebox.showwarning(t("warn_title"), t("no_exe"))
            return
        import subprocess
        subprocess.Popen([os.path.join(game_dir, exes[0])], cwd=game_dir)
        self._set_status(t("launch_exe", f=exes[0]))

    def _switch_lang(self):
        global _LANG
        _LANG = self._lang_display_map.get(self._lang_var.get(), "zh")
        save_config({"lang": _LANG})
        # 销毁所有子 widget 并重建 UI
        for w in self.winfo_children():
            w.destroy()
        self.title(t("window_title"))
        self._build_ui()
        self._refresh_local()

    def _browse_game_dir(self):
        d = filedialog.askdirectory(title="选择游戏根目录（含 .exe 的那一层）")
        if d:
            path = d.replace("/", "\\")
            self.game_dir.set(path)
            save_config({"game_dir": path})

    def _install_bepinex(self):
        game_dir = self.game_dir.get().strip()
        if not game_dir or not os.path.isdir(game_dir):
            messagebox.showwarning(t("warn_title"), t("warn_no_gamedir"))
            return
        if not messagebox.askyesno(t("bepinex_confirm_title"), t("bepinex_confirm")):
            return
        self._set_status(t("bepinex_downloading"))
        threading.Thread(target=self._bepinex_install_worker,
                         args=(game_dir,), daemon=True).start()

    def _bepinex_install_worker(self, game_dir: str):
        BEPINEX_URL = "https://thunderstore.io/api/experimental/package/BepInEx/BepInExPack/"
        try:
            req = urllib.request.Request(BEPINEX_URL,
                                         headers={"User-Agent": "REPOKit/1.0"})
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                pkg = json.loads(resp.read().decode())
            dl_url = (pkg.get("latest") or {}).get("download_url", "")
            if not dl_url:
                raise ValueError("未找到下载链接")
            data = ts_download(dl_url)
            # BepInExPack ZIP 结构：BepInExPack/<BepInEx/...> + 其他文件
            # 找到顶层唯一文件夹作为前缀，将其内容直接解压到游戏根目录
            buf = io.BytesIO(data)
            with zipfile.ZipFile(buf, "r") as zf:
                names = zf.namelist()
                # 找顶层文件夹前缀（第一个含 / 的路径段）
                top_dirs = {n.split("/")[0] for n in names if "/" in n}
                prefix = (top_dirs.pop() + "/") if len(top_dirs) == 1 else ""
                for member in names:
                    rel = member[len(prefix):] if prefix and member.startswith(prefix) else member
                    if not rel or rel.endswith("/"):
                        continue
                    dest = os.path.join(game_dir, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        dst.write(src.read())
            self.after(0, lambda: self._set_status(t("bepinex_ok")))
        except Exception as exc:
            self.after(0, lambda e=str(exc): messagebox.showerror(t("install_fail_title"), t("bepinex_fail", e=e)))
            self.after(0, lambda: self._set_status(t("bepinex_fail", e="")))

    def _browse_dir(self):
        d = filedialog.askdirectory(title="选择 BepInEx/plugins 目录")
        if d:
            path = d.replace("/", "\\")
            self.plugins_dir.set(path)
            save_config({"plugins_dir": path})
            self._refresh_local()

    def _refresh_local(self):
        for w in self._local_card_frame.winfo_children():
            w.destroy()
        self._local_img_refs.clear()
        self._local_selected = {}
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            self._set_status("plugins 目录无效，请重新选择。")
            return
        self._mods = list_mods(d)
        self._installed_names = {
            os.path.splitext(m["name"])[0].lower() for m in self._mods
        }
        COLS = 4
        LOCAL_CARD_W = 200
        LOCAL_IMG_H  = 100
        for idx, mod in enumerate(self._mods):
            name = mod["name"]
            kind = mod["kind"]
            path = mod["path"]
            row, col = divmod(idx, COLS)

            card = tk.Frame(self._local_card_frame, bg=PANEL, bd=0,
                            highlightthickness=1, highlightbackground=CARD_BDR,
                            width=LOCAL_CARD_W, cursor="hand2")
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self._local_card_frame.grid_columnconfigure(col, weight=1)

            def _lc_enter(e, c=card): c.config(highlightbackground=ACCENT)
            def _lc_leave(e, c=card): c.config(highlightbackground=CARD_BDR)
            card.bind("<Enter>", _lc_enter)
            card.bind("<Leave>", _lc_leave)

            # 图片区
            img_frame = tk.Frame(card, bg=IMG_PH, height=LOCAL_IMG_H, width=LOCAL_CARD_W)
            img_frame.pack(fill=tk.X)
            img_frame.pack_propagate(False)
            img_lbl = tk.Label(img_frame, bg=IMG_PH, text="", cursor="hand2")
            img_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

            # 文字区
            info = tk.Frame(card, bg=PANEL, padx=10, pady=8)
            info.pack(fill=tk.BOTH, expand=True)
            tk.Label(info, text=name, bg=PANEL, fg=FG,
                     font=("Segoe UI", 9, "bold"),
                     anchor=tk.W, wraplength=LOCAL_CARD_W - 20, justify=tk.LEFT
                     ).pack(fill=tk.X)
            tk.Label(info, text=kind, bg=PANEL, fg=DIM,
                     font=("Segoe UI", 8), anchor=tk.W).pack(fill=tk.X, pady=(1, 0))
            tk.Frame(info, bg=CARD_BDR, height=1).pack(fill=tk.X, pady=(5, 4))

            btn_row = tk.Frame(info, bg=PANEL)
            btn_row.pack(fill=tk.X)
            make_label_btn(btn_row, "🗑 删除",
                           lambda p=path, n=name: self._delete_mod_card(n, p),
                           RED).pack(side=tk.LEFT)

            # 绑定滚轮
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                for w in (card, img_frame, img_lbl, info, btn_row):
                    w.bind(seq, self._on_mousewheel)

            # 异步加载图标
            icon_src = mod.get("icon", "")
            if not icon_src:
                mod_name_lc = os.path.splitext(name)[0].lower()
                icon_src = next(
                    (((p.get("versions") or [{}])[0].get("icon", ""))
                     for p in _ts_all if p.get("name", "").lower() == mod_name_lc),
                    ""
                )
            if icon_src:
                threading.Thread(
                    target=self._load_local_icon_card_worker,
                    args=(path, icon_src, img_lbl, img_frame, LOCAL_IMG_H),
                    daemon=True,
                ).start()
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

    def _delete_mod_card(self, name: str, path: str):
        if not messagebox.askyesno(
            "确认删除",
            f"确定要删除以下 MOD 吗？\n\n名称：{name}\n路径：{path}\n\n此操作不可恢复！",
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
        # 根据事件来源决定滚动哪个 Canvas
        w = event.widget
        canvas = None
        while w:
            if w is self._local_canvas:
                canvas = self._local_canvas
                break
            if w is self._card_canvas:
                canvas = self._card_canvas
                break
            try:
                w = w.master
            except Exception:
                break
        if canvas is None:
            canvas = self._card_canvas
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(int(-1 * (event.delta / 4)), "units")

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
        ModDetailDialog(self, pkg, install_cb=lambda override_url=None: self._ts_do_install(pkg, override_url=override_url))

    def _ts_sort_changed(self):
        self._ts_page = 1
        if self._ts_fetched:
            self._ts_render_page()

    def _ts_filter_chinese(self):
        self._search_var.set("chinese")
        self._ts_page = 1
        if not self._ts_fetched:
            self._set_status("正在获取 REPO MOD 列表（首次需要约10秒）…")
            threading.Thread(target=self._ts_fetch_worker, daemon=True).start()
        else:
            self._ts_render_page()

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
        self._render_gen += 1          # 翻页/刷新时代次递增，令旧翻译回调失效
        gen = self._render_gen
        kw   = self._search_var.get()
        sort = self._sort_var.get()
        data = ts_get_page(kw, self._ts_page, sort)
        self._ts_page        = data["page"]
        self._ts_total_pages = data["total_pages"]
        self._ts_render(data)
        if self._ts_translated:
            self._set_trans_list_btn("🔄 原文", self._restore_list)
            untranslated = [
                (p["name"], p.get("description", ""), p.get("_raw_pkg"))
                for p in self._ts_results
                if p.get("_raw_pkg") is not None and "zh_name" not in p["_raw_pkg"]
            ]
            if untranslated:
                self._set_trans_list_btn("翻译中…", None)
                threading.Thread(
                    target=self._translate_list_worker,
                    args=(untranslated, gen),
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
                            highlightthickness=1, highlightbackground=CARD_BDR,
                            width=CARD_W, cursor="hand2")
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self._card_frame.grid_columnconfigure(col, weight=1)

            # 悬停高亮
            def _on_enter(e, c=card): c.config(highlightbackground=ACCENT)
            def _on_leave(e, c=card): c.config(highlightbackground=CARD_BDR)
            card.bind("<Enter>", _on_enter)
            card.bind("<Leave>", _on_leave)

            # 图片区
            img_frame = tk.Frame(card, bg=IMG_PH, height=IMG_H, width=CARD_W)
            img_frame.pack(fill=tk.X)
            img_frame.pack_propagate(False)
            img_lbl = tk.Label(img_frame, bg=IMG_PH, text="", cursor="hand2")
            img_lbl.place(relx=0, rely=0, relwidth=1, relheight=1)
            # 已安装徽标
            if name.lower() in self._installed_names or \
               f"{author.lower()}-{name.lower()}" in self._installed_names:
                tk.Label(img_frame, text=" ✓ 已安装 ",
                         bg=GREEN, fg="#ffffff",
                         font=("Segoe UI", 8, "bold"), pady=3,
                         ).place(relx=0, rely=0, anchor="nw")

            # 版本角标
            if version:
                tk.Label(img_frame, text=f" v{version} ",
                         bg="#334155", fg="#ffffff",
                         font=("Segoe UI", 7), pady=2,
                         ).place(relx=1.0, rely=1.0, anchor="se")

            # 文字区
            info = tk.Frame(card, bg=PANEL, padx=10, pady=8)
            info.pack(fill=tk.BOTH, expand=True)

            name_lbl = tk.Label(info, text=disp_name, bg=PANEL, fg=FG,
                                font=("Segoe UI", 10, "bold"),
                                anchor=tk.W, wraplength=CARD_W - 22, justify=tk.LEFT)
            name_lbl.pack(fill=tk.X)

            author_lbl = tk.Label(info, text=f"by {author}", bg=PANEL, fg=ACCENT,
                     font=("Segoe UI", 8), anchor=tk.W)
            author_lbl.pack(fill=tk.X, pady=(1, 0))

            tk.Frame(info, bg=CARD_BDR, height=1).pack(fill=tk.X, pady=(5, 4))

            desc_lbl = tk.Label(info, text=disp_desc[:100] + ("…" if len(disp_desc) > 100 else ""),
                                bg=PANEL, fg=DIM,
                                font=("Segoe UI", 8), anchor=tk.W,
                                wraplength=CARD_W - 22, justify=tk.LEFT)
            desc_lbl.pack(fill=tk.X)

            if cats:
                tag_row = tk.Frame(info, bg=PANEL)
                tag_row.pack(fill=tk.X, pady=(5, 0))
                for cat in cats[:3]:
                    tk.Label(tag_row, text=cat, bg=TAG_BG, fg=TAG_FG,
                             font=("Segoe UI", 7, "bold"), padx=5, pady=2
                             ).pack(side=tk.LEFT, padx=(0, 4))

            meta_row = tk.Frame(info, bg=PANEL)
            meta_row.pack(fill=tk.X, pady=(5, 0))
            tk.Label(meta_row, text=f"⬇ {dl_cnt:,}", bg=PANEL, fg=DIM,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)
            tk.Label(meta_row, text=f"  ⭐ {rating}", bg=PANEL, fg=DIM,
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)

            btn_row = tk.Frame(info, bg=PANEL)
            btn_row.pack(fill=tk.X, pady=(6, 0))
            make_label_btn(btn_row, "⬇ 安装",
                           lambda p=_pkg: self._ts_do_install(p),
                           GREEN).pack(side=tk.LEFT)
            make_label_btn(btn_row, "详情 ›",
                           lambda p=_pkg: self._ts_show_detail(p),
                           BTN_LIGHT).pack(side=tk.LEFT, padx=(6, 0))

            for w in (card, img_frame, img_lbl, info, name_lbl, author_lbl, desc_lbl):
                w.bind("<Button-1>", lambda e, p=_pkg: self._ts_show_detail(p))
                w.bind("<Enter>", _on_enter)
                w.bind("<Leave>", _on_leave)

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
        import base64, io
        global _icon_cache
        cache_key = (url, img_h)
        if cache_key not in _icon_cache:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "REPOKit/1.0"})
                with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as resp:
                    raw = resp.read()
                img = _scale_image_to_fill(raw, img_h)
                _icon_cache[cache_key] = img
            except Exception:
                return
        img = _icon_cache[cache_key]
        self._card_img_refs.append(img)
        self.after(0, lambda: self._set_card_image(lbl, frame, img))

    def _set_card_image(self, lbl, frame, img):
        try:
            lbl.config(image=img)
            frame.config(bg=PANEL)
        except Exception:
            pass

    def _load_local_icon_card_worker(self, path: str, src: str, lbl, frame, img_h: int):
        cache_key = (src, img_h)
        if cache_key not in _icon_cache:
            try:
                if src.startswith("http"):
                    req = urllib.request.Request(src, headers={"User-Agent": "REPOKit/1.0"})
                    with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                        raw = resp.read()
                else:
                    with open(src, "rb") as f:
                        raw = f.read()
                img = _scale_image_to_fill(raw, img_h)
                _icon_cache[cache_key] = img
            except Exception:
                return
        img = _icon_cache[cache_key]
        self._local_img_refs[path] = img
        self.after(0, lambda: self._set_card_image(lbl, frame, img))

    def _load_local_icon_worker(self, iid: str, src: str):
        ICON_SIZE = 40
        if src not in _icon_cache:
            try:
                if src.startswith("http"):
                    req = urllib.request.Request(src, headers={"User-Agent": "REPOKit/1.0"})
                    with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                        raw = resp.read()
                else:
                    with open(src, "rb") as f:
                        raw = f.read()
                import base64
                b64 = base64.b64encode(raw).decode()
                img = tk.PhotoImage(data=b64)
                iw, ih = img.width(), img.height()
                scale = max(1, max(iw, ih) // ICON_SIZE)
                img = img.subsample(scale, scale)
                _icon_cache[src] = img
            except Exception:
                return
        img = _icon_cache[src]
        def _apply():
            try:
                self._local_img_refs[iid] = img
                self.local_tree.item(iid, image=img)
            except Exception:
                pass
        self.after(0, _apply)

    def _set_trans_list_btn(self, text: str, cmd):
        self._trans_list_btn.config(text=text)
        self._trans_list_btn.unbind("<Button-1>")
        if cmd:
            self._trans_list_btn.bind("<Button-1>", lambda e: cmd())

    def _translate_list(self):
        if not self._ts_results:
            return
        self._render_gen += 1
        gen = self._render_gen
        self._set_trans_list_btn("翻译中…", None)
        self._set_status("正在翻译当前页，请稍候…")
        # 同时捕获 raw_pkg 引用，不依赖回调时的 _ts_results 索引
        items = [
            (p["name"], p.get("description", ""), p.get("_raw_pkg"))
            for p in self._ts_results
        ]
        threading.Thread(target=self._translate_list_worker, args=(items, gen), daemon=True).start()

    def _translate_list_worker(self, items: list, gen: int):
        names    = [n for n, _, _ in items]
        descs    = [d for _, d, _ in items]
        raw_pkgs = [r for _, _, r in items]
        try:
            zh_names = translate_batch(names)
        except Exception:
            zh_names = names
        try:
            zh_descs = translate_batch(descs)
        except Exception:
            zh_descs = descs
        results = list(zip(zh_names, zh_descs, raw_pkgs))
        self.after(0, lambda: self._apply_list_translation(results, gen))

    def _apply_list_translation(self, results: list, gen: int):
        # 无论是否过期，都将翻译结果写入 _ts_all 缓存（raw_pkg 引用已在启动时捕获）
        for zh_name, zh_desc, raw_pkg in results:
            if raw_pkg is not None:
                raw_pkg["zh_name"] = zh_name
                raw_pkg["zh_desc"] = zh_desc
        # 代次不匹配说明已翻页，只写缓存不重新渲染
        if gen != self._render_gen:
            return
        self._ts_translated = True
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

    def _collect_missing_deps(self, pkg: dict, visited: set) -> list:
        """递归收集所有缺失的前置依赖，返回列表顺序为安装顺序。"""
        result = []
        for dep_str in pkg.get("dependencies", []):
            parts = dep_str.split("-")
            if len(parts) < 2:
                continue
            dep_name = parts[1].lower()
            if dep_name in visited or dep_name in self._installed_names:
                continue
            visited.add(dep_name)
            # 在 _ts_all 中查找对应包
            dep_pkg_raw = next(
                (p for p in _ts_all if p.get("name", "").lower() == dep_name),
                None
            )
            if dep_pkg_raw is None:
                continue
            versions = dep_pkg_raw.get("versions") or []
            latest   = versions[0] if versions else {}
            dep_pkg  = {
                "name":         dep_pkg_raw.get("name", ""),
                "author":       dep_pkg_raw.get("owner", ""),
                "download_url": latest.get("download_url", ""),
                "dependencies": latest.get("dependencies", []),
            }
            # 先递归收集它的前置
            result.extend(self._collect_missing_deps(dep_pkg, visited))
            result.append(dep_pkg)
        return result

    def _ts_do_install(self, pkg: dict, override_url: str = None):
        d = self.plugins_dir.get().strip()
        if not d or not os.path.isdir(d):
            messagebox.showwarning("警告", "请先设置有效的 plugins 目录。")
            return
        name   = pkg["name"]
        dl_url = override_url or pkg.get("download_url", "")
        if not dl_url:
            messagebox.showerror("错误", "该 MOD 无可用下载链接。")
            return
        # 如果是指定历史版本，直接安装该版本（不拉取前置）
        if override_url:
            ver_label = override_url.split("/")[-2] if override_url else ""
            msg = f"确定要安装指定版本吗？\n\n{pkg['author']}-{name} {ver_label}"
            if not messagebox.askyesno("确认安装", msg):
                return
            install_queue = [{**pkg, "download_url": override_url}]
        else:
            # 收集缺失前置
            missing_deps = self._collect_missing_deps(pkg, {name.lower()})
            if missing_deps:
                dep_names = "\n".join(f"  • {p['author']}-{p['name']}" for p in missing_deps)
                msg = (
                    f"确定安装以下 MOD 吗？\n\n"
                    f"{pkg['author']}-{name}\n\n"
                    f"将同时安装以下 {len(missing_deps)} 个缺失前置：\n{dep_names}"
                )
            else:
                msg = f"确定要下载并安装以下 MOD 吗？\n\n{pkg['author']}-{name}"
            if not messagebox.askyesno("确认安装", msg):
                return
            install_queue = missing_deps + [pkg]
        dlg = DownloadDialog(self, title=f"安装 {name}")
        self._set_status(f"正在下载 {name}…")
        threading.Thread(
            target=self._ts_download_worker,
            args=(install_queue, d, dlg),
            daemon=True,
        ).start()

    def _ts_download_worker(self, install_queue: list, plugins_dir: str, dlg: "DownloadDialog"):
        total_count = len(install_queue)
        for idx, pkg in enumerate(install_queue):
            name   = pkg["name"]
            dl_url = pkg.get("download_url", "")
            if not dl_url:
                continue
            self.after(0, lambda n=name, i=idx: (
                dlg._label.config(text=f"({i+1}/{total_count}) 下载 {n}…"),
                self._set_status(f"正在下载 {n}…"),
            ))
            def on_progress(received, total):
                self.after(0, lambda: dlg.update_progress(received, total))
            try:
                data = ts_download(dl_url, progress_cb=on_progress)
            except Exception as exc:
                self.after(0, dlg.destroy)
                self.after(0, lambda e=str(exc): messagebox.showerror("下载失败", e))
                self.after(0, lambda: self._set_status("下载失败。"))
                return
            self.after(0, dlg.set_installing)
            pkg_name = f"{pkg.get('author', '')}-{name}"
            ok, msg = install_zip_from_bytes(data, plugins_dir, pkg_name)
            if not ok:
                self.after(0, dlg.destroy)
                self.after(0, lambda m=msg: messagebox.showerror("安装失败", m))
                self.after(0, lambda: self._set_status("安装失败。"))
                return
        main_name = install_queue[-1]["name"]
        self.after(0, dlg.destroy)
        self.after(0, lambda: self._set_status(f"✅ {main_name} 安装完成（共安装 {total_count} 个包）"))
        self.after(0, self._refresh_local)
        if self._ts_fetched:
            self.after(0, self._ts_render_page)

    def _set_status(self, text: str):
        self.status_var.set(text)


# ── 入口 ──────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
