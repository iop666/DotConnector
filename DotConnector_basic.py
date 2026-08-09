#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DotConnector 鼠标连点器 (Python / tkinter)
===========================================
- 通过 ctypes 直接调用 Win32 mouse_event 模拟点击，不依赖 pynput
- 支持 左键 / 中键 / 右键
- 三种模式：固定间隔 / 随机间隔 / 长按模式
- 全局热键 Ctrl+F9 启动/停止、Ctrl+Alt+F10 强制退出（窗口不在前台也生效，
  系统托盘图标同步显示 运行中/已停止 状态）
- 点击位置：跟随鼠标 或 锁定固定坐标（支持手动输入 / 捕获当前坐标 / ±5px 随机偏移）
- 停止条件：点击次数 / 倒计时 / 运行到指定时间
- 窗口检测：按标题或进程名，目标窗口失焦自动暂停，切回自动恢复
- 历史累计次数 + 置顶实时计数小窗
- 100% / 150% / 200% 三种缩放
- 退出时保存 config.ini 到本目录，下次启动自动恢复
"""

import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time
import random
import queue
import struct
import tempfile
import configparser

import tkinter as tk
import tkinter.scrolledtext as scrolledtext
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from tkinter import ttk
from tkinter import font as tkfont

APP_NAME = 'DotConnector 连点器'
VERSION = '1.0.0'


def app_base_dir():
    """程序数据目录（config.ini / logs 写入位置）：
    - 打包为 exe 后 = exe 所在目录（可写、重启持久）
    - 源码运行时 = 项目目录
    注意：PyInstaller onefile 下 __file__ 指向临时 _MEIPASS 目录，配置写那里退出即丢。"""
    if getattr(sys, 'frozen', False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        # 若 exe 所在目录不可写（如 Program Files），退回用户目录
        try:
            probe = os.path.join(d, '.dc_probe')
            with open(probe, 'w'):
                pass
            os.remove(probe)
            return d
        except Exception:
            return os.path.expanduser('~')
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = app_base_dir()
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')


def resource_path(name):
    """定位资源文件：兼容 PyInstaller 打包后 _MEIPASS 路径（只读资源如图标）。"""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

# ---------------------------------------------------------------------------
# 基础 Win32 声明
# ---------------------------------------------------------------------------
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
BUTTON_FLAGS = {
    0: (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),      # 左键
    1: (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),  # 中键
    2: (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),    # 右键
}

WM_APP = 0x8000
WM_NOTIFYICON = WM_APP + 1
WM_HOTKEY = 0x0312
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203
WM_QUIT = 0x0012
HWND_MESSAGE = wt.HWND(-3)
GWL_STYLE = -16
WS_MAXIMIZEBOX = 0x00010000
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
VK_F9 = 0x78
VK_F8 = 0x77
VK_F10 = 0x79
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# ---------------------------------------------------------------------------
# 热键配置与映射
# ---------------------------------------------------------------------------
VK_NAMES_EXTRA = {
    0x26: 'Up', 0x28: 'Down', 0x25: 'Left', 0x27: 'Right',
    0x24: 'Home', 0x23: 'End', 0x21: 'PageUp', 0x22: 'PageDown',
    0x2D: 'Insert', 0x2E: 'Delete', 0x20: 'Space',
    0x0D: 'Enter', 0x08: 'Backspace', 0x09: 'Tab', 0x1B: 'Esc',
}
_FKEYS = {}
for _i in range(1, 25):
    _FKEYS['f%d' % _i] = 0x70 + (_i - 1)


def keysym_to_vk(ks):
    """把 Tk keysym 转成 Win32 虚拟键码；不支持的返回 None。"""
    ks = ks.lower()
    if len(ks) == 1 and ks.isalpha():
        return ord(ks.upper())
    if len(ks) == 1 and ks.isdigit():
        return ord(ks)
    _map = {
        'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
        'home': 0x24, 'end': 0x23, 'prior': 0x21, 'next': 0x22,
        'insert': 0x2D, 'delete': 0x2E, 'space': 0x20,
        'return': 0x0D, 'backspace': 0x08, 'tab': 0x09, 'escape': 0x1B,
    }
    return _FKEYS.get(ks, _map.get(ks))


def vk_to_name(vk):
    if 0x70 <= vk <= 0x87:
        return 'F%d' % (vk - 0x70 + 1)
    if 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x41 <= vk <= 0x5A:
        return chr(vk)
    return VK_NAMES_EXTRA.get(vk, 'VK%X' % vk)


def mod_to_names(mods):
    parts = []
    if mods & MOD_CONTROL:
        parts.append('Ctrl')
    if mods & MOD_ALT:
        parts.append('Alt')
    if mods & MOD_SHIFT:
        parts.append('Shift')
    return parts


def fmt_hotkey(mods, vk):
    return '+'.join(mod_to_names(mods) + [vk_to_name(vk)])


# 默认热键
HK_DEFAULTS = {
    'toggle':  [MOD_CONTROL, VK_F9],
    'force':   [MOD_CONTROL | MOD_ALT, VK_F10],
    'capture': [MOD_CONTROL | MOD_SHIFT, VK_F8],
}
HK_LABELS = {'toggle': '启动/停止', 'force': '强制退出', 'capture': '捕获坐标'}

# ---------------------------------------------------------------------------
# 界面主题色板（美化版）
# ---------------------------------------------------------------------------
CLR_BG = '#eef1f7'            # 窗口背景：浅灰蓝
CLR_CARD = '#f7f9fd'          # 卡片背景：极浅蓝灰（与内部 Label 同色，融为一体）
CLR_BORDER = '#d5dcea'        # 卡片边框
CLR_PRIMARY = '#3b6ef6'       # 主色：靛蓝
CLR_PRIMARY_DARK = '#2a55d8'  # 主色按下态
CLR_PRIMARY_BG = '#e8effe'    # 主色浅底（强调提示）
CLR_TEXT = '#262e40'          # 主文字
CLR_SUB = '#7a8499'           # 次要文字
CLR_OK = '#1faf58'            # 运行绿
CLR_WARN = '#c47a00'          # 暂停橙
CLR_STOP = '#dc3545'          # 停止红
FONT_FAMILY = 'Microsoft YaHei UI'
FONT_EN = 'Segoe UI'
FONT_MONO = 'Consolas'


def _setup_api():
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wt.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
    user32.GetCursorPos.restype = wt.BOOL
    user32.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_ssize_t]
    user32.mouse_event.restype = None
    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user32.GetWindowThreadProcessId.restype = wt.DWORD
    user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetForegroundWindow.restype = wt.BOOL
    user32.GetDpiForSystem.restype = ctypes.c_uint
    user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
    user32.LoadImageW.restype = wt.HANDLE
    shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wt.BOOL
    user32.EnumWindows.argtypes = [ENUMWNDPROC, wt.LPARAM]
    user32.EnumWindows.restype = wt.BOOL
    user32.IsWindowVisible.argtypes = [wt.HWND]
    user32.IsWindowVisible.restype = wt.BOOL
    user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    kernel32.GetCurrentProcessId.restype = wt.DWORD
    user32.CreatePopupMenu.restype = wt.HMENU
    user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_ssize_t, wt.LPCWSTR]
    user32.AppendMenuW.restype = wt.BOOL
    user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wt.HWND, ctypes.c_void_p]
    user32.TrackPopupMenu.restype = wt.BOOL
    user32.DestroyMenu.argtypes = [wt.HMENU]
    user32.DestroyMenu.restype = wt.BOOL
    user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
    user32.RegisterHotKey.restype = wt.BOOL
    user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wt.BOOL
    user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
    user32.GetMessageW.restype = wt.BOOL
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.TranslateMessage.restype = wt.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.restype = ctypes.c_ssize_t
    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.PostThreadMessageW.restype = wt.BOOL
    user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.PostMessageW.restype = wt.BOOL
    user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
    user32.CreateWindowExW.restype = wt.HWND
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    user32.RegisterClassW.restype = ctypes.c_ushort
    user32.DestroyWindow.argtypes = [wt.HWND]
    user32.DestroyWindow.restype = wt.BOOL
    user32.UnregisterClassW.argtypes = [wt.LPCWSTR, wt.HINSTANCE]
    user32.UnregisterClassW.restype = wt.BOOL

    kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel32.OpenProcess.restype = wt.HANDLE
    kernel32.CloseHandle.argtypes = [wt.HANDLE]
    kernel32.CloseHandle.restype = wt.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                                    ctypes.POINTER(wt.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wt.BOOL
    kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wt.HMODULE
    kernel32.GetCurrentThreadId.restype = wt.DWORD


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
ENUMWNDPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ('style', wt.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wt.HINSTANCE),
        ('hIcon', wt.HICON),
        ('hCursor', wt.HANDLE),
        ('hbrBackground', wt.HBRUSH),
        ('lpszMenuName', wt.LPCWSTR),
        ('lpszClassName', wt.LPCWSTR),
    ]


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wt.DWORD), ('Data2', wt.WORD), ('Data3', wt.WORD),
                ('Data4', ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD),
        ('hWnd', wt.HWND),
        ('uID', wt.UINT),
        ('uFlags', wt.UINT),
        ('uCallbackMessage', wt.UINT),
        ('hIcon', wt.HICON),
        ('szTip', wt.WCHAR * 128),
        ('dwState', wt.DWORD),
        ('dwStateMask', wt.DWORD),
        ('szInfo', wt.WCHAR * 256),
        ('uTimeoutOrVersion', wt.UINT),
        ('szInfoTitle', wt.WCHAR * 64),
        ('dwInfoFlags', wt.DWORD),
        ('guidItem', GUID),
        ('hBalloonIcon', wt.HICON),
    ]


_setup_api()


# ---------------------------------------------------------------------------
# DPI 感知与图标生成
# ---------------------------------------------------------------------------
def set_dpi_aware():
    """进程设为 DPI 感知（Per-Monitor V2），避免高分屏下虚化与坐标错位。"""
    try:
        shcore = ctypes.WinDLL('shcore')
        try:
            if shcore.SetProcessDpiAwareness(2) != 0:
                shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def get_system_dpi():
    try:
        return int(user32.GetDpiForSystem())
    except Exception:
        return 96


def build_ico_bytes(color):
    """按 (r,g,b) 生成一个 16x16 圆形 .ico 文件字节（带透明通道）。"""
    w = h = 16
    c = (w - 1) / 2.0
    r2 = c * c + 0.5
    xor = bytearray()
    for y in range(h - 1, -1, -1):          # 图标位图自下而上
        for x in range(w):
            dx = x - c
            dy = y - c
            if dx * dx + dy * dy <= r2:
                xor += bytes((color[2], color[1], color[0], 255))
            else:
                xor += bytes((0, 0, 0, 0))
    xor = bytes(xor)
    mask_row = 4 * ((w + 7) // 8)           # AND 掩码每行按 4 字节对齐
    mask = b'\x00' * (mask_row * h)
    bi = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    data = bi + xor + mask
    ico = struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(data), 22) + data
    return ico


_ICON_CACHE = None


def ensure_icons():
    """返回 (运行图标, 停止图标) 两个 HICON。"""
    global _ICON_CACHE
    if _ICON_CACHE:
        return _ICON_CACHE
    d = os.path.join(tempfile.gettempdir(), 'dotconnector_tk')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = BASE_DIR
    run_p = os.path.join(d, 'run.ico')
    stop_p = os.path.join(d, 'stop.ico')
    try:
        with open(run_p, 'wb') as f:
            f.write(build_ico_bytes((0x1E, 0xB8, 0x30)))   # 绿色 = 运行中
        with open(stop_p, 'wb') as f:
            f.write(build_ico_bytes((0xE8, 0x40, 0x33)))   # 红色 = 已停止
    except Exception:
        return None, None
    hrun = user32.LoadImageW(None, run_p, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
    hstop = user32.LoadImageW(None, stop_p, IMAGE_ICON, 0, 0, LR_LOADFROMFILE)
    if not hrun or not hstop:
        return None, None
    _ICON_CACHE = (ctypes.cast(hrun, wt.HICON), ctypes.cast(hstop, wt.HICON))
    return _ICON_CACHE


# ---------------------------------------------------------------------------
# 系统托盘 + 全局热键（独立线程，纯 Win32 消息循环，不碰 tkinter）
# ---------------------------------------------------------------------------
class Tray:
    CLASS_NAME = 'DotConnectorTk_Tray'
    HK_TOGGLE = 0x101   # 启动/停止
    HK_FORCE = 0x102    # 强制退出
    HK_CAPTURE = 0x103  # 捕获坐标
    WM_REFRESH_HOTKEYS = WM_APP + 2   # 主线程请求重注册热键
    MENU_TOGGLE = 1
    MENU_SHOW = 2
    MENU_QUIT = 3

    def __init__(self, app):
        self.app = app
        self.hwnd = None
        self.thread = None
        self.tid = 0
        self.icon_run = None
        self.icon_stop = None
        self._wndproc = None

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name='tray')
        self.thread.start()

    def _run(self):
        self.icon_run, self.icon_stop = ensure_icons()
        self._wndproc = WNDPROC(self._wnd_proc)
        wc = WNDCLASS()
        wc.style = 0
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(
            0, self.CLASS_NAME, APP_NAME, 0,
            0, 0, 0, 0, HWND_MESSAGE, None, wc.hInstance, None)
        if not self.hwnd:
            return
        self._register_all()
        self._add_icon()
        self.tid = kernel32.GetCurrentThreadId()
        msg = wt.MSG()
        while True:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        # 退出清理
        self._delete_icon()
        user32.UnregisterHotKey(self.hwnd, self.HK_TOGGLE)
        user32.UnregisterHotKey(self.hwnd, self.HK_FORCE)
        user32.UnregisterHotKey(self.hwnd, self.HK_CAPTURE)
        user32.DestroyWindow(self.hwnd)
        user32.UnregisterClassW(self.CLASS_NAME, wc.hInstance)

    def _register_all(self):
        """按 app.hotkey_cfg 注册全部热键。"""
        hk = self.app.hotkey_cfg
        ok1 = user32.RegisterHotKey(self.hwnd, self.HK_TOGGLE, hk['toggle'][0], hk['toggle'][1])
        ok2 = user32.RegisterHotKey(self.hwnd, self.HK_FORCE, hk['force'][0], hk['force'][1])
        ok3 = user32.RegisterHotKey(self.hwnd, self.HK_CAPTURE, hk['capture'][0], hk['capture'][1])
        self.app.hotkey_registered = bool(ok1 and ok2 and ok3)

    def _refresh_hotkeys(self):
        """重注册全部热键（改热键后由主线程通知本线程调用）。"""
        if not self.hwnd:
            return
        user32.UnregisterHotKey(self.hwnd, self.HK_TOGGLE)
        user32.UnregisterHotKey(self.hwnd, self.HK_FORCE)
        user32.UnregisterHotKey(self.hwnd, self.HK_CAPTURE)
        self._register_all()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == self.WM_REFRESH_HOTKEYS:
            self._refresh_hotkeys()
            return 0
        if msg == WM_HOTKEY:
            if wparam == self.HK_TOGGLE:
                self.app.tray_action('toggle')
            elif wparam == self.HK_FORCE:
                self.app.tray_action('force')
            elif wparam == self.HK_CAPTURE:
                self.app.tray_action('capture')
            return 0
        if msg == WM_NOTIFYICON:
            low = lparam & 0xFFFF
            if low == WM_RBUTTONUP:
                self._show_menu()
            elif low == WM_LBUTTONDBLCLK:
                self.app.tray_action('show')
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _nid(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_NOTIFYICON
        nid.hIcon = self.icon_stop or self.icon_run
        nid.szTip = APP_NAME + ' - 已停止'
        return nid

    def _add_icon(self):
        nid = self._nid()
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _delete_icon(self):
        nid = self._nid()
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    def set_state(self, running, paused=False):
        if not self.hwnd or not (self.icon_run and self.icon_stop):
            return
        nid = self._nid()
        nid.hIcon = self.icon_run if running else self.icon_stop
        if running:
            nid.szTip = APP_NAME + (' - 运行中(窗口失焦暂停)' if paused else ' - 运行中')
        else:
            nid.szTip = APP_NAME + ' - 已停止'
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _show_menu(self):
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        running = self.app.is_running()
        user32.AppendMenuW(hmenu, 0, self.MENU_TOGGLE, '停止连点' if running else '开始连点')
        user32.AppendMenuW(hmenu, 0, self.MENU_SHOW, '显示主窗口')
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, 0, self.MENU_QUIT, '退出')
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                                    pt.x, pt.y, 0, self.hwnd, None)
        user32.DestroyMenu(hmenu)
        if cmd == self.MENU_TOGGLE:
            self.app.tray_action('toggle')
        elif cmd == self.MENU_SHOW:
            self.app.tray_action('show')
        elif cmd == self.MENU_QUIT:
            self.app.tray_action('quit')


# ---------------------------------------------------------------------------
# 点击引擎（独立线程；sim=True 时不产生真实点击，用于自测）
# ---------------------------------------------------------------------------
class ClickEngine:
    def __init__(self, cfg, sim=False):
        self.cfg = cfg
        self.sim = sim
        self._stop = threading.Event()
        self.count = 0
        self.paused = False
        self.finished = threading.Event()
        self._lhwnd = 0
        self._lproc = ''
        self._buf_title = ctypes.create_unicode_buffer(256)
        self._buf_proc = ctypes.create_unicode_buffer(1024)
        # 点击坐标追踪：coord_counts[(x,y)]=次数，last_coord 为最近一次
        self.coord_counts = {}
        self.last_coord = None

    def _record_coord(self, x, y):
        self.last_coord = (int(x), int(y))
        k = self.last_coord
        self.coord_counts[k] = self.coord_counts.get(k, 0) + 1

    def start(self):
        threading.Thread(target=self._run, daemon=True, name='click').start()

    def stop(self):
        self._stop.set()

    def _run(self):
        try:
            self._loop()
        finally:
            self.finished.set()

    def _loop(self):
        cfg = self.cfg
        mode = cfg['mode']
        button = cfg['button']
        lock = cfg['lock']
        fx = cfg['x']
        fy = cfg['y']
        off = cfg['rand_offset']
        interval = max(1, cfg['interval'])
        rmin = max(1, min(cfg['rmin'], cfg['rmax']))
        rmax = max(rmin, cfg['rmax'])
        hold = max(1, cfg['hold'])
        gap = max(0, cfg['gap'])
        count_on = cfg['count_on']
        count_n = cfg['count_n']
        end_time = cfg.get('end_time')
        until_ts = cfg.get('until_ts')
        win_on = cfg.get('win_on', False)
        win_mode = cfg.get('win_mode', 'title')
        win_text = cfg.get('win_text', '')
        down, up = BUTTON_FLAGS[button]

        while not self._stop.is_set():
            # 窗口检测：目标窗口未激活时暂停
            if win_on:
                if not self._check_window(win_mode, win_text):
                    self.paused = True
                    self._sleep(200)
                    continue
                self.paused = False
            else:
                self.paused = False

            now = time.time()
            if count_on and self.count >= count_n:
                break
            if end_time is not None and now >= end_time:
                break
            if until_ts is not None and now >= until_ts:
                break

            if mode == 'hold':
                x, y = self._resolve_pos(lock, fx, fy, off)
                self._set_pos(x, y)
                self._send(down)
                self._sleep(hold)
                self._send(up)
                self._record_coord(x, y)
                self.count += 1
                if self._stop.is_set():
                    break
                self._sleep(gap)
            else:
                x, y = self._resolve_pos(lock, fx, fy, off)
                self._set_pos(x, y)
                self._send(down)
                self._send(up)
                self._record_coord(x, y)
                self.count += 1
                wait = random.uniform(rmin, rmax) if mode == 'random' else interval
                self._sleep(wait)

    # ---- 辅助 ----
    def _resolve_pos(self, lock, fx, fy, off):
        if not lock:
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            return pt.x, pt.y
        if off:
            return fx + random.randint(-5, 5), fy + random.randint(-5, 5)
        return fx, fy

    def _set_pos(self, x, y):
        if not self.sim:
            user32.SetCursorPos(int(x), int(y))

    def _send(self, flags):
        if not self.sim:
            user32.mouse_event(flags, 0, 0, 0, 0)

    def _check_window(self, mode, text):
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        if mode == 'title':
            user32.GetWindowTextW(hwnd, self._buf_title, 256)
            return text.lower() in self._buf_title.value.lower()
        # 进程名（带缓存：前台窗口不变时不重复查询）
        if hwnd != self._lhwnd:
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            name = ''
            if pid.value:
                h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
                if h:
                    size = wt.DWORD(1024)
                    if kernel32.QueryFullProcessImageNameW(h, 0, self._buf_proc, ctypes.byref(size)):
                        name = os.path.basename(self._buf_proc.value).lower()
                    kernel32.CloseHandle(h)
            self._lhwnd = hwnd
            self._lproc = name
        return text.lower() in self._lproc

    def _sleep(self, ms):
        end = time.monotonic() + max(0.0, ms) / 1000.0
        while not self._stop.is_set():
            remain = end - time.monotonic()
            if remain <= 0:
                break
            time.sleep(min(0.05, remain))


# ---------------------------------------------------------------------------
# 自绘单选/复选控件（完全复现参考 CSS 效果：灰边白底、选中主色圆点/对勾、悬停变蓝）
# ---------------------------------------------------------------------------
class ModernIndicator(tk.Canvas):
    """自绘单选/复选基类。参考 CSS：
       - 未选中：2px #c0c0c0 灰边 + 白底
       - 悬停：边变主色 #3b6ef6
       - 选中：Radio 主色内圆点；Checkbox 主色蓝底 + 白色对勾
       - 禁用：整体降透明度
    控件逻辑尺寸：指示器 22px，与文字同处一个 Canvas。"""
    SIZE = 22
    GAP = 6
    BORDER = '#c0c0c0'
    PRIM = CLR_PRIMARY
    PRIM_BG = CLR_PRIMARY_BG
    TEXT = CLR_TEXT
    DISABLED_TEXT = CLR_SUB

    def __init__(self, master, text, variable, command=None, **kw):
        self._variable = variable
        self._cmd = command
        self._disabled = False
        self._hover = False
        self._states = []
        # 文字宽度（用于 Canvas 宽度）
        fnt = tkfont.Font(family=FONT_FAMILY, size=9)
        tw = fnt.measure(text)
        w = self.SIZE + self.GAP + tw + 2
        h = self.SIZE + 2
        super().__init__(master, width=w, height=h, bg='#ffffff',
                         highlightthickness=0, bd=0, cursor='hand2', **kw)
        self._text = text
        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', lambda e: self._set_hover(True))
        self.bind('<Leave>', lambda e: self._set_hover(False))
        # 变量变化时立即重绘（同组控件切换/互斥取消即刻生效，无需移过鼠标）
        variable.trace_add('write', self._on_var_changed)
        self._draw()

    def _on_var_changed(self, *_a):
        try:
            self._draw()
        except Exception:
            pass

    # ---- 兼容 ttk 的 state() 接口（供 _sync_enabled 等调用） ----
    def state(self, states=None):
        if states is None:
            return list(self._states)
        if 'disabled' in states:
            self._disabled = True
            self._states.append('disabled')
        elif '!disabled' in states:
            self._disabled = False
            try:
                self._states.remove('disabled')
            except ValueError:
                pass
        self._draw()
        return list(self._states)

    # ---- 状态 ----
    def _set_hover(self, on):
        self._hover = on
        self._draw()

    def _is_checked(self):
        if self._is_checkbox():
            return bool(self._variable.get())
        return self._variable.get() == self._value

    def _on_click(self, _e):
        if self._disabled:
            return
        if self._is_checkbox():
            self._variable.set(not bool(self._variable.get()))
        else:
            self._variable.set(self._value)
        self._draw()
        if self._cmd:
            self._cmd()

    def _draw(self):
        self.delete('all')
        s = self.SIZE
        border = self.PRIM if (self._hover or self._is_checked()) else self.BORDER
        text_fill = self.DISABLED_TEXT if self._disabled else self.TEXT
        # 背景（禁用降透明度）
        bg = '#f5f6f8' if self._disabled else '#ffffff'
        self.configure(bg=bg)
        # 外框
        if self._is_checkbox():
            self.create_rectangle(2, 2, s - 2, s - 2, outline=border, width=2,
                                  fill='#ffffff')
        else:
            self.create_oval(2, 2, s - 2, s - 2, outline=border, width=2, fill='#ffffff')
        # 选中
        if self._is_checked():
            if self._is_checkbox():
                self.create_rectangle(2, 2, s - 2, s - 2, outline=self.PRIM, width=2,
                                      fill=self.PRIM)
                # 白色对勾
                self.create_line(s * 0.27, s * 0.52, s * 0.43, s * 0.68,
                                 s * 0.73, s * 0.34, fill='#ffffff', width=2.5,
                                 capstyle='round', joinstyle='round')
            else:
                self.create_oval(s * 0.27, s * 0.27, s * 0.73, s * 0.73,
                                 fill=self.PRIM, outline='')
        # 文字
        self.create_text(s + self.GAP, s / 2 + 1, text=self._text, anchor='w',
                         font=(FONT_FAMILY, 9), fill=text_fill)

    def _is_checkbox(self):
        return isinstance(self, ModernCheck)


class ModernRadio(ModernIndicator):
    """自绘单选框：绑定 tk.Variable + value。"""
    def __init__(self, master, text, variable, value, command=None):
        self._value = value
        super().__init__(master, text, variable, command)


class ModernCheck(ModernIndicator):
    """自绘复选框：绑定 tk.BooleanVar。"""
    def __init__(self, master, text, variable, command=None):
        self._value = None   # checkbox 用布尔值
        super().__init__(master, text, variable, command)


# ---------------------------------------------------------------------------
# 主应用（tkinter UI）
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.dpi = get_system_dpi()
        self.scale_opt = tk.DoubleVar(value=1.0)
        self.eff = (self.dpi / 96.0) * self.scale_opt.get() * self._dpi_factor()
        self.lock = threading.Lock()
        self.q = queue.Queue()
        self.engine = None
        self._running = False
        self._finalized = True
        self._total = 0
        self._last_cfg = None
        self._last_icon = None
        self._top = None
        self._top_drag = None
        self.hotkey_registered = False

        # 控件状态变量
        self.v_button = tk.IntVar(value=0)
        self.v_mode = tk.StringVar(value='fixed')
        self.v_interval = tk.StringVar(value='100')
        self.v_rmin = tk.StringVar(value='1')
        self.v_rmax = tk.StringVar(value='2000')
        self.v_hold = tk.StringVar(value='200')
        self.v_gap = tk.StringVar(value='100')
        self.v_strategy = tk.StringVar(value='follow')
        self.v_x = tk.StringVar(value='400')
        self.v_y = tk.StringVar(value='300')
        self.v_offset = tk.BooleanVar(value=False)
        self.v_count_on = tk.BooleanVar(value=False)
        self.v_count = tk.StringVar(value='100')
        self.v_cd_on = tk.BooleanVar(value=False)
        self.v_cd_min = tk.StringVar(value='0')
        self.v_cd_sec = tk.StringVar(value='10')
        self.v_until_on = tk.BooleanVar(value=False)
        self.v_until = tk.StringVar(value='00:00:00')
        self.v_hotkey_stop = tk.BooleanVar(value=True)
        self.v_win_on = tk.BooleanVar(value=True)
        self.v_win_mode = tk.StringVar(value='title')
        self.v_win_text = tk.StringVar(value='')
        self.v_top = tk.BooleanVar(value=False)
        self.v_resize = tk.BooleanVar(value=False)

        self._status_text = tk.StringVar(value='已停止')
        self._count_text = tk.StringVar(value='0')
        self._total_text = tk.StringVar(value='历史累计: 0 次')
        self._hint_text = tk.StringVar(value='')
        # 热键配置（默认 Ctrl+F9 启停 / Ctrl+Alt+F10 强退 / Ctrl+Shift+F8 捕获）
        self.hotkey_cfg = {k: [m, v] for k, (m, v) in HK_DEFAULTS.items()}
        self._capturing = None          # 正在自定义的热键 key
        self._hk_entries = {}           # key -> Entry
        self._hk_status_lbl = None
        self._run_start_ts = 0.0
        self._stop_reason = '手动停止'
        self._manual_stop = False
        self._last_paused = False

        # 动态更新
        for v in (self.v_interval, self.v_rmin, self.v_rmax, self.v_hold, self.v_gap, self.v_mode):
            v.trace_add('write', self._update_hint)
        self.v_mode.trace_add('write', self._sync_mode_fields)
        self.v_strategy.trace_add('write', self._sync_enabled)
        self.v_top.trace_add('write', self._on_top_toggled)
        self.v_resize.trace_add('write', lambda *a: self._apply_resize())
        # 停止条件互斥：点击次数/倒计时/运行到 三选一
        self.v_count_on.trace_add('write', lambda *a: self._sync_stop_mutual(self.v_count_on))
        self.v_cd_on.trace_add('write', lambda *a: self._sync_stop_mutual(self.v_cd_on))
        self.v_until_on.trace_add('write', lambda *a: self._sync_stop_mutual(self.v_until_on))

        self._load_config()
        self.eff = (self.dpi / 96.0) * self.scale_opt.get() * self._dpi_factor()
        self._apply_font_scale()

        self.root.title(APP_NAME)
        self.root.protocol('WM_DELETE_WINDOW', self._quit)
        # 窗口/任务栏图标
        try:
            ico = resource_path('icon.ico')
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

        self._build_ui()
        self._apply_minsize()
        self._remove_maximize()
        self._sync_enabled()
        self._sync_mode_fields()
        self._update_hint()
        self._refresh_state()
        self._last_cfg = self._collect_cfg()
        # 热键自定义：主窗口捕获组合键（仅当 _capturing 时生效）
        self.root.bind('<KeyPress>', self._on_hotkey_pressed)

        if self.v_top.get():
            self._maybe_create_top()

        self.tray = Tray(self)
        self.tray.start()
        self.root.after(150, self._poll_queue)
        self.root.after(200, self._poll)

    # ---------- 布局工具 ----------
    def P(self, n):
        return max(1, int(round(n * self.eff)))

    def _dpi_factor(self):
        """高 DPI 系统（>100%）下界面基准减半，使软件 200% 档 = 系统自然大小，
        避免 200% 档叠加系统 DPI 后溢出屏幕（如 3200x2000@200% 下 200% 档过高）。"""
        return 0.5 if self.dpi > 96 else 1.0

    def _apply_font_scale(self):
        try:
            self.root.tk.call('tk', 'scaling',
                              (self.dpi / 72.0) * self.scale_opt.get() * self._dpi_factor())
            self.root.option_add('*Font', (FONT_FAMILY, 9))
        except Exception:
            pass
        self._setup_style()

    def _setup_style(self):
        """配置美化版主题：卡片式分组框 + 统一配色。"""
        try:
            st = ttk.Style(self.root)
            # 关键：Windows 默认 vista 主题下 TButton/TLabelframe/TEntry 的
            # background/foreground/bordercolor 走原生绘制不生效（导致白字白底、卡片无边框）。
            # 切换 clam 主题后所有自定义配色才能真正渲染。
            try:
                st.theme_use('clam')
            except Exception:
                pass
            st.configure('.', font=(FONT_FAMILY, 9), background=CLR_BG, foreground=CLR_TEXT)
            # 主窗口背景
            st.configure('TFrame', background=CLR_BG)
            # 卡片式分组框
            st.configure('Card.TLabelframe',
                         background=CLR_CARD,
                         bordercolor=CLR_BORDER,
                         lightcolor=CLR_BORDER,
                         darkcolor=CLR_BORDER,
                         relief='solid',
                         borderwidth=1)
            st.configure('Card.TLabelframe.Label',
                         background=CLR_CARD,
                         foreground=CLR_PRIMARY,
                         font=(FONT_FAMILY, 9, 'bold'))
            # 框架背景
            st.configure('TFrame', background=CLR_BG)
            st.configure('App.TFrame', background=CLR_BG)
            st.configure('Card.TFrame', background=CLR_CARD)
            # 普通标签（卡片白底，与分组框融为一体）
            st.configure('TLabel', background=CLR_CARD, foreground=CLR_TEXT)
            st.configure('Sub.TLabel', background=CLR_CARD, foreground=CLR_SUB)
            st.configure('Primary.TLabel', background=CLR_CARD, foreground=CLR_PRIMARY)
            st.configure('Card.TLabel', background=CLR_CARD, foreground=CLR_TEXT)
            st.configure('Card.Sub.TLabel', background=CLR_CARD, foreground=CLR_SUB)
            # 普通按钮
            st.configure('TButton',
                         background=CLR_BG, foreground=CLR_TEXT,
                         bordercolor=CLR_BORDER,
                         focusthickness=0, padding=(10, 5))
            st.map('TButton',
                   background=[('active', CLR_PRIMARY_BG), ('disabled', '#e8eaed')],
                   foreground=[('active', CLR_PRIMARY), ('disabled', CLR_SUB)],
                   bordercolor=[('disabled', CLR_BORDER)])
            # 强调按钮（开始/停止）
            st.configure('Accent.TButton',
                         background=CLR_PRIMARY, foreground='#ffffff',
                         bordercolor=CLR_PRIMARY, padding=(16, 7),
                         font=(FONT_FAMILY, 10, 'bold'))
            st.map('Accent.TButton',
                   background=[('active', CLR_PRIMARY_DARK), ('pressed', CLR_PRIMARY_DARK)],
                   foreground=[('active', '#ffffff')])
            # 小按钮（导出/清空等）
            st.configure('Small.TButton',
                         background=CLR_BG, foreground=CLR_TEXT,
                         bordercolor=CLR_BORDER,
                         focusthickness=0, padding=(8, 4),
                         font=(FONT_FAMILY, 9))
            st.map('Small.TButton',
                   background=[('active', CLR_PRIMARY_BG), ('disabled', '#e8eaed')],
                   foreground=[('active', CLR_PRIMARY), ('disabled', CLR_SUB)],
                   bordercolor=[('disabled', CLR_BORDER)])
            # 输入框
            st.configure('TEntry',
                         fieldbackground='#ffffff', foreground=CLR_TEXT,
                         bordercolor=CLR_BORDER,
                         lightcolor=CLR_BORDER, darkcolor=CLR_BORDER,
                         padding=(4, 3))
            st.map('TEntry',
                   bordercolor=[('focus', CLR_PRIMARY)],
                   lightcolor=[('focus', CLR_PRIMARY)],
                   darkcolor=[('focus', CLR_PRIMARY)])
            # 单选 / 复选（卡片白底 + 主色指示器 + 柔和边框/悬停高亮）
            # 单选 / 复选（现代风格：白底灰边，悬停/选中主色，参考 CSS #c0c0c0 边框）
            RB_BORDER = '#c0c0c0'
            st.configure('TRadiobutton',
                         background=CLR_CARD, foreground=CLR_TEXT, focuscolor=CLR_PRIMARY,
                         indicatorcolor=CLR_PRIMARY, indicatorbackground='#ffffff',
                         indicatorrelief='flat', bordercolor=RB_BORDER,
                         lightcolor=RB_BORDER, darkcolor=RB_BORDER,
                         indicatormargin=6, padding=(5, 4))
            st.map('TRadiobutton',
                   background=[('active', CLR_PRIMARY_BG), ('selected', CLR_CARD),
                               ('disabled', CLR_CARD)],
                   foreground=[('active', CLR_PRIMARY), ('selected', CLR_TEXT),
                               ('disabled', CLR_SUB)],
                   indicatorcolor=[('selected', CLR_PRIMARY), ('!selected', '#ffffff')],
                   bordercolor=[('active', CLR_PRIMARY), ('focus', CLR_PRIMARY),
                                ('selected', CLR_PRIMARY)],
                   lightcolor=[('active', CLR_PRIMARY), ('focus', CLR_PRIMARY)],
                   darkcolor=[('active', CLR_PRIMARY), ('focus', CLR_PRIMARY)])
            st.configure('TCheckbutton',
                         background=CLR_CARD, foreground=CLR_TEXT, focuscolor=CLR_PRIMARY,
                         indicatorcolor='#ffffff', indicatorbackground='#ffffff',
                         indicatorrelief='flat', bordercolor=RB_BORDER,
                         lightcolor=RB_BORDER, darkcolor=RB_BORDER,
                         indicatormargin=6, padding=(5, 4))
            st.map('TCheckbutton',
                   background=[('active', CLR_PRIMARY_BG), ('selected', CLR_CARD),
                               ('disabled', CLR_CARD)],
                   foreground=[('active', CLR_PRIMARY), ('selected', CLR_TEXT),
                               ('disabled', CLR_SUB)],
                   indicatorbackground=[('selected', CLR_PRIMARY), ('!selected', '#ffffff')],
                   indicatorcolor=[('selected', '#ffffff'), ('!selected', '#ffffff')],
                   bordercolor=[('active', CLR_PRIMARY), ('focus', CLR_PRIMARY),
                                ('selected', CLR_PRIMARY)],
                   lightcolor=[('active', CLR_PRIMARY), ('focus', CLR_PRIMARY)],
                   darkcolor=[('active', CLR_PRIMARY), ('focus', CLR_PRIMARY)])
            # 顶栏标签（状态/缩放卡片内）
            st.configure('Top.Sub.TLabel', background=CLR_CARD, foreground=CLR_SUB)
            st.configure('Top.Count.TLabel', background=CLR_CARD, foreground=CLR_PRIMARY,
                         font=(FONT_FAMILY, 9, 'bold'))
            st.configure('Top.Status.TLabel', background=CLR_CARD, foreground=CLR_TEXT,
                         font=(FONT_FAMILY, 9, 'bold'))
            # 滚动条（clam 默认样式较粗糙，统一为柔和滑块）
            st.configure('Vertical.TScrollbar',
                         background=CLR_BORDER, troughcolor=CLR_CARD,
                         bordercolor=CLR_CARD, arrowcolor=CLR_SUB, relief='flat')
            st.map('Vertical.TScrollbar',
                   background=[('active', CLR_PRIMARY), ('pressed', CLR_PRIMARY_DARK)])
        except Exception:
            pass

    def _build_ui(self):
        """基础版：保留 v2 设计风格，顶部标签页布局，点击标签切换页面。"""
        self._pages = {}
        self._tab_btns = {}
        self._log_boxes = []
        self.root.configure(bg=CLR_BG)

        # 顶部标签栏（类似标签页）
        self._build_tabsbar()

        # 页面容器
        self._page_host = ttk.Frame(self.root, style='App.TFrame')
        self._page_host.pack(fill='both', expand=True, padx=self.P(8), pady=self.P(6))

        # 构建 5 个标签页（点击设置第1默认打开，运行状态第2）
        self._build_page_click()       # 1 点击设置（默认）
        self._build_page_status()      # 2 运行状态
        self._build_page_log()         # 3 运行日志
        self._build_page_hotkeys()     # 4 热键设置
        self._build_page_ui()          # 5 界面设置

        self.show_page(getattr(self, '_current_page', '点击设置'))

    TAB_ITEMS = ['点击设置', '运行状态', '运行日志', '热键设置', '界面设置']

    def _build_tabsbar(self):
        """顶部标签栏：纯文字标签靠左对齐，选中高亮。"""
        P = self.P
        bar = ttk.Frame(self.root, style='App.TFrame')
        bar.pack(fill='x', padx=(0, P(8)), pady=(P(6), 0))
        # Logo（紧贴左缘）
        ttk.Label(bar, text='DotConnector', style='App.TFrame',
                  font=(FONT_EN, 12, 'bold'), foreground=CLR_PRIMARY).pack(
            side='left', padx=(P(4), P(12)))
        # 标签按钮（无图标，靠左顺序排列）
        for name in self.TAB_ITEMS:
            btn = tk.Label(bar, text=name,
                           font=(FONT_FAMILY, 10, 'bold'),
                           bg=CLR_BG, fg=CLR_SUB, cursor='hand2',
                           padx=P(14), pady=P(6))
            btn.pack(side='left', padx=P(1))
            btn.bind('<Button-1>', lambda e, n=name: self.show_page(n))
            self._tab_btns[name] = btn

    def show_page(self, name):
        """切换标签页：高亮当前标签 + 显示对应页面。"""
        if name not in self._pages:
            name = '点击设置'
        self._current_page = name
        for pname, page in self._pages.items():
            if pname == name:
                page.pack(fill='both', expand=True)
            elif page.winfo_manager():
                page.pack_forget()
        for n, btn in self._tab_btns.items():
            if n == name:
                btn.configure(bg=CLR_PRIMARY_BG, fg=CLR_PRIMARY)
            else:
                btn.configure(bg=CLR_BG, fg=CLR_SUB)

    def _make_scrollable(self, parent):
        canvas = tk.Canvas(parent, bg=CLR_BG, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        inner = tk.Frame(canvas, bg=CLR_BG)
        wid = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(wid, width=e.width))
        canvas.bind('<MouseWheel>',
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), 'units'))
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        return inner, canvas

    # ---------- 标签页 1：运行状态 ----------
    def _build_page_status(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        self._pages['运行状态'] = page
        P = self.P

        # 详细运行状态
        sf = ttk.LabelFrame(page, text='运行状态', padding=P(6), style='Card.TLabelframe')
        sf.pack(fill='x', pady=(0, P(3)))
        self._lamp = tk.Canvas(sf, width=18, height=18, bg=CLR_CARD, highlightthickness=0, bd=0)
        self._lamp.grid(row=0, column=0, rowspan=2, sticky='ns', padx=(P(4), 0), pady=P(2))
        self._lamp_id = self._lamp.create_oval(3, 3, 15, 15, fill=CLR_STOP, outline='')
        self._lbl_status = ttk.Label(sf, text='已停止', style='Top.Status.TLabel')
        self._lbl_status.grid(row=0, column=1, sticky='w', padx=(P(4), P(4)))
        ttk.Label(sf, text='本次:', style='Top.Sub.TLabel').grid(row=0, column=2, sticky='e', padx=(P(16), 0))
        ttk.Label(sf, textvariable=self._count_text, style='Top.Count.TLabel').grid(
            row=0, column=3, sticky='w', padx=P(2))
        ttk.Label(sf, textvariable=self._total_text, style='Top.Sub.TLabel').grid(
            row=0, column=4, sticky='e', padx=P(10))
        self._lbl_counts = ttk.Label(sf, text='', style='Top.Sub.TLabel')
        self._lbl_counts.grid(row=1, column=1, columnspan=4, sticky='w', padx=P(4), pady=(P(4), 0))

        # 热键说明
        hk_card = ttk.LabelFrame(page, text='热键说明', padding=P(6), style='Card.TLabelframe')
        hk_card.pack(fill='x', pady=P(3))
        for i, (key, label) in enumerate(HK_LABELS.items()):
            ttk.Label(hk_card, text=label + ':', style='Card.TLabel').grid(
                row=i, column=0, sticky='w', padx=P(6), pady=P(2))
            m, v = self.hotkey_cfg[key]
            ttk.Label(hk_card, text=fmt_hotkey(m, v), foreground=CLR_PRIMARY,
                      style='Card.TLabel', font=(FONT_EN, 9, 'bold')).grid(
                row=i, column=1, sticky='w', padx=P(4), pady=P(2))

        # 窗口检测
        wf = ttk.LabelFrame(page, text='窗口检测', padding=P(6), style='Card.TLabelframe')
        wf.pack(fill='x', pady=(P(3), 0))
        wf.columnconfigure(1, weight=1)
        self._chk_win = ModernCheck(wf, '仅当指定窗口激活时连点，否则自动暂停', self.v_win_on)
        self._chk_win.grid(row=0, column=0, columnspan=2, sticky='w', padx=P(6))
        ttk.Button(wf, text='选择运行中的程序…', command=self._pick_window).grid(
            row=1, column=0, sticky='w', padx=P(6), pady=(P(2), 0))
        self._chk_win_selected = ttk.Label(wf, text='', foreground=CLR_PRIMARY)
        self._chk_win_selected.grid(row=2, column=0, columnspan=2, sticky='w', padx=P(6), pady=(P(2), 0))

    # ---------- 标签页 2：点击设置 ----------
    def _build_page_click(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        page.columnconfigure(0, weight=1)
        self._pages['点击设置'] = page
        self._click_inner = page    # 供 _apply_minsize 计算默认窗口尺寸
        P = self.P
        inner = page
        row = 0

        # ① 点击模式
        lf = ttk.LabelFrame(inner, text='① 点击模式', padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        for i, (txt, val) in enumerate([('固定间隔', 'fixed'), ('随机间隔', 'random'), ('长按模式', 'hold')]):
            ModernRadio(lf, txt, self.v_mode, val).grid(
                row=0, column=i, sticky='w', padx=P(6))

        # ② 鼠标按键
        lf = ttk.LabelFrame(inner, text='② 鼠标按键', padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        for i, txt in enumerate(['左键', '中键', '右键']):
            ModernRadio(lf, txt, self.v_button, i).grid(
                row=0, column=i, sticky='w', padx=P(6))

        # ③ 点击速度（pack 布局：每组「标签+输入框」紧贴，提示紧跟其后）
        lf = ttk.LabelFrame(inner, text='③ 点击速度', padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        speed_row = ttk.Frame(lf, style='Card.TFrame')
        speed_row.pack(fill='x', pady=(0, P(4)))
        # 固定间隔组
        self._grp_fixed = ttk.Frame(speed_row, style='Card.TFrame')
        self._lbl_interval = ttk.Label(self._grp_fixed, text='间隔(ms):')
        self._ent_interval = ttk.Entry(self._grp_fixed, textvariable=self.v_interval,
                                       width=6, justify='center')
        self._lbl_interval.pack(side='left')
        self._ent_interval.pack(side='left', padx=(2, 0))
        # 随机间隔组：最小 / 最大
        self._grp_random = ttk.Frame(speed_row, style='Card.TFrame')
        self._lbl_rmin = ttk.Label(self._grp_random, text='最小(ms):')
        self._ent_rmin = ttk.Entry(self._grp_random, textvariable=self.v_rmin,
                                   width=6, justify='center')
        self._lbl_rmax = ttk.Label(self._grp_random, text='最大(ms):')
        self._ent_rmax = ttk.Entry(self._grp_random, textvariable=self.v_rmax,
                                   width=6, justify='center')
        self._lbl_rmin.pack(side='left')
        self._ent_rmin.pack(side='left', padx=(2, 0))
        self._lbl_rmax.pack(side='left', padx=(8, 0))
        self._ent_rmax.pack(side='left', padx=(2, 0))
        # 长按模式组：按住 / 松开
        self._grp_hold = ttk.Frame(speed_row, style='Card.TFrame')
        self._lbl_hold = ttk.Label(self._grp_hold, text='按住(ms):')
        self._ent_hold = ttk.Entry(self._grp_hold, textvariable=self.v_hold,
                                   width=6, justify='center')
        self._lbl_gap = ttk.Label(self._grp_hold, text='松开(ms):')
        self._ent_gap = ttk.Entry(self._grp_hold, textvariable=self.v_gap,
                                  width=6, justify='center')
        self._lbl_hold.pack(side='left')
        self._ent_hold.pack(side='left', padx=(2, 0))
        self._lbl_gap.pack(side='left', padx=(8, 0))
        self._ent_gap.pack(side='left', padx=(2, 0))
        # 换算提示（紧跟当前模式组后面）
        self._hint_lbl = ttk.Label(speed_row, textvariable=self._hint_text, foreground=CLR_PRIMARY)
        # 默认显示固定间隔组
        self._grp_fixed.pack(side='left')
        self._hint_lbl.pack(side='left', padx=(6, 0))

        qf = ttk.Frame(lf, style='Card.TFrame')
        qf.pack(fill='x', pady=(P(4), 0))
        ttk.Label(qf, text='常用:').pack(side='left', padx=(P(6), P(4)))
        self._preset_btns = {}
        for txt, ms in [('1秒1下', 1000), ('1秒10下', 100), ('1秒20下', 50),
                        ('1秒50下', 20), ('1秒100下', 10)]:
            b = ttk.Button(qf, text=txt, width=9, command=lambda m=ms: self._quick(m))
            b.pack(side='left', padx=P(2))
            self._preset_btns[ms] = b

        # ④ 点击位置
        lf = ttk.LabelFrame(inner, text='④ 点击位置', padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        ModernRadio(lf, '跟随鼠标', self.v_strategy, 'follow').grid(
            row=0, column=0, sticky='w', padx=P(6))
        ModernRadio(lf, '锁定坐标', self.v_strategy, 'lock').grid(
            row=0, column=1, sticky='w', padx=P(12))
        self._lbl_cap = ttk.Label(lf, text='按 Ctrl+Shift+F8 捕获当前坐标', foreground=CLR_SUB)
        self._lbl_cap.grid(row=0, column=2, sticky='w', padx=P(12))
        xy = ttk.Frame(lf, style='Card.TFrame')
        xy.grid(row=1, column=0, columnspan=3, sticky='w', padx=P(6), pady=P(2))
        self._lbl_x = ttk.Label(xy, text='X:')
        self._ent_x = ttk.Entry(xy, textvariable=self.v_x, width=7, justify='center')
        self._lbl_y = ttk.Label(xy, text='Y:')
        self._ent_y = ttk.Entry(xy, textvariable=self.v_y, width=7, justify='center')
        self._lbl_x.pack(side='left')
        self._ent_x.pack(side='left', padx=(2, 0))
        self._lbl_y.pack(side='left', padx=(8, 0))
        self._ent_y.pack(side='left', padx=(2, 0))
        self._chk_offset = ModernCheck(lf, '锁定后每次点击 ±5 像素随机偏移', self.v_offset)
        self._chk_offset.grid(row=2, column=0, columnspan=3, sticky='w', padx=P(6), pady=P(2))

        # ⑤ 停止条件
        lf = ttk.LabelFrame(inner, text='⑤ 停止条件', padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=(P(3), 0)); row += 1
        ModernCheck(lf, '热键 Ctrl+F9 开启/停止（默认开启）', self.v_hotkey_stop).grid(
            row=0, column=0, columnspan=5, sticky='w', padx=P(6), pady=(0, P(2)))
        ModernCheck(lf, '点击次数:', self.v_count_on).grid(
            row=1, column=0, sticky='w', padx=P(6))
        ttk.Entry(lf, textvariable=self.v_count, width=8, justify='center').grid(
            row=1, column=1, sticky='w', padx=P(4))
        ttk.Label(lf, text='次').grid(row=1, column=2, sticky='w', padx=P(2))
        ModernCheck(lf, '倒计时:', self.v_cd_on).grid(
            row=2, column=0, sticky='w', padx=P(6))
        ttk.Entry(lf, textvariable=self.v_cd_min, width=5, justify='center').grid(
            row=2, column=1, sticky='w', padx=P(4))
        ttk.Label(lf, text='分').grid(row=2, column=2, sticky='w', padx=P(2))
        ttk.Entry(lf, textvariable=self.v_cd_sec, width=5, justify='center').grid(
            row=2, column=3, sticky='w', padx=P(4))
        ttk.Label(lf, text='秒').grid(row=2, column=4, sticky='w', padx=P(2))
        ModernCheck(lf, '运行到:', self.v_until_on).grid(
            row=3, column=0, sticky='w', padx=P(6))
        ttk.Entry(lf, textvariable=self.v_until, width=10, justify='center').grid(
            row=3, column=1, sticky='w', padx=P(4))
        ttk.Label(lf, text='(时:分:秒, 到点自动停止)').grid(
            row=3, column=2, columnspan=3, sticky='w', padx=P(2))

        self._sync_mode_fields()
        self._sync_enabled()

    # ---------- 标签页 3：运行日志（含导出） ----------
    def _build_page_log(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        self._pages['运行日志'] = page
        P = self.P
        logf = ttk.LabelFrame(page, text='运行日志', padding=P(6), style='Card.TLabelframe')
        logf.pack(fill='both', expand=True)
        top = ttk.Frame(logf, style='Card.TFrame')
        top.pack(fill='x', pady=(0, P(4)))
        ttk.Button(top, text='清空日志', command=self._clear_log,
                   style='Small.TButton').pack(side='right', padx=P(2))
        ttk.Button(top, text='导出 TXT', command=lambda: self._export_log('txt'),
                   style='Small.TButton').pack(side='right', padx=P(2))
        ttk.Button(top, text='导出 MD', command=lambda: self._export_log('md'),
                   style='Small.TButton').pack(side='right', padx=P(2))
        self._log_box = scrolledtext.ScrolledText(
            logf, height=7, wrap='word', state='disabled',
            font=(FONT_MONO, 9), bg='#ffffff', fg=CLR_TEXT,
            insertbackground=CLR_TEXT, relief='flat', bd=0)
        self._log_box.pack(fill='both', expand=True)
        self._log_boxes.append(self._log_box)
        if not getattr(self, '_startup_logged', False):
            self._log('程序已启动，按热键（默认 Ctrl+F9）启动/停止连点')
            self._startup_logged = True

    # ---------- 标签页 4：热键设置 ----------
    def _build_page_hotkeys(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        self._pages['热键设置'] = page
        P = self.P
        hkf = ttk.LabelFrame(page, text='热键设置', padding=P(6), style='Card.TLabelframe')
        hkf.pack(fill='x')
        for i, (key, label) in enumerate(HK_LABELS.items()):
            ttk.Label(hkf, text=label + ':', style='Card.TLabel').grid(
                row=i, column=0, sticky='w', padx=P(4), pady=P(1))
            ent = ttk.Entry(hkf, width=15, justify='center', state='readonly')
            ent.grid(row=i, column=1, sticky='w', padx=P(2), pady=P(1))
            self._hk_entries[key] = ent
            self._update_hk_entry(key)
            ttk.Button(hkf, text='设置', width=5,
                       command=lambda k=key: self._capture_hotkey(k)).grid(
                row=i, column=2, sticky='w', padx=P(4), pady=P(1))
        self._hk_status_lbl = ttk.Label(hkf, text='点击"设置"自定义热键', foreground=CLR_SUB,
                                        style='Card.Sub.TLabel')
        self._hk_status_lbl.grid(row=len(HK_LABELS), column=0, columnspan=3,
                                 sticky='w', padx=P(4), pady=(P(2), 0))
        ttk.Button(hkf, text='恢复默认热键', command=self._reset_hotkeys).grid(
            row=len(HK_LABELS) + 1, column=0, columnspan=3, sticky='w',
            padx=P(4), pady=(P(4), P(2)))

    # ---------- 标签页 5：界面设置 ----------
    def _build_page_ui(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        self._pages['界面设置'] = page
        P = self.P
        # 界面缩放模块（仅缩放选项）
        vf = ttk.LabelFrame(page, text='界面缩放', padding=P(6), style='Card.TLabelframe')
        vf.pack(fill='x', pady=(0, P(4)))
        for i, (txt, val) in enumerate([('100%', 1.0), ('150%', 1.5), ('200%', 2.0)]):
            ModernRadio(vf, txt, self.scale_opt, val,
                        command=self._on_scale_change).grid(row=0, column=i, sticky='w', padx=P(4))
        self._chk_resize = ModernCheck(vf, '界面拖拽（可调整窗口大小）', self.v_resize)
        self._chk_resize.grid(row=1, column=0, columnspan=3, sticky='w', padx=P(4), pady=(P(2), 0))
        # 更多功能模块（置顶计数等）
        mf = ttk.LabelFrame(page, text='更多功能', padding=P(6), style='Card.TLabelframe')
        mf.pack(fill='x', pady=(0, P(4)))
        self._chk_top = ModernCheck(mf, '置顶计数', self.v_top)
        self._chk_top.pack(anchor='w', padx=P(4), pady=(P(2), P(4)))
        ttk.Label(vf, text='DotConnector  v%s' % VERSION, foreground=CLR_SUB,
                  style='Card.Sub.TLabel').grid(row=2, column=0, columnspan=3, sticky='w',
                                                 padx=P(4), pady=(P(6), 0))

    def _export_log(self, fmt):
        """导出日志为 md 或 txt 格式文件。"""
        try:
            content = ''
            for box in self._log_boxes:
                try:
                    content = box.get('1.0', 'end-1c')
                    break
                except Exception:
                    continue
            if not content.strip():
                self._log('日志为空，无可导出内容')
                return
            ts = time.strftime('%Y%m%d_%H%M%S')
            if fmt == 'md':
                ext = 'md'
                body = '# DotConnector 运行日志\n\n> 导出时间：%s\n\n```\n%s\n```\n' % (
                    time.strftime('%Y-%m-%d %H:%M:%S'), content)
            else:
                ext = 'txt'
                body = 'DotConnector 运行日志\n导出时间：%s\n%s\n' % (
                    time.strftime('%Y-%m-%d %H:%M:%S'), content)
            path = filedialog.asksaveasfilename(
                defaultextension='.%s' % ext,
                initialfile='dotconnector_log_%s.%s' % (ts, ext),
                filetypes=[('%s 文件' % fmt.upper(), '*.%s' % ext)],
                title='导出运行日志')
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(body)
                self._log('日志已导出：%s' % os.path.basename(path))
        except Exception as e:
            self._log('导出日志失败：%s' % e)

    def _clear_log(self):
        for box in self._log_boxes:
            try:
                box.configure(state='normal')
                box.delete('1.0', 'end')
                box.configure(state='disabled')
            except Exception:
                pass
        self._log('日志已清空')

    def _reset_hotkeys(self):
        """恢复默认热键并立即生效。"""
        self.hotkey_cfg = {k: [m, v] for k, (m, v) in HK_DEFAULTS.items()}
        for k in HK_LABELS:
            self._update_hk_entry(k)
        self._save_config()
        self._log('热键已恢复默认')
        if hasattr(self, 'tray') and self.tray.hwnd:
            user32.PostMessageW(self.tray.hwnd, Tray.WM_REFRESH_HOTKEYS, 0, 0)

    def _apply_minsize(self):
        """按「点击设置」页内容需求固定默认窗口尺寸，完整显示全部设置。"""
        try:
            self.root.update_idletasks()
            inner = getattr(self, '_click_inner', None)
            if inner is not None:
                req_w = inner.winfo_reqwidth()
                req_h = inner.winfo_reqheight()
            else:
                req_w = self._page_host.winfo_reqwidth()
                req_h = self._page_host.winfo_reqheight()
            # 标签栏 + 边距
            w = req_w + self.P(24)
            h = req_h + self.P(64)
            # 不超出屏幕
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            w = min(w, sw - self.P(20))
            h = min(h, sh - self.P(40))
            self.root.minsize(w, h)
            if not getattr(self, '_geom_set', False):
                self.root.geometry('%dx%d' % (w, h))
                self._geom_set = True
            # 应用界面拖拽开关
            self._apply_resize()
        except Exception:
            pass

    def _apply_resize(self, *a):
        """界面拖拽开关：默认关闭(固定大小)，开启后允许拖拽调整窗口大小。"""
        try:
            if getattr(self, '_geom_set', False):
                self.root.resizable(self.v_resize.get(), self.v_resize.get())
        except Exception:
            pass

    def _remove_maximize(self):
        try:
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            style = user32.GetWindowLongW(hwnd, GWL_STYLE)
            user32.SetWindowLongW(hwnd, GWL_STYLE, style & ~WS_MAXIMIZEBOX)
        except Exception:
            pass

    # ---------- 动态状态 ----------
    def _sync_enabled(self, *a):
        try:
            lock = self.v_strategy.get() == 'lock'
            for wd in (self._lbl_x, self._ent_x, self._lbl_y, self._ent_y, self._chk_offset):
                wd.state(['!disabled'] if lock else ['disabled'])
        except Exception:
            pass

    def _sync_mode_fields(self, *a):
        try:
            mode = self.v_mode.get()
            # 隐藏全部三组后，只显示当前模式组（pack 布局，提示紧跟组尾）
            for g in (self._grp_fixed, self._grp_random, self._grp_hold):
                g.pack_forget()
            self._hint_lbl.pack_forget()
            if mode == 'random':
                self._grp_random.pack(side='left')
            elif mode == 'hold':
                self._grp_hold.pack(side='left')
            else:
                self._grp_fixed.pack(side='left')
            self._hint_lbl.pack(side='left', padx=(self.P(6), 0))
            # 常用预设按钮：仅固定间隔模式启用，随机/长按模式下禁用
            enabled = (mode == 'fixed')
            for b in getattr(self, '_preset_btns', {}).values():
                b.configure(state='normal' if enabled else 'disabled')
        except Exception:
            pass

    def _sync_stop_mutual(self, src):
        """停止条件三选一：勾选一项时自动取消另外两项。"""
        try:
            if not src.get():
                return
            for v in (self.v_count_on, self.v_cd_on, self.v_until_on):
                if v is not src and v.get():
                    v.set(False)
        except Exception:
            pass

    def _f(self, v):
        try:
            return float(v.get())
        except Exception:
            return 0.0

    def _clamp_f(self, v, lo, hi):
        val = self._f(v)
        if val < lo:
            val = lo
        if val > hi:
            val = hi
        return val

    def _update_hint(self, *a):
        try:
            mode = self.v_mode.get()
            if mode == 'hold':
                h = max(1, self._f(self.v_hold))
                g = max(0, self._f(self.v_gap))
                self._hint_text.set('按住 %.0f ms / 松开 %.0f ms' % (h, g))
            elif mode == 'random':
                lo = self._f(self.v_rmin)
                hi = self._f(self.v_rmax)
                if lo <= 0 or hi <= 0:
                    self._hint_text.set('')
                    return
                if lo > hi:
                    lo, hi = hi, lo
                self._hint_text.set('≈ 1秒 %.1f ~ %.1f 下' % (1000.0 / hi, 1000.0 / lo))
            else:
                iv = self._f(self.v_interval)
                if iv <= 0:
                    self._hint_text.set('')
                    return
                self._hint_text.set('≈ 1秒 %.1f 下' % (1000.0 / iv))
        except Exception:
            self._hint_text.set('')

    def _quick(self, ms):
        # 速度按钮同时设置固定间隔与随机范围，三种模式保持一致
        self.v_interval.set(str(ms))
        self.v_rmin.set(str(ms))
        self.v_rmax.set(str(ms))
        self._update_hint()

    def _capture_pos(self):
        pt = wt.POINT()
        if user32.GetCursorPos(ctypes.byref(pt)):
            self.v_strategy.set('lock')
            self.v_x.set(str(int(pt.x)))
            self.v_y.set(str(int(pt.y)))
            self._log('已捕获当前坐标 (%d, %d)' % (pt.x, pt.y))

    # ---------- 热键自定义 ----------
    def _update_hk_entry(self, key):
        ent = self._hk_entries.get(key)
        if ent is not None:
            m, v = self.hotkey_cfg[key]
            ent.configure(state='normal')
            ent.delete(0, 'end')
            ent.insert(0, fmt_hotkey(m, v))
            ent.configure(state='readonly')

    def _capture_hotkey(self, key):
        """点击"设置"后监听下一次按键组合作为新热键。"""
        if self._capturing:
            self._log('请先完成当前热键设置')
            return
        self._capturing = key
        ent = self._hk_entries[key]
        ent.configure(state='normal')
        ent.delete(0, 'end')
        ent.insert(0, '请按键…')
        ent.configure(state='readonly')
        if self._hk_status_lbl is not None:
            self._hk_status_lbl.config(text='正在设置[%s]，请按新的组合键…' % HK_LABELS[key],
                                       foreground=CLR_WARN)
        # 主窗口获得焦点以接收按键
        self._show_window()
        self.root.focus_force()

    def _on_hotkey_pressed(self, event):
        """主窗口 KeyPress 回调：收集修饰键 + 主键，完成热键自定义。"""
        if not self._capturing:
            return
        if event.keysym == 'Escape':
            key = self._capturing
            self._capturing = None
            self._update_hk_entry(key)
            if self._hk_status_lbl is not None:
                self._hk_status_lbl.config(text='已取消', foreground=CLR_SUB)
            return
        mods = 0
        if event.state & 0x4:
            mods |= MOD_CONTROL
        # Windows Tk 中 Alt 的位是 0x20000，0x8 不是 Alt（可能是 NumLock 等系统状态），
        # 认 0x8 会导致"没按 Alt 却录成 Alt"的误判。
        if event.state & 0x20000:
            mods |= MOD_ALT
        if event.state & 0x1:
            mods |= MOD_SHIFT
        vk = keysym_to_vk(event.keysym)
        if vk is None:
            return
        # 允许无修饰键的功能键（F1-F24）作为热键；字母/数字/方向键必须带修饰键，避免误触
        if not mods and not (0x70 <= vk <= 0x87):
            return
        # 冲突检测：不允许与其他热键相同
        for k, (m, v) in self.hotkey_cfg.items():
            if k != self._capturing and m == mods and v == vk:
                if self._hk_status_lbl is not None:
                    self._hk_status_lbl.config(text='与[%s]冲突，请换一个' % HK_LABELS[k],
                                               foreground=CLR_STOP)
                return
        key = self._capturing
        self.hotkey_cfg[key] = [mods, vk]
        self._capturing = None
        self._update_hk_entry(key)
        if self._hk_status_lbl is not None:
            self._hk_status_lbl.config(text='已更新，立即生效', foreground=CLR_OK)
        self._save_config()
        self._log('热键[%s]已改为 %s' % (HK_LABELS[key], fmt_hotkey(mods, vk)))
        # 通知托盘线程重注册热键（PostMessageW 到托盘窗口，由窗口过程处理）
        if hasattr(self, 'tray') and self.tray.hwnd:
            user32.PostMessageW(self.tray.hwnd, Tray.WM_REFRESH_HOTKEYS, 0, 0)

    # ---------- 选择运行中的程序（窗口检测） ----------
    def _window_title(self, hwnd):
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ''
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value.strip()

    def _process_name_of(self, hwnd):
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ''
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return ''
        try:
            size = wt.DWORD(1024)
            buf = ctypes.create_unicode_buffer(1024)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(h)
        return ''

    def _list_running_windows(self):
        """枚举所有可见顶层窗口，返回 [(标题, 进程名), ...]（去重，跳过无标题窗口）。"""
        items = []
        seen = set()
        own = kernel32.GetCurrentProcessId()

        def cb(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            title = self._window_title(hwnd)
            if not title:
                return True
            proc = self._process_name_of(hwnd)
            if not proc:
                return True
            # 跳过自身
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == own:
                return True
            key = (proc.lower(), title.lower())
            if key in seen:
                return True
            seen.add(key)
            items.append((title, proc))
            return True

        user32.EnumWindows(ENUMWNDPROC(cb), 0)
        items.sort(key=lambda x: (x[1].lower(), x[0].lower()))
        return items

    def _pick_window(self):
        """弹出对话框，列出运行中的窗口，双击/选择后填入窗口检测目标。"""
        items = self._list_running_windows()
        if not items:
            self._chk_win_selected.config(text='未发现可选的运行中窗口', foreground=CLR_STOP)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title('选择运行中的程序')
        dlg.transient(self.root)
        dlg.configure(bg=CLR_BG)
        dlg.resizable(True, True)
        P = self.P
        frm = ttk.Frame(dlg, padding=P(10), style='App.TFrame')
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text='双击选择要检测的窗口（自动填充：有标题用标题，否则用进程名）',
                  foreground=CLR_SUB, background=CLR_BG, wraplength=int(560 * self.eff),
                  justify='left').pack(anchor='w', pady=(0, P(4)))

        # 搜索框
        sf = ttk.Frame(frm, style='App.TFrame')
        sf.pack(fill='x', pady=(P(6), P(6)))
        ttk.Label(sf, text='搜索:', background=CLR_BG, foreground=CLR_TEXT).pack(side='left')
        search = tk.StringVar()

        # 列表（行高按当前缩放适配，避免文字上下被裁切）
        listf = ttk.Frame(frm, style='App.TFrame')
        listf.pack(fill='both', expand=True)
        pst = ttk.Style(self.root)
        pst.configure('Pick.Treeview',
                      rowheight=max(24, int(24 * self.eff)),
                      font=('Microsoft YaHei UI', 9),
                      background='#ffffff', fieldbackground='#ffffff',
                      foreground=CLR_TEXT)
        pst.map('Pick.Treeview',
                background=[('selected', CLR_PRIMARY)],
                foreground=[('selected', '#ffffff')])
        pst.configure('Pick.Treeview.Heading', font=('Microsoft YaHei UI', 9, 'bold'),
                      background=CLR_CARD, foreground=CLR_PRIMARY, relief='flat')
        cols = ('title', 'proc')
        tree = ttk.Treeview(listf, columns=cols, show='headings', height=14, style='Pick.Treeview')
        tree.heading('title', text='窗口标题')
        tree.heading('proc', text='进程名')
        tree.column('title', width=int(380 * self.eff), minwidth=200, anchor='w', stretch=True)
        tree.column('proc', width=int(190 * self.eff), minwidth=120, anchor='w', stretch=True)
        vsb = ttk.Scrollbar(listf, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        def refresh(*_a):
            tree.delete(*tree.get_children())
            kw = search.get().strip().lower()
            for title, proc in items:
                if kw and kw not in title.lower() and kw not in proc.lower():
                    continue
                tree.insert('', 'end', values=(title, proc))

        refresh()

        # 确定 / 取消
        btnf = ttk.Frame(frm, style='App.TFrame')
        btnf.pack(fill='x', pady=(P(8), 0))
        ttk.Button(btnf, text='取消', command=dlg.destroy).pack(side='right', padx=(P(4), 0))
        ttk.Button(btnf, text='确定', style='Accent.TButton',
                   command=lambda: _apply()).pack(side='right')

        def _apply():
            sel = tree.selection()
            if not sel:
                return
            title, proc = tree.item(sel[0], 'values')
            self.v_win_on.set(True)
            # 有标题优先按标题匹配，否则按进程名
            if title.strip():
                self.v_win_mode.set('title')
                self.v_win_text.set(title)
            else:
                self.v_win_mode.set('process')
                self.v_win_text.set(proc)
            self._chk_win_selected.config(text='已选择：%s [%s]' % (title, proc),
                                          foreground=CLR_PRIMARY)
            dlg.destroy()

        tree.bind('<Double-1>', lambda _e: _apply())
        search.trace_add('write', refresh)
        ent = ttk.Entry(sf, textvariable=search)
        ent.pack(side='left', fill='x', expand=True, padx=(P(4), 0))

        # 设置合理初始尺寸并居中
        dlg.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = min(int(620 * self.eff), sw - 40)
        h = min(int(500 * self.eff), sh - 60)
        dlg.geometry('%dx%d+%d+%d' % (w, h, (sw - w) // 2, (sh - h) // 3))
        dlg.grab_set()
        dlg.focus_set()

    # ---------- 日志 ----------
    def _log(self, msg, tag=None):
        """向日志窗口追加一行（含时间戳），并写文件 logs/dotconnector.log。"""
        try:
            line = '[%s] %s' % (time.strftime('%H:%M:%S'), msg)
            for box in getattr(self, '_log_boxes', []):
                try:
                    box.configure(state='normal')
                    box.insert('end', line + '\n')
                    box.see('end')
                    box.configure(state='disabled')
                except Exception:
                    pass
        except Exception:
            pass
        try:
            d = os.path.join(BASE_DIR, 'logs')
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, 'dotconnector.log'), 'a', encoding='utf-8') as f:
                f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
        except Exception:
            pass

    def _describe_cfg(self, cfg):
        """把一次运行的完整配置整理成日志文本。"""
        mode_name = {'fixed': '固定间隔', 'random': '随机间隔', 'hold': '长按模式'}.get(cfg['mode'], cfg['mode'])
        btn_name = {0: '左键', 1: '中键', 2: '右键'}.get(cfg['button'], '?')
        if cfg['mode'] == 'random':
            speed = '%d~%dms' % (cfg['rmin'], cfg['rmax'])
        elif cfg['mode'] == 'hold':
            speed = '按住%dms/松开%dms' % (cfg['hold'], cfg['gap'])
        else:
            speed = '%dms' % cfg['interval']
        pos = '跟随鼠标' if not cfg['lock'] else '锁定(%d,%d)%s' % (
            cfg['x'], cfg['y'], ' ±5随机' if cfg['rand_offset'] else '')
        stop = []
        if self.v_hotkey_stop.get():
            stop.append('热键')
        if cfg['count_on']:
            stop.append('次数%d' % cfg['count_n'])
        if cfg['end_time']:
            stop.append('倒计时')
        if cfg['until_ts']:
            stop.append('运行到%s' % time.strftime('%H:%M:%S', time.localtime(cfg['until_ts'])))
        win = ''
        if cfg['win_on']:
            win = ' 窗口[%s:%s]' % ('标题' if cfg['win_mode'] == 'title' else '进程', cfg['win_text'])
        return '按键=%s %s %s 位置=%s 停止条件=%s%s' % (
            btn_name, mode_name, speed, pos, ','.join(stop) or '无', win)

    # ---------- 点击控制 ----------
    def _on_start_stop(self):
        with self.lock:
            if self._running:
                self._stop_clicking_locked()
            else:
                self._start_clicking_locked(self._collect_cfg())
        self._refresh_state()

    def _start_clicking_locked(self, cfg):
        if self._running:
            return
        # 窗口检测开启但未选择运行窗口 → 阻止启动并提示
        if cfg.get('win_on') and not cfg.get('win_text'):
            self._log('⚠ 窗口检测已开启，但尚未选择运行窗口，已阻止启动')
            try:
                messagebox.showwarning('提示', '还未选择运行窗口！\n请在「运行状态」页点击"选择运行中的程序…"绑定目标窗口。',
                                       parent=self.root)
            except Exception:
                pass
            return
        self._last_cfg = cfg
        self.engine = ClickEngine(cfg)
        self._finalized = False
        self._manual_stop = False
        self._running = True
        self._run_start_ts = time.time()
        self.engine.start()
        self._log('▶ 开始连点  %s' % self._describe_cfg(cfg))

    def _stop_clicking_locked(self):
        if self._running and self.engine:
            self._manual_stop = True
            self._stop_reason = '手动停止（热键/托盘菜单）'
            self.engine.stop()

    def is_running(self):
        return self._running

    def _hotkey_toggle(self):
        # 停止条件勾选了"热键开启/停止"才响应
        if not self.v_hotkey_stop.get():
            return
        with self.lock:
            if self._running:
                self._stop_clicking_locked()
            else:
                # 直接生效：按热键启动时使用当前界面上的所有设置
                self._start_clicking_locked(self._collect_cfg())

    def tray_action(self, action):
        """托盘线程/热键线程调用（不直接碰 tkinter）。"""
        if action == 'toggle':
            self._hotkey_toggle()
        elif action == 'force':
            self._save_config()
            os._exit(0)
        elif action == 'capture':
            self.q.put('capture')
        elif action == 'show':
            self.q.put('show')
        elif action == 'quit':
            self.q.put('quit')

    def _collect_cfg(self):
        mode = self.v_mode.get()
        button = int(self.v_button.get())
        interval = int(self._clamp_f(self.v_interval, 1, 2000))
        self.v_interval.set(str(interval))
        rmin = int(self._clamp_f(self.v_rmin, 1, 2000))
        rmax = int(self._clamp_f(self.v_rmax, 1, 2000))
        if rmin > rmax:
            rmin, rmax = rmax, rmin
        self.v_rmin.set(str(rmin))
        self.v_rmax.set(str(rmax))
        hold = int(self._clamp_f(self.v_hold, 1, 60000))
        gap = int(self._clamp_f(self.v_gap, 0, 60000))
        self.v_hold.set(str(hold))
        self.v_gap.set(str(gap))
        lock = self.v_strategy.get() == 'lock'
        x = int(self._clamp_f(self.v_x, -32768, 32767))
        y = int(self._clamp_f(self.v_y, -32768, 32767))
        self.v_x.set(str(x))
        self.v_y.set(str(y))
        off = self.v_offset.get() and lock

        count_on = self.v_count_on.get()
        count_n = int(max(1, self._f(self.v_count)))
        self.v_count.set(str(count_n))

        cd_on = self.v_cd_on.get()
        cd_s = int(self._f(self.v_cd_min)) * 60 + int(self._f(self.v_cd_sec))
        cd_s = max(0, cd_s)
        end_time = (time.time() + cd_s) if (cd_on and cd_s > 0) else None

        until_on = self.v_until_on.get()
        until_ts = self._parse_until(self.v_until.get()) if until_on else None

        win_on = self.v_win_on.get()
        win_text = self.v_win_text.get().strip()

        return {
            'mode': mode, 'button': button,
            'interval': interval, 'rmin': rmin, 'rmax': rmax,
            'hold': hold, 'gap': gap,
            'lock': lock, 'x': x, 'y': y, 'rand_offset': off,
            'count_on': count_on, 'count_n': count_n,
            'end_time': end_time, 'until_ts': until_ts,
            'win_on': win_on, 'win_mode': self.v_win_mode.get(), 'win_text': win_text,
        }

    def _parse_until(self, s):
        try:
            parts = [int(p) for p in s.strip().split(':')]
            if len(parts) != 3:
                return None
            h, m, sec = parts
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= sec <= 59):
                return None
            now = time.localtime()
            t = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, h, m, sec, 0, 0, -1))
            if t <= time.time():
                t += 86400
            return t
        except Exception:
            return None

    # ---------- 状态刷新 ----------
    def _poll(self):
        self._refresh_state()
        self.root.after(200, self._poll)

    def _poll_queue(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item == 'show':
                    self._show_window()
                elif item == 'capture':
                    self._capture_pos()
                elif item == 'quit':
                    self._quit()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _refresh_state(self):
        eng = self.engine
        if eng is not None:
            self._count_text.set(str(eng.count))
            if eng.finished.is_set() and not self._finalized:
                self._finalized = True
                self._running = False
                reason = self._stop_reason if self._manual_stop else self._guess_stop_reason()
                dur = (time.time() - self._run_start_ts) if self._run_start_ts else 0.0
                self._log('■ 停止连点  本次 %d 次，耗时 %.1f 秒，原因：%s' % (eng.count, dur, reason))
                # 详细坐标汇总
                coord_txt = self._summarize_coords(eng.coord_counts)
                if coord_txt:
                    self._log('  点击坐标: %s' % coord_txt)
                self._total += eng.count
                self._total_text.set('历史累计: %d 次' % self._total)
                self._save_config()
        if self._running:
            paused = bool(eng and eng.paused)
            if paused and not self._last_paused:
                self._log('⏸ 目标窗口失焦，自动暂停')
            elif not paused and self._last_paused:
                self._log('▶ 目标窗口恢复，继续连点')
            self._last_paused = paused
            self._set_status(True, paused)
        else:
            if self._last_paused:
                self._log('⏸ 连点已停止，暂停状态清除')
            self._last_paused = False
            self._set_status(False)
        # 运行状态页：本次 / 历史累计 / 运行时长 / 最近点击坐标
        if getattr(self, '_lbl_counts', None) is not None:
            dur_txt = ''
            if self._running and self._run_start_ts:
                dur = time.time() - self._run_start_ts
                dur_txt = '    已运行 %d 分 %d 秒' % (dur // 60, int(dur) % 60)
            coord_txt = ''
            if self._running and eng is not None and eng.last_coord:
                coord_txt = '    最近坐标 (%d, %d)' % eng.last_coord
            self._lbl_counts.config(text='本次 %s 次    历史累计 %d 次%s%s'
                                         % (self._count_text.get(), self._total, dur_txt, coord_txt))
        # 热键提示（如存在）
        if getattr(self, '_lbl_hot', None) is not None:
            parts = ['%s %s' % (fmt_hotkey(m, v), HK_LABELS[k])
                     for k, (m, v) in self.hotkey_cfg.items()]
            base = '热键:  ' + '   '.join(parts)
            if not self.hotkey_registered:
                base += '    [注册失败，可能被占用]'
            self._lbl_hot.config(text=base)

    def _guess_stop_reason(self):
        """根据上次配置推断引擎自然停止的原因。"""
        try:
            cfg = self._last_cfg or {}
            if cfg.get('count_on'):
                return '点击次数已达成'
            if cfg.get('end_time'):
                return '倒计时结束'
            if cfg.get('until_ts'):
                return '运行到指定时间'
        except Exception:
            pass
        return '停止'

    def _summarize_coords(self, coord_counts):
        """把坐标统计整理为日志文本，如 '锁定坐标 (400,300) × 25 次'。"""
        try:
            if not coord_counts:
                return ''
            # 排序：次数降序，坐标升序
            items = sorted(coord_counts.items(), key=lambda kv: (-kv[1], kv[0]))
            total = sum(coord_counts.values())
            parts = []
            if len(items) == 1 and len(coord_counts) == 1:
                (x, y), n = items[0]
                return '(%d,%d) × %d 次' % (x, y, n)
            for (x, y), n in items[:5]:
                parts.append('(%d,%d)×%d' % (x, y, n))
            if len(items) > 5:
                parts.append('…共%d个坐标' % len(items))
            return '共%d次，主要坐标: %s' % (total, ' '.join(parts))
        except Exception:
            return ''
        # 启动回显：config 里已有检测目标时，在"已选择"标签显示
        if getattr(self, '_chk_win_selected', None) is not None:
            try:
                if not self._chk_win_selected.cget('text'):
                    wtxt = self.v_win_text.get().strip()
                    if wtxt:
                        self._chk_win_selected.config(text='已选择：%s' % wtxt,
                                                      foreground=CLR_PRIMARY)
            except Exception:
                pass

    def _set_status(self, running, paused=False):
        if running:
            if paused:
                self._status_text.set('运行中（窗口失焦暂停）')
                color = CLR_WARN
            else:
                self._status_text.set('运行中')
                color = CLR_OK
        else:
            self._status_text.set('已停止')
            color = CLR_STOP
        if self._lbl_status is not None:
            self._lbl_status.config(text=self._status_text.get(), foreground=color)
        # 窗口标题带状态标记 → 任务栏可直观看到是否在运行
        try:
            if running:
                self.root.title('● %s - %s' % (self._status_text.get(), APP_NAME))
            else:
                self.root.title(APP_NAME)
        except Exception:
            pass
        # 状态灯圆点同步变色
        if getattr(self, '_lamp', None) is not None:
            try:
                self._lamp.itemconfig(self._lamp_id, fill=color)
            except Exception:
                pass
        key = (running, paused)
        if key != self._last_icon:
            self._last_icon = key
            if hasattr(self, 'tray'):
                self.tray.set_state(running, paused)

    def _show_window(self):
        try:
            self.root.deiconify()
            self.root.state('normal')
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(120, lambda: self.root.attributes('-topmost', False))
        except Exception:
            pass

    # ---------- 缩放 / 置顶计数窗 ----------
    def _on_scale_change(self):
        self._save_config()
        self._rebuild_ui()

    def _rebuild_ui(self):
        top_wanted = self.v_top.get()
        self._destroy_top()
        cur_page = getattr(self, '_current_page', '点击设置')
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        self.eff = (self.dpi / 96.0) * self.scale_opt.get() * self._dpi_factor()
        self._apply_font_scale()
        # 保留日志内容（重建后恢复）
        log_content = ''
        for box in getattr(self, '_log_boxes', []):
            try:
                log_content += box.get('1.0', 'end-1c') + '\n'
            except Exception:
                pass
        for child in self.root.winfo_children():
            child.destroy()
        self._lbl_status = None
        self._lbl_hot = None
        self._lbl_counts = None
        self._tab_btns = {}
        self._pages = {}
        self._hk_entries = {}
        self._hk_status_lbl = None
        self._log_box = None
        self._log_boxes = []
        self._build_ui()
        if log_content:
            for box in getattr(self, '_log_boxes', []):
                try:
                    box.configure(state='normal')
                    box.insert('1.0', log_content.strip())
                    box.see('end')
                    box.configure(state='disabled')
                except Exception:
                    pass
        self._apply_minsize()
        self._remove_maximize()
        if w > 40 and h > 40:
            self.root.geometry('%dx%d' % (w, h))
        self.show_page(cur_page)
        self._sync_enabled()
        self._sync_mode_fields()
        self._update_hint()
        self._refresh_state()
        if top_wanted:
            self._maybe_create_top()

    def _on_top_toggled(self, *a):
        if self.v_top.get():
            self._maybe_create_top()
        else:
            self._destroy_top()

    def _maybe_create_top(self):
        if self._top is not None:
            return
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes('-topmost', True)
        top.attributes('-alpha', 0.92)
        top.configure(bg='#2b2b2b')
        bar = tk.Frame(top, bg='#2b2b2b', cursor='fleur')
        bar.pack(fill='x')
        title = tk.Label(bar, text='连点计数', fg='#9aa0a6', bg='#2b2b2b',
                         font=('Microsoft YaHei UI', 9))
        title.pack(side='left', padx=6, pady=2)
        close = tk.Button(bar, text='✕', command=self._close_top, bg='#2b2b2b', fg='#cccccc',
                          relief='flat', bd=0, activebackground='#4a4a4a', cursor='hand2',
                          font=('Microsoft YaHei UI', 9))
        close.pack(side='right', padx=2)
        val = tk.Label(top, textvariable=self._count_text, fg='#4fc3f7', bg='#2b2b2b',
                       font=('Consolas', int(round(22 * self.scale_opt.get()))))
        val.pack(padx=10, pady=(0, 6))

        def drag_start(e):
            self._top_drag = (e.x_root - top.winfo_x(), e.y_root - top.winfo_y())

        def drag_move(e):
            if self._top_drag:
                nx = e.x_root - self._top_drag[0]
                ny = e.y_root - self._top_drag[1]
                top.geometry('+%d+%d' % (nx, ny))
                self._top_pos = (nx, ny)   # 记住拖拽位置，重开后沿用

        bar.bind('<Button-1>', drag_start)
        bar.bind('<B1-Motion>', drag_move)
        title.bind('<Button-1>', drag_start)
        title.bind('<B1-Motion>', drag_move)

        top.update_idletasks()
        # 默认置于屏幕右上角；若用户拖拽过则沿用上次位置
        if getattr(self, '_top_pos', None):
            x, y = self._top_pos
        else:
            sw = user32.GetSystemMetrics(0)          # 物理屏幕宽度（DPI-aware 准确）
            sh = user32.GetSystemMetrics(1)          # 物理屏幕高度
            tw = max(10, top.winfo_reqwidth())
            th = max(10, top.winfo_reqheight())
            x = max(0, sw - tw - self.P(24))
            y = max(0, self.P(24))
            self._top_pos = (x, y)
        top.geometry('+%d+%d' % (x, y))
        self._top = top

    def _close_top(self):
        self.v_top.set(False)
        self._destroy_top()

    def _destroy_top(self):
        if self._top is not None:
            try:
                self._top.destroy()
            except Exception:
                pass
            self._top = None

    # ---------- 配置 ----------
    def _load_config(self):
        cp = configparser.ConfigParser()
        try:
            if os.path.exists(CONFIG_PATH):
                cp.read(CONFIG_PATH, encoding='utf-8')
        except Exception:
            cp = configparser.ConfigParser()
        g = cp['general'] if cp.has_section('general') else {}
        c = cp['click'] if cp.has_section('click') else {}
        p = cp['position'] if cp.has_section('position') else {}
        s = cp['stop'] if cp.has_section('stop') else {}
        w = cp['window'] if cp.has_section('window') else {}
        v = cp['view'] if cp.has_section('view') else {}
        h = cp['hotkey'] if cp.has_section('hotkey') else {}

        def gi(sec, key, default):
            return sec.get(key, str(default))

        self._total = int(float(gi(g, 'total', 0)))
        # 默认缩放档：高 DPI 系统默认 200%，常规系统默认 100%
        self.scale_opt.set(float(gi(g, 'scale', 2.0 if self.dpi > 96 else 1.0)))
        self.v_button.set(int(gi(c, 'button', 0)))
        self.v_mode.set(gi(c, 'mode', 'fixed'))
        self.v_interval.set(gi(c, 'interval', '100'))
        self.v_rmin.set(gi(c, 'random_min', '1'))
        self.v_rmax.set(gi(c, 'random_max', '2000'))
        self.v_hold.set(gi(c, 'hold', '200'))
        self.v_gap.set(gi(c, 'gap', '100'))
        self.v_strategy.set(gi(p, 'strategy', 'follow'))
        self.v_x.set(gi(p, 'x', '400'))
        self.v_y.set(gi(p, 'y', '300'))
        self.v_offset.set(gi(p, 'random_offset', 'false') == 'true')
        self.v_count_on.set(gi(s, 'count_enabled', 'false') == 'true')
        self.v_count.set(gi(s, 'count', '100'))
        self.v_cd_on.set(gi(s, 'countdown_enabled', 'false') == 'true')
        self.v_cd_min.set(gi(s, 'countdown_min', '0'))
        self.v_cd_sec.set(gi(s, 'countdown_sec', '10'))
        self.v_until_on.set(gi(s, 'until_enabled', 'false') == 'true')
        self.v_until.set(gi(s, 'until', '00:00:00'))
        self.v_hotkey_stop.set(gi(s, 'hotkey_stop', 'true') == 'true')
        self.v_win_on.set(gi(w, 'check_enabled', 'true') == 'true')
        self.v_win_mode.set(gi(w, 'match', 'title'))
        self.v_win_text.set(gi(w, 'target', ''))
        self.v_top.set(gi(v, 'top_counter', 'false') == 'true')
        self.v_resize.set(gi(v, 'resize_enabled', 'false') == 'true')
        # 热键自定义配置
        for hk in ('toggle', 'force', 'capture'):
            s2 = h.get(hk, '').strip()
            if s2:
                try:
                    m, v = s2.split(',')
                    self.hotkey_cfg[hk] = [int(m), int(v)]
                except Exception:
                    pass

    def _save_config(self):
        try:
            cp = configparser.ConfigParser()
            cp['general'] = {
                'version': VERSION,
                'total': str(int(self._total)),
                'scale': str(self.scale_opt.get()),
            }
            cp['click'] = {
                'button': str(int(self.v_button.get())),
                'mode': self.v_mode.get(),
                'interval': self.v_interval.get(),
                'random_min': self.v_rmin.get(),
                'random_max': self.v_rmax.get(),
                'hold': self.v_hold.get(),
                'gap': self.v_gap.get(),
            }
            cp['position'] = {
                'strategy': self.v_strategy.get(),
                'x': self.v_x.get(),
                'y': self.v_y.get(),
                'random_offset': 'true' if self.v_offset.get() else 'false',
            }
            cp['stop'] = {
                'count_enabled': 'true' if self.v_count_on.get() else 'false',
                'count': self.v_count.get(),
                'countdown_enabled': 'true' if self.v_cd_on.get() else 'false',
                'countdown_min': self.v_cd_min.get(),
                'countdown_sec': self.v_cd_sec.get(),
                'until_enabled': 'true' if self.v_until_on.get() else 'false',
                'until': self.v_until.get(),
                'hotkey_stop': 'true' if self.v_hotkey_stop.get() else 'false',
            }
            cp['window'] = {
                'check_enabled': 'true' if self.v_win_on.get() else 'false',
                'match': self.v_win_mode.get(),
                'target': self.v_win_text.get(),
            }
            cp['view'] = {
                'top_counter': 'true' if self.v_top.get() else 'false',
                'resize_enabled': 'true' if self.v_resize.get() else 'false',
            }
            cp['hotkey'] = {
                'toggle': '%d,%d' % (self.hotkey_cfg['toggle'][0], self.hotkey_cfg['toggle'][1]),
                'force': '%d,%d' % (self.hotkey_cfg['force'][0], self.hotkey_cfg['force'][1]),
                'capture': '%d,%d' % (self.hotkey_cfg['capture'][0], self.hotkey_cfg['capture'][1]),
            }
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                cp.write(f)
        except Exception:
            pass

    # ---------- 退出 ----------
    def _quit(self):
        try:
            with self.lock:
                if self.engine and not self._finalized:
                    self._total += self.engine.count
                    self._finalized = True
                if self.engine:
                    self.engine.stop()
            self._save_config()
        except Exception:
            pass
        self._destroy_top()
        if hasattr(self, 'tray') and self.tray.tid:
            user32.PostThreadMessageW(self.tray.tid, WM_QUIT, 0, 0)
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)


# ---------------------------------------------------------------------------
# 自测（模拟点击，不碰真实鼠标）
# ---------------------------------------------------------------------------
def run_selftest():
    print('DotConnector 引擎自测（模拟模式，不产生真实点击）...')
    ok = True

    def check(name, cond):
        nonlocal ok
        print(('  PASS  ' if cond else '  FAIL  ') + name)
        if not cond:
            ok = False

    base = dict(mode='fixed', button=0, interval=30, rmin=1, rmax=2000,
                hold=100, gap=50, lock=True, x=100, y=100, rand_offset=False,
                count_on=False, count_n=10, end_time=None, until_ts=None,
                win_on=False, win_mode='title', win_text='')

    # 1. 固定间隔 + 次数
    cfg = dict(base); cfg.update(interval=30, count_on=True, count_n=25)
    e = ClickEngine(cfg, sim=True)
    t0 = time.monotonic(); e.start(); e.finished.wait(15)
    dt = time.monotonic() - t0
    check('固定间隔25次 → count=%d' % e.count, e.count == 25)
    check('25次×30ms≈0.75s, 实际 %.3fs' % dt, 0.5 <= dt <= 2.0)

    # 2. 随机间隔
    cfg = dict(base); cfg.update(mode='random', rmin=1, rmax=10, count_on=True, count_n=60)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check('随机间隔60次 → count=%d' % e.count, e.count == 60)

    # 3. 长按模式
    cfg = dict(base); cfg.update(mode='hold', hold=15, gap=5, count_on=True, count_n=12)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check('长按模式12次 → count=%d' % e.count, e.count == 12)

    # 4. 倒计时停止
    cfg = dict(base); cfg.update(interval=5, count_on=False, end_time=time.time() + 0.3)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check('倒计时0.3s自动停止 → count=%d' % e.count, e.finished.is_set() and e.count >= 1)

    # 5. 定时停止
    cfg = dict(base); cfg.update(interval=5, count_on=False, until_ts=time.time() + 0.3)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check('定时0.3s自动停止 → count=%d' % e.count, e.finished.is_set() and e.count >= 1)

    # 6. 窗口检测暂停
    cfg = dict(base); cfg.update(win_on=True, win_mode='title', win_text='__NEVER_MATCH_XYZ__',
                                 count_on=False, end_time=None, interval=10)
    e = ClickEngine(cfg, sim=True)
    e.start(); time.sleep(0.4); e.stop(); e.finished.wait(5)
    check('窗口检测(不匹配)暂停 → count=%d paused=%s' % (e.count, e.paused),
          e.count == 0 and e.paused is True)

    # 7. 快速停止响应
    cfg = dict(base); cfg.update(interval=200, count_on=False, end_time=None)
    e = ClickEngine(cfg, sim=True)
    e.start(); time.sleep(0.1); e.stop()
    t0 = time.monotonic(); e.finished.wait(5); dt = time.monotonic() - t0
    check('运行中手动停止, 0.1s内响应' if dt < 0.1 else '停止响应耗时 %.3fs' % dt, dt < 0.1)

    print('自测结果: ' + ('全部通过' if ok else '存在失败'))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
def main():
    if '--selftest' in sys.argv:
        return run_selftest()
    set_dpi_aware()
    if '--smoke' in sys.argv:
        root = tk.Tk()
        app = App(root)
        root.after(1200, lambda: (
            print('SMOKE OK  hwnd=%s  hotkey_registered=%s  tray_tid=%d' % (
                bool(app.tray.hwnd), app.hotkey_registered, app.tray.tid), flush=True),
            os._exit(0)))
        root.mainloop()
        return 0
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
