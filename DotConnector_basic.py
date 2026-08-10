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
import configparser
import webbrowser

import tkinter as tk
import tkinter.scrolledtext as scrolledtext
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from tkinter import ttk
from tkinter import font as tkfont


# ---------------------------------------------------------------------------
# 国际化：简体中文 / English
# ---------------------------------------------------------------------------
LANG = 'zh'    # 'zh' / 'en'

I18N = {
    '  点击坐标: %s': '  coords: %s',
    ' - 已停止': ' - Stopped',
    ' ±5随机': ' ±5rand',
    ' 窗口[%s:%s]': ' win[%s:%s]',
    '# DotConnector 运行日志\n\n> 导出时间：%s\n\n```\n%s\n```\n': '# DotConnector Log\n\n> Exported: %s\n\n```\n%s\n```\n',
    '%.1f秒': '%.1fs',
    '%d分%d秒': '%dm %ds',
    '%s 文件': '%s file',
    '(%d,%d) × %d 次': '(%d,%d) × %d',
    '(时:分:秒, 到点自动停止)': '(hh:mm:ss, stops at that time)',
    '1秒100下': '100/s',
    '1秒10下': '10/s',
    '1秒1下': '1/s',
    '1秒20下': '20/s',
    '1秒50下': '50/s',
    '25次×30ms≈0.75s, 实际 %.3fs': '25 clicks × 30ms ≈ 0.75s, actual %.3fs',
    '== DotConnector v%s 启动于 %s ==\n': '== DotConnector v%s started at %s ==\n',
    'DotConnector 已在运行中！\n请勿重复打开，已为您切换到正在运行的实例。': 'DotConnector is already running!\nPlease do not open it again; switched to the running instance.',
    'DotConnector 引擎自测（模拟模式，不产生真实点击）...': 'DotConnector engine self-test (simulated, no real clicks)...',
    'DotConnector 运行日志\n导出时间：%s\n%s\n': 'DotConnector Log\nExported: %s\n%s\n',
    'DotConnector 连点器': 'DotConnector Auto Clicker',
    'XML': 'XML',
    'XML 脚本': 'XML script',
    '…共%d个坐标': '…%d positions',
    '≈ 1秒 %.1f ~ %.1f 下': '≈ %.1f–%.1f clicks/s',
    '≈ 1秒 %.1f 下': '≈ %.1f clicks/s',
    '⏸ 目标窗口失焦，自动暂停': 'Target window unfocused, paused',
    '⏸ 连点已停止，暂停状态清除': 'Clicking stopped, pause cleared',
    '① 点击模式': '1. Click Mode',
    '② 鼠标按键': '2. Mouse Button',
    '③ 点击速度': '3. Click Speed',
    '④ 点击位置': '4. Click Position',
    '⑤ 停止条件': '5. Stop Condition',
    '⑥ 窗口检测': '6. Window Detection',
    '■ 停止播放脚本': 'Playback stopped',
    '■ 停止连点  本次 %d 次，耗时 %.1f 秒，原因：%s': 'Stopped clicking: %d this session, %.1fs, reason: %s',
    '■ 录制结束，共 %d 条动作': 'Recording finished, %d actions',
    '▶ 开始播放脚本 %s（倍率%.2fx，循环%s%s）': '▶ Playing script %s (rate %.2fx, loop %s%s)',
    '▶ 开始连点  %s': '▶ Start clicking  %s',
    '▶ 目标窗口恢复，继续连点': 'Target window focused, resumed',
    '● 开始录制脚本（%s，上限 %d 步）': '● Recording script (%s, max %d steps)',
    '⚠ 录制中，请先停止录制再播放': 'Recording in progress — stop it before playing',
    '⚠ 播放中，请先停止播放再录制': 'Playback in progress — stop it before recording',
    '⚠ 窗口检测已开启，但尚未选择运行窗口，已阻止启动': 'Window detection is on but no window selected — start blocked',
    '⚠ 脚本文件不存在：%s': 'Script file not found: %s',
    '⚠ 请先在脚本列表中选择一个脚本': 'Select a script from the list first',
    '✔ 脚本已保存：%s': '✔ Script saved: %s',
    '✔ 脚本播放完成': 'Script playback finished',
    '不循环': 'no loop',
    '不自动停止': 'No auto-stop',
    '与[%s]冲突，请换一个': 'Conflicts with [%s], choose another',
    '中键': 'Middle',
    '中键按下': 'Middle down',
    '中键松开': 'Middle up',
    '二进制': 'Binary',
    '二进制脚本': 'Binary script',
    '仅当指定窗口激活时连点，否则自动暂停': 'Only click when the target window is active, else pause',
    '仅鼠标': 'mouse only',
    '保存录制脚本': 'Save Recording',
    '保存脚本失败：%s': 'Failed to save script: %s',
    '倒序': 'Desc',
    '倒计时': 'countdown',
    '倒计时0.3s自动停止 → count=%d': 'Countdown 0.3s auto-stop → count=%d',
    '倒计时:': 'Countdown:',
    '倒计时结束': 'Countdown finished',
    '停止': 'Stopped',
    '停止响应耗时 %.3fs': 'Stop response took %.3fs',
    '停止连点': 'Stop Clicking',
    '全部通过': 'All passed',
    '共%d次，主要坐标: %s': '%d total, main coords: %s',
    '关闭': 'Close',
    '分': 'min',
    '删除历史记录': 'Delete History',
    '删除失败': 'Delete failed',
    '删除选中': 'Delete Selected',
    '刷新': 'Refresh',
    '历史日志文件': 'Log Files',
    '历史累计: %d 次': 'Total: %d',
    '历史累计: 0 次': 'Total: 0',
    '历史记录': 'History',
    '历史记录 - %s': 'History - %s',
    '历史记录（记录每次运行日志到 logs/ 会话文件）': 'History (save session logs to logs/ per run)',
    '双击选择要检测的窗口（自动填充：有标题用标题，否则用进程名）': 'Double-click a window to select (auto: title if present, else process name)',
    '取消': 'Cancel',
    '只执行一轮': 'once',
    '只执行一轮脚本': 'Run script once',
    '右键': 'Right',
    '右键按下': 'Right down',
    '右键松开': 'Right up',
    '名称': 'Name',
    '后监听下一次按键组合作为新热键。': 'listen for the next key combo as the new hotkey.',
    '含键盘': 'with keyboard',
    '启动/停止': 'Start/Stop',
    '固定间隔': 'Fixed',
    '固定间隔25次 → count=%d': 'Fixed 25 clicks → count=%d',
    '失控应急，立即结束进程': 'Emergency: immediately terminates the process',
    '字体:': 'Font:',
    '存在失败': 'Failed',
    '定时0.3s自动停止 → count=%d': 'Scheduled 0.3s auto-stop → count=%d',
    '导入/导出脚本：可放入或移动文件到软件同名目录下的 Scripts 文件夹': 'Import/export scripts: put or move files into the Scripts folder next to the program',
    '导出 MD': 'Export MD',
    '导出 TXT': 'Export TXT',
    '导出日志失败：%s': 'Export log failed: %s',
    '导出运行日志': 'Export Log',
    '左键': 'Left',
    '左键按下': 'Left down',
    '左键松开': 'Left up',
    '已停止': 'Stopped',
    '已删除历史日志：%s': 'Deleted history log: %s',
    '已取消': 'Cancelled',
    '已启用': 'enabled',
    '已捕获当前坐标 (%d, %d)': 'Captured position (%d, %d)',
    '已更新，立即生效': 'Updated, takes effect now',
    '已运行 %d 分 %d 秒': 'Running %dm %ds',
    '已选择：%s [%s]': 'Selected: %s [%s]',
    '常用:': 'Presets:',
    '开始/停止录制：按 %s': 'Start/Stop recording: %s',
    '开始/停止播放：按 %s': 'Start/Stop playback: %s',
    '开始连点': 'Start Clicking',
    '强制退出': 'Force Quit',
    '强制退出:': 'Force quit:',
    '强制退出软件': 'Force Quit',
    '强制退出软件热键': 'Force-Quit Hotkey',
    '当前版本': 'Version',
    '录制中…': 'Recording…',
    '循环次数:': 'Loops:',
    '循环轮数：%d/%d': 'Loop %d/%d',
    '循环轮数：%d/∞': 'Loop %d/∞',
    '循环间隔:': 'Loop gap:',
    '恢复默认热键': 'Restore Default Hotkeys',
    '手动停止': 'Manual stop',
    '手动停止（热键/托盘菜单）': 'Manual stop (hotkey/tray menu)',
    '打开历史记录失败：%s': 'Failed to open history: %s',
    '打开日志文件夹': 'Open Log Folder',
    '打开脚本文件夹': 'Open Scripts Folder',
    '打开脚本文件夹失败：%s': 'Failed to open scripts folder: %s',
    '按 %s 捕获当前坐标': 'Press %s to capture position',
    '按下': 'Press',
    '按住 %.0f ms / 松开 %.0f ms': 'Hold %.0f ms / release %.0f ms',
    '按住%dms/松开%dms': 'Hold %dms / release %dms',
    '按住(ms):': 'Press (ms):',
    '按键 %s': 'Key %s',
    '按键=%s %s %s 位置=%s 停止条件=%s%s': 'button=%s %s %s pos=%s stop=%s%s',
    '捕获坐标': 'Capture Position',
    '排序:': 'Sort:',
    '提示': 'Notice',
    '搜索:': 'Search:',
    '无': 'none',
    '无限循环': 'Infinite',
    '日志为空，无可导出内容': 'Log is empty, nothing to export',
    '日志内容': 'Content',
    '日志已导出：%s': 'Log exported: %s',
    '日志已清空': 'Log cleared',
    '日志设置': 'Log Settings',
    '时间': 'Time',
    '显示主窗口': 'Show Main Window',
    '更多设置': 'More Settings',
    '最大(ms):': 'Max (ms):',
    '最大步骤:': 'Max steps:',
    '最小(ms):': 'Min (ms):',
    '最近坐标 (%d, %d)': 'Last pos (%d, %d)',
    '未发现可选的运行中窗口': 'No running windows found',
    '未启用': 'not enabled',
    '本次:': 'Session:',
    '松开': 'Release',
    '松开(ms):': 'Release (ms):',
    '松键 %s': 'Release %s',
    '标题': 'Title',
    '次': 'times',
    '次数%d': 'count%d',
    '正在设置[%s]，请按新的组合键…': 'Setting [%s], press the new combo…',
    '正序': 'Asc',
    '清空日志': 'Clear Log',
    '点击"设置"自定义热键': 'Click "Set" to customize a hotkey',
    '点击次数:': 'Click count:',
    '点击次数已达成': 'Click count reached',
    '点击次数记录：': 'Click Count:',
    '热键': 'hotkey',
    '热键 %s 开启/停止（固定开启）': 'Hotkey %s start/stop (always on)',
    '热键[%s]已改为 %s': 'Hotkey [%s] changed to %s',
    '热键已恢复默认': 'Hotkeys restored to default',
    '热键设置': 'Hotkeys',
    '热键说明': 'Hotkey Guide',
    '界面拖拽（可调整窗口大小）': 'Resizable window (drag to resize)',
    '界面缩放': 'UI Scale',
    '语言': 'Language',
    '语言已切换': 'Language switched',
    '简体中文': '简体中文',
    'English': 'English',
    '相对移动（不跳到录制坐标）': 'Relative movement (no jump to recorded pos)',
    '确定': 'OK',
    '确定删除日志文件 %s 吗？': 'Delete log file %s?',
    '秒': 'sec',
    '移动': 'Move',
    '程序已启动，按热键（默认 Ctrl+F9）启动/停止连点': 'Started. Press hotkey (default Ctrl+F9) to start/stop clicking',
    '空闲': 'Idle',
    '窗口标题': 'Window Title',
    '窗口检测(不匹配)暂停 → count=%d paused=%s': 'Window detect (no match) paused → count=%d paused=%s',
    '等待': 'Wait',
    '置顶位置已恢复默认（左上角）': 'On-top position reset to default (top-left)',
    '置顶位置恢复默认': 'Reset Top Position',
    '置顶显示': 'Always on Top',
    '脚本:': 'Script:',
    '脚本:%s  急停:%s': 'Script:%s  Stop:%s',
    '脚本:%s  急停:%s  %s': 'Script:%s  Stop:%s  %s',
    '脚本:%s  急停:%s  只执行一轮': 'Script:%s  Stop:%s  once',
    '脚本录制': 'Record Script',
    '脚本播放': 'Play Script',
    '脚本模式': 'Script Mode',
    '脚本模式热键': 'Script-Mode Hotkeys',
    '脚本模式置顶进度显示': 'Script-Mode On-Top Progress',
    '脚本说明：录制 %d 步，总时长 %s，键盘录制 %s': 'Info: %d steps, %s duration, keyboard %s',
    '脚本运行记录：': 'Script Runs:',
    '脚本：%s（无法读取）': 'Script: %s (unreadable)',
    '自测结果: ': 'Self-test result: ',
    '记录格式:': 'Format:',
    '记录键盘输入（常用键+符号键）': 'Record keyboard input (common + symbol keys)',
    '设置': 'Set',
    '请先完成当前热键设置': 'Please finish the current hotkey setup first',
    '请按键…': 'Press keys…',
    '读取失败：%s': 'Failed to read: %s',
    '跟随鼠标': 'Follow Mouse',
    '软件下载地址：%s': 'Download: %s',
    '运行中': 'Running',
    '运行中手动停止, 0.1s内响应': 'Manual stop responds within 0.1s',
    '运行中（窗口失焦暂停）': 'Running (paused: window unfocused)',
    '运行到%s': 'until %s',
    '运行到:': 'Run until:',
    '运行到指定时间': 'Reached scheduled time',
    '运行日志': 'Log',
    '运行状态': 'Status',
    '还未选择运行窗口！\n请在「连点模式」页点击"选择运行中的程序…"绑定目标窗口。': 'No target window selected!\nBind one in "Click Mode" → "Select running program…".',
    '进程': 'Process',
    '进程名': 'Process Name',
    '连点:%s  急停:%s': 'Click:%s  Stop:%s',
    '连点模式': 'Click Mode',
    '连点模式热键': 'Click-Mode Hotkeys',
    '连点模式置顶计数显示': 'Click-Mode On-Top Counter',
    '退出': 'Exit',
    '选择运行中的程序': 'Select Running Program',
    '选择运行中的程序…': 'Select running program…',
    '透明度:': 'Opacity:',
    '速度倍率:': 'Speed rate:',
    '锁定(%d,%d)%s': 'locked(%d,%d)%s',
    '锁定后每次点击 ±5 像素随机偏移': 'Randomize each click by ±5px when locked',
    '锁定坐标': 'Locked',
    '长按模式': 'Hold',
    '长按模式12次 → count=%d': 'Hold 12 clicks → count=%d',
    '间隔(ms):': 'Interval (ms):',
    '随机间隔': 'Random',
    '随机间隔60次 → count=%d': 'Random 60 clicks → count=%d',
    '顺序:': 'Order:',
    '，间隔%dms': ', gap %dms',
}


def tr(text):
    """按当前语言返回文本；英文未收录时回退原文。"""
    if LANG == 'en':
        return I18N.get(text, text)
    return text

APP_NAME = 'DotConnector 连点器'
VERSION = '1.1.0'


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
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
GA_ROOT = 2
GCL_HICON = -14
GCL_HICONSM = -34
RDW_FRAME = 0x0400
RDW_INVALIDATE = 0x0001
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SW_RESTORE = 9
SW_SHOWMINNOACTIVE = 7
SW_SHOWNOACTIVATE = 4
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
VK_F11 = 0x7A
VK_F12 = 0x7B
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_ALREADY_EXISTS = 183
MB_OK = 0x00000000
MB_ICONWARNING = 0x00000030
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000

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
    'record':  [MOD_CONTROL | MOD_SHIFT, VK_F11],   # 脚本录制/停止
    'play':    [MOD_CONTROL | MOD_SHIFT, VK_F12],   # 脚本播放/停止
}
HK_LABELS = {'toggle': '启动/停止', 'force': '强制退出', 'capture': '捕获坐标',
             'record': tr('脚本录制'), 'play': tr('脚本播放')}

# ---------------------------------------------------------------------------
# 脚本录制/播放 常量
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.join(BASE_DIR, 'Scripts')      # 脚本保存目录
SCRIPT_MAGIC = b'DCS1'                              # 二进制文件魔数
SCRIPT_VERSION = 1                                  # 脚本文件格式版本
SCRIPT_MAX_ACTIONS = 50000                          # 录制动作缓冲上限（预分配，可自定义）
SCRIPT_MAX_MOVE_POINTS = 50000                      # 最多移动点
SCRIPT_MOVE_THRESHOLD = 5                           # 移动抽稀：位移阈值(px)
SCRIPT_MOVE_MIN_INTERVAL = 50                       # 移动抽稀：最短间隔(ms)

# 脚本文件格式：xml（结构化，默认）/ dcs（轻量二进制）

# 动作类型
ACT_MOVE = 0        # 鼠标移动（轨迹点）
ACT_DOWN = 1        # 鼠标按键按下（btn 在 flags）
ACT_UP = 2          # 鼠标按键释放
ACT_KEYDOWN = 3     # 键盘按下（vk 在 flags）
ACT_KEYUP = 4       # 键盘释放
ACT_WAIT = 5        # 等待（显式延迟）

ACT_NAMES = {ACT_MOVE: 'move', ACT_DOWN: 'down', ACT_UP: 'up',
             ACT_KEYDOWN: 'keydown', ACT_KEYUP: 'keyup', ACT_WAIT: 'wait'}

# 每条动作 10 字节：<BBhhI = type(1) flags(1) x(2) y(2) delay(4)
ACT_STRUCT = struct.Struct('<BBhhI')
ACT_SIZE = ACT_STRUCT.size

# 常用键集合（键盘录制可选，默认不启用；含数字/字母/F键/功能键/符号键）
COMMON_VKS = list(range(0x30, 0x3A)) + list(range(0x41, 0x5B)) \
    + [0x70 + i for i in range(12)] \
    + [0x08, 0x09, 0x0D, 0x1B, 0x20, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
       0x2D, 0x2E, 0x90, 0x14, 0x10, 0x11, 0x12, 0x91]
# 符号键（需求4）：`-=[]\;',./  及其 Shift 组合所在键位
COMMON_VKS += [0xC0, 0xBD, 0xBB, 0xDB, 0xDD, 0xDC, 0xBA, 0xDE, 0xBC, 0xBE, 0xBF]

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

# 动作文字描述（置顶进度显示"下一步操作"用）
def act_desc(typ, flags):
    """把一条动作转成简短中文描述。"""
    if typ == ACT_MOVE:
        return tr('移动')
    if typ == ACT_DOWN:
        return {0: tr('左键按下'), 1: tr('中键按下'), 2: tr('右键按下')}.get(flags, tr('按下'))
    if typ == ACT_UP:
        return {0: tr('左键松开'), 1: tr('中键松开'), 2: tr('右键松开')}.get(flags, tr('松开'))
    if typ == ACT_KEYDOWN:
        return tr('按键 %s') % vk_to_name(flags)
    if typ == ACT_KEYUP:
        return tr('松键 %s') % vk_to_name(flags)
    if typ == ACT_WAIT:
        return tr('等待')
    return '?'


def save_script_xml(path, actions, count):
    """把动作列表以结构化 XML 格式写入文件。"""
    import xml.etree.ElementTree as ET
    root = ET.Element('DotConnectorScript', version=str(SCRIPT_VERSION))
    act_el = ET.SubElement(root, 'actions', count=str(count))
    for i in range(count):
        typ, flags, x, y, delay = actions[i]
        a = ET.SubElement(act_el, 'action')
        a.set('type', ACT_NAMES.get(typ, str(typ)))
        a.set('flags', str(flags))
        a.set('x', str(x))
        a.set('y', str(y))
        a.set('delay', str(delay))
    tree = ET.ElementTree(root)
    tree.write(path, encoding='utf-8', xml_declaration=True)


def load_script_xml(path):
    """从 XML 脚本文件读取动作列表，返回 [(typ, flags, x, y, delay), ...] 或 None。"""
    import xml.etree.ElementTree as ET
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        if root.tag != 'DotConnectorScript':
            return None
        rev = {v: k for k, v in ACT_NAMES.items()}
        acts = []
        for a in root.find('actions') or []:
            typ = rev.get(a.get('type'), ACT_MOVE)
            flags = int(a.get('flags', 0))
            x = int(a.get('x', 0))
            y = int(a.get('y', 0))
            delay = int(a.get('delay', 0))
            acts.append((typ, flags, x, y, delay))
        return acts
    except Exception:
        return None


def script_file_format(path):
    """识别脚本文件格式：'dcs' / 'xml' / None。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(4)
        if head == SCRIPT_MAGIC:
            return 'dcs'
    except Exception:
        pass
    try:
        with open(path, 'r', encoding='utf-8') as f:
            head = f.read(200)
        return 'xml' if head.lstrip().startswith('<') else None
    except Exception:
        return None


def script_summary(path):
    """读取脚本文件，返回 (步数, 总时长ms, 是否启用键盘录制)。
    无法读取时返回 None。"""
    try:
        fmt = script_file_format(path)
        if fmt == 'xml':
            acts = load_script_xml(path)
            if not acts:
                return None
        elif fmt == 'dcs':
            acts = []
            with open(path, 'rb') as f:
                magic = f.read(4)
                if magic != SCRIPT_MAGIC:
                    return None
                f.read(1)
                (n,) = struct.unpack('<I', f.read(4))
                for _ in range(n):
                    raw = f.read(ACT_SIZE)
                    if len(raw) != ACT_SIZE:
                        break
                    typ, flags, x, y, delay = ACT_STRUCT.unpack(raw)
                    if x >= 0x8000:
                        x -= 0x10000
                    if y >= 0x8000:
                        y -= 0x10000
                    acts.append((typ, flags, x, y, delay))
        else:
            return None
        count = len(acts)
        total = sum(a[4] for a in acts)
        has_keys = any(a[0] in (ACT_KEYDOWN, ACT_KEYUP) for a in acts)
        return count, total, has_keys
    except Exception:
        return None

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
    user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    user32.DestroyIcon.argtypes = [wt.HICON]
    user32.DestroyIcon.restype = wt.BOOL
    user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
    user32.GetAncestor.restype = wt.HWND
    user32.SetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.SetClassLongPtrW.restype = ctypes.c_ssize_t
    user32.RedrawWindow.argtypes = [wt.HWND, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
    user32.RedrawWindow.restype = wt.BOOL
    user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wt.UINT]
    user32.SetWindowPos.restype = wt.BOOL
    user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wt.BOOL
    shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wt.BOOL
    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wt.LPCWSTR]
    shell32.SetCurrentProcessExplicitAppUserModelID.restype = wt.HRESULT
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

    # 键盘模拟 / 按键状态（脚本录制与回放）
    user32.keybd_event.argtypes = [wt.BYTE, wt.BYTE, wt.DWORD, ctypes.c_size_t]
    user32.keybd_event.restype = None
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
    user32.MapVirtualKeyW.restype = wt.UINT

    # 单实例：命名互斥体 + 激活已运行实例窗口
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
    kernel32.CreateMutexW.restype = wt.HANDLE
    kernel32.GetLastError.restype = wt.DWORD
    user32.MessageBoxW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT]
    user32.MessageBoxW.restype = ctypes.c_int
    user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
    user32.FindWindowW.restype = wt.HWND
    user32.IsIconic.argtypes = [wt.HWND]
    user32.IsIconic.restype = wt.BOOL
    user32.GetWindowTextLengthW.argtypes = [wt.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int


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


# ---------------------------------------------------------------------------
# 单实例锁：只允许一个实例运行，重复打开提示并激活已有窗口
# ---------------------------------------------------------------------------
_MUTEX_NAME = 'DotConnector_SingleInstance_Mutex'
_hMutex = None


def _find_existing_main_window():
    """遍历顶层窗口，寻找已运行实例的主窗口（标题含 APP_NAME 且非托盘消息窗）。"""
    found = []
    enum_cb = ENUMWNDPROC(lambda hwnd, lparam: _enum_proc(hwnd, found))
    try:
        user32.EnumWindows(enum_cb, 0)
    except Exception:
        pass
    # 返回第一个可见（或可激活）的主窗口
    for hwnd in found:
        try:
            if user32.IsWindowVisible(hwnd):
                return hwnd
        except Exception:
            continue
    return found[0] if found else None


def _enum_proc(hwnd, found):
    try:
        # 排除托盘消息窗口（窗口类 DotConnectorTk_Tray）与其他非本应用窗口
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, cls, 64)
        if cls.value == 'DotConnectorTk_Tray':
            return 1
        ln = user32.GetWindowTextLengthW(hwnd)
        if ln <= 0 or ln > 256:
            return 1
        buf = ctypes.create_unicode_buffer(ln + 1)
        user32.GetWindowTextW(hwnd, buf, ln + 1)
        if 'DotConnector' in buf.value:
            found.append(hwnd)
    except Exception:
        pass
    return 1


def single_instance_check(show_dialog=True):
    """尝试获取命名互斥体。若已存在其他实例，提示"软件运行中"并激活其窗口，返回 False；
    本实例获得互斥体返回 True（句柄保存至全局，进程退出自动释放）。
    show_dialog=False 时跳过消息框（供自动化测试使用）。"""
    global _hMutex
    if _hMutex:
        return True
    try:
        _hMutex = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        if not _hMutex:
            return True  # 创建失败不阻塞（罕见）
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            # 已有实例在运行：激活其主窗口 + 提示
            hwnd = _find_existing_main_window()
            if hwnd:
                try:
                    if user32.IsIconic(hwnd):
                        user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass
            if show_dialog:
                user32.MessageBoxW(None,
                                   tr('DotConnector 已在运行中！\n'
                                   '请勿重复打开，已为您切换到正在运行的实例。'),
                                   APP_NAME,
                                   MB_OK | MB_ICONWARNING | MB_SETFOREGROUND | MB_TOPMOST)
            return False
        return True
    except Exception:
        return True  # 任何异常都不阻止启动


_ICON_CACHE = None


def ensure_icons():
    """返回 (默认蓝, 红色) 两个托盘图标 HICON（16x16，托盘图标尺寸）。
    红色 icon_run.ico 用于连点运行/录制/播放状态，蓝色 icon.ico 默认。"""
    global _ICON_CACHE
    if _ICON_CACHE:
        return _ICON_CACHE
    stop_p = resource_path('icon.ico')
    run_p = resource_path('icon_run.ico')
    if not os.path.exists(stop_p):
        stop_p = run_p
    if not os.path.exists(stop_p):
        return None, None
    hstop = user32.LoadImageW(None, stop_p, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    hrun = None
    if os.path.exists(run_p):
        hrun = user32.LoadImageW(None, run_p, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    if not hstop:
        return None, None
    _ICON_CACHE = (ctypes.cast(hstop, wt.HICON),
                   ctypes.cast(hrun, wt.HICON) if hrun else None)
    return _ICON_CACHE


# ---------------------------------------------------------------------------
# 系统托盘 + 全局热键（独立线程，纯 Win32 消息循环，不碰 tkinter）
# ---------------------------------------------------------------------------
class Tray:
    CLASS_NAME = 'DotConnectorTk_Tray'
    HK_TOGGLE = 0x101   # 启动/停止
    HK_FORCE = 0x102    # 强制退出
    HK_CAPTURE = 0x103  # 捕获坐标
    HK_RECORD = 0x104   # 脚本录制/停止
    HK_PLAY = 0x105     # 脚本播放/停止
    WM_REFRESH_HOTKEYS = WM_APP + 2   # 主线程请求重注册热键
    MENU_TOGGLE = 1
    MENU_SHOW = 2
    MENU_QUIT = 3

    def __init__(self, app):
        self.app = app
        self.hwnd = None
        self.thread = None
        self.tid = 0
        self.icon_stop = None   # 默认蓝色
        self.icon_run = None    # 运行/录制/播放红色
        self._wndproc = None
        self._icon_is_run = False

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name='tray')
        self.thread.start()

    def _run(self):
        ic = ensure_icons()
        if isinstance(ic, tuple):
            self.icon_stop, self.icon_run = ic
        else:
            self.icon_stop, self.icon_run = ic, None
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
        self._refresh_state()
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
        for hkid in self.HK_ACTIONS:
            user32.UnregisterHotKey(self.hwnd, hkid)
        user32.DestroyWindow(self.hwnd)
        user32.UnregisterClassW(self.CLASS_NAME, wc.hInstance)

    # 热键 ID → 动作名 映射（与 app.hotkey_cfg 键对应）
    HK_ACTIONS = {
        HK_TOGGLE: 'toggle',
        HK_FORCE: 'force',
        HK_CAPTURE: 'capture',
        HK_RECORD: 'record',
        HK_PLAY: 'play',
    }

    def _register_all(self):
        """按 app.hotkey_cfg 注册全部热键。"""
        ok = True
        for hkid, name in self.HK_ACTIONS.items():
            mods, vk = self.app.hotkey_cfg.get(name, (0, 0))
            if not user32.RegisterHotKey(self.hwnd, hkid, mods, vk):
                ok = False
        self.app.hotkey_registered = ok

    def _refresh_hotkeys(self):
        """重注册全部热键（改热键后由主线程通知本线程调用）。"""
        if not self.hwnd:
            return
        for hkid in self.HK_ACTIONS:
            user32.UnregisterHotKey(self.hwnd, hkid)
        self._register_all()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == self.WM_REFRESH_HOTKEYS:
            self._refresh_hotkeys()
            return 0
        if msg == WM_HOTKEY:
            action = self.HK_ACTIONS.get(wparam)
            if action:
                self.app.tray_action(action)
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
        nid.hIcon = self.icon_stop if self.icon_stop else self.icon_run
        nid.szTip = tr(APP_NAME) + tr(' - 已停止')
        return nid

    def _add_icon(self):
        nid = self._nid()
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _delete_icon(self):
        nid = self._nid()
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    def set_state(self, running):
        """切换托盘图标：running=True 显示红色运行图标，否则恢复蓝色默认。"""
        if not self.hwnd:
            self._icon_is_run = bool(running)
            return
        if self._icon_is_run == bool(running):
            return
        self._icon_is_run = bool(running)
        nid = self._nid()
        nid.hIcon = self.icon_run if self._icon_is_run and self.icon_run else self.icon_stop
        if nid.hIcon:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _refresh_state(self):
        """由主线程在托盘线程就绪后调用，应用延迟设置的状态。"""
        if not self.hwnd:
            return
        nid = self._nid()
        nid.hIcon = self.icon_run if self._icon_is_run and self.icon_run else self.icon_stop
        if nid.hIcon:
            shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))

    def _show_menu(self):
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        running = self.app.is_running()
        user32.AppendMenuW(hmenu, 0, self.MENU_TOGGLE, tr('停止连点') if running else tr('开始连点'))
        user32.AppendMenuW(hmenu, 0, self.MENU_SHOW, tr('显示主窗口'))
        user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(hmenu, 0, self.MENU_QUIT, tr('退出'))
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
# 脚本引擎：录制 + 播放（独立线程，内存友好）
# ---------------------------------------------------------------------------
class ScriptRecorder:
    """鼠标/键盘动作录制器。
    - 录制期间预分配固定缓冲（SCRIPT_MAX_ACTIONS 条），避免频繁分配；
    - 移动抽稀：位移 >5px 或 距上次 >50ms 才记录，最多 10000 个移动点；
    - 记录鼠标按键按下/释放、键盘（可选）、以及动作间延迟。"""

    MOUSE_BTNS = {0x01: 0, 0x04: 1, 0x02: 2}   # VK → (0左/1中/2右)

    def __init__(self, record_keys=False, max_actions=None):
        self.record_keys = record_keys
        self.max_actions = max(1000, int(max_actions or SCRIPT_MAX_ACTIONS))
        self._stop = threading.Event()
        self.actions = [None] * self.max_actions   # 预分配固定缓冲
        self.count = 0
        self.finished = threading.Event()
        self._last_move_ts = 0.0
        self._last_pos = None
        self._last_state = {}      # btn/vk -> down 时间（用于长按期间延迟计算）
        self._pending_delay = 0    # 距上一动作的毫秒延迟

    def start(self):
        self._last_move_ts = 0.0
        self._last_pos = None
        threading.Thread(target=self._run, daemon=True, name='script_rec').start()

    def stop(self):
        self._stop.set()

    def _append(self, typ, flags, x, y):
        """写入一条动作，自动带上自上一动作的延迟。"""
        if self.count >= self.max_actions:
            return False
        self.actions[self.count] = (typ, flags, int(x), int(y), self._pending_delay)
        self._pending_delay = 0
        self.count += 1
        return True

    def _run(self):
        try:
            self._poll()
        finally:
            self.finished.set()

    def _poll(self):
        last_tick = time.time() * 1000.0
        prev_state = {}
        # 初始化按键状态
        for vk in self.MOUSE_BTNS:
            prev_state[vk] = bool(self._is_down(vk))
        if self.record_keys:
            for vk in COMMON_VKS:
                prev_state[vk] = bool(self._is_down(vk))
        while not self._stop.is_set():
            now_ms = time.time() * 1000.0
            dt = now_ms - last_tick
            # 1) 鼠标移动（抽稀）
            pt = wt.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            cur = (pt.x, pt.y)
            if self._last_pos is None:
                self._last_pos = cur
                self._last_move_ts = now_ms
            else:
                dx = cur[0] - self._last_pos[0]
                dy = cur[1] - self._last_pos[1]
                dist = (dx * dx + dy * dy) ** 0.5
                if dist >= SCRIPT_MOVE_THRESHOLD or (now_ms - self._last_move_ts) >= SCRIPT_MOVE_MIN_INTERVAL:
                    # 记录移动点（超限时跳过，避免爆缓冲）
                    if self._move_points() < SCRIPT_MAX_MOVE_POINTS:
                        self._append(ACT_MOVE, 0, cur[0], cur[1])
                    self._last_pos = cur
                    self._last_move_ts = now_ms
            # 2) 鼠标按键 按下/释放
            for vk, btn in self.MOUSE_BTNS.items():
                down = self._is_down(vk)
                prev = prev_state.get(vk, False)
                if down and not prev:
                    self._append(ACT_DOWN, btn, cur[0], cur[1])
                    self._last_state[vk] = now_ms
                elif not down and prev:
                    self._append(ACT_UP, btn, cur[0], cur[1])
                    self._last_state.pop(vk, None)
                prev_state[vk] = down
            # 3) 键盘（可选）
            if self.record_keys:
                for vk in COMMON_VKS:
                    down = self._is_down(vk)
                    prev = prev_state.get(vk, False)
                    if down and not prev:
                        self._append(ACT_KEYDOWN, vk, cur[0], cur[1])
                    elif not down and prev:
                        self._append(ACT_KEYUP, vk, cur[0], cur[1])
                    prev_state[vk] = down
            # 4) 延迟累计（动作间的等待自动记录）
            self._pending_delay += int(dt)
            last_tick = now_ms
            self._sleep(8)

    def _move_points(self):
        n = 0
        for i in range(self.count):
            if self.actions[i][0] == ACT_MOVE:
                n += 1
        return n

    def _is_down(self, vk):
        try:
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    def _sleep(self, ms):
        end = time.monotonic() + ms / 1000.0
        while not self._stop.is_set():
            remain = end - time.monotonic()
            if remain <= 0:
                break
            time.sleep(min(0.005, remain))

    def save(self, path, fmt=None):
        """把录制动作写入脚本文件。
        fmt：'dcs'（轻量二进制，默认）或 'xml'（结构化）。"""
        if fmt is None:
            fmt = 'dcs'
        if fmt == 'xml':
            save_script_xml(path, self.actions, self.count)
        else:
            with open(path, 'wb') as f:
                f.write(SCRIPT_MAGIC)
                f.write(bytes([SCRIPT_VERSION]))
                f.write(struct.pack('<I', self.count))
                for i in range(self.count):
                    typ, flags, x, y, delay = self.actions[i]
                    f.write(ACT_STRUCT.pack(typ, flags, x & 0xFFFF, y & 0xFFFF, delay))


class ScriptPlayer:
    """脚本播放器：流式读取动作逐条回放。
    - 不一次性加载整个文件（按序读取当前动作，保持低内存）；
    - 支持循环次数 / 无限循环、速度倍率、循环间隔、绝对/相对坐标；
    - 记录进度（当前动作序号 / 总动作数），供 UI 显示。"""

    def __init__(self, path, loops=1, infinite=False, rate=1.0, loop_gap=0,
                 relative=False):
        self.path = path
        self.loops = max(1, int(loops))
        self.infinite = infinite
        self.rate = max(0.1, float(rate))
        self.loop_gap = max(0, int(loop_gap))
        self.relative = relative
        self._stop = threading.Event()
        self.finished = threading.Event()
        self.total = 0
        self.index = 0          # 当前动作序号（0-based）
        self.loop_now = 0       # 当前循环次数
        self.cur_x = None
        self.cur_y = None
        self.next_desc = ''     # 下一步操作描述（置顶进度显示用）
        self.next_pos = None    # 下一步动作的坐标（避让置顶窗用）

    def start(self):
        self.total, self.index = self._scan_count()
        self.index = 0
        self.loop_now = 0
        threading.Thread(target=self._run, daemon=True, name='script_play').start()

    def stop(self):
        self._stop.set()

    def _scan_count(self):
        """读文件头获取动作总数（不加载全部内容）。"""
        try:
            fmt = script_file_format(self.path)
            if fmt == 'xml':
                acts = load_script_xml(self.path)
                return (len(acts) if acts else 0), 0
            if fmt == 'dcs':
                with open(self.path, 'rb') as f:
                    magic = f.read(4)
                    if magic != SCRIPT_MAGIC:
                        return 0, 0
                    f.read(1)                       # version
                    (n,) = struct.unpack('<I', f.read(4))
                    return n, 0
            return 0, 0
        except Exception:
            return 0, 0

    def _run(self):
        try:
            while True:
                if self.infinite or self.loop_now < self.loops:
                    if not self._play_once():
                        break
                    self.loop_now += 1
                    if (self.infinite or self.loop_now < self.loops) and self.loop_gap > 0:
                        if not self._sleep_until(self.loop_gap):
                            break
                else:
                    break
        finally:
            self.finished.set()

    def _play_once(self):
        try:
            fmt = script_file_format(self.path)
            if fmt == 'xml':
                return self._play_xml()
            return self._play_dcs()
        except Exception:
            return False

    def _play_dcs(self):
        """流式播放轻量二进制脚本（不整文件加载）。"""
        try:
            with open(self.path, 'rb') as f:
                magic = f.read(4)
                if magic != SCRIPT_MAGIC:
                    return False
                f.read(1)
                (total,) = struct.unpack('<I', f.read(4))
                self.total = total
                self.index = 0
                self.next_desc = ''
                self.next_pos = None
                while True:
                    if self._stop.is_set():
                        return False
                    raw = f.read(ACT_SIZE)
                    if len(raw) != ACT_SIZE:
                        break
                    typ, flags, x, y, delay = ACT_STRUCT.unpack(raw)
                    if x >= 0x8000:
                        x -= 0x10000
                    if y >= 0x8000:
                        y -= 0x10000
                    self.next_desc = act_desc(typ, flags)
                    if typ in (ACT_MOVE, ACT_DOWN, ACT_UP):
                        self.next_pos = (x, y)
                    self._exec(typ, flags, x, y)
                    self.index += 1
                    # 动作间延迟（除以速度倍率）
                    wait = int(delay / self.rate)
                    if wait > 0 and not self._sleep_until(wait):
                        return False
                self.next_desc = ''
                return not self._stop.is_set()
        except Exception:
            return False

    def _play_xml(self):
        """播放结构化 XML 脚本（读取全部动作，回放执行）。"""
        try:
            acts = load_script_xml(self.path)
            if not acts:
                return False
            self.total = len(acts)
            self.index = 0
            self.next_desc = ''
            self.next_pos = None
            for i, (typ, flags, x, y, delay) in enumerate(acts):
                if self._stop.is_set():
                    return False
                # 下一步操作 = 当前要执行的动作（进度显示当前即将执行的动作）
                self.next_desc = act_desc(typ, flags)
                if typ in (ACT_MOVE, ACT_DOWN, ACT_UP):
                    self.next_pos = (x, y)
                self._exec(typ, flags, x, y)
                self.index += 1
                wait = int(delay / self.rate)
                if wait > 0 and not self._sleep_until(wait):
                    return False
            self.next_desc = ''
            return not self._stop.is_set()
        except Exception:
            return False

    def _exec(self, typ, flags, x, y):
        if typ == ACT_MOVE:
            self._move_to(x, y)
        elif typ == ACT_DOWN:
            if not self.relative:
                self._move_to(x, y)
            self._mouse(flags, True)
        elif typ == ACT_UP:
            if not self.relative:
                self._move_to(x, y)
            self._mouse(flags, False)
        elif typ == ACT_KEYDOWN:
            self._key(flags, True)
        elif typ == ACT_KEYUP:
            self._key(flags, False)

    def _move_to(self, x, y):
        if self.relative and self.cur_x is not None:
            nx = self.cur_x + x
            ny = self.cur_y + y
        else:
            nx, ny = x, y
        self.cur_x, self.cur_y = nx, ny
        user32.SetCursorPos(int(nx), int(ny))

    def _mouse(self, btn, down):
        flags = {0: (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
                 1: (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
                 2: (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)}.get(btn)
        if flags:
            user32.mouse_event(flags[0] if down else flags[1], 0, 0, 0, 0)

    def _key(self, vk, down):
        scan = user32.MapVirtualKeyW(vk, 0)
        flags = 0
        if down:
            flags = KEYEVENTF_EXTENDEDKEY
        else:
            flags = KEYEVENTF_KEYUP | KEYEVENTF_EXTENDEDKEY
        user32.keybd_event(int(vk), int(scan), flags, 0)

    def _sleep_until(self, ms):
        end = time.monotonic() + ms / 1000.0
        while not self._stop.is_set():
            remain = end - time.monotonic()
            if remain <= 0:
                return True
            time.sleep(min(0.01, remain))
        return False


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
        # 背景（与卡片背景一致；禁用时略降）
        bg = '#eef0f4' if self._disabled else CLR_CARD
        self.configure(bg=bg)
        # 字体行高（自适应 tk scaling，200% 缩放下避免文字底部裁剪）
        fnt = tkfont.Font(family=FONT_FAMILY, size=9)
        try:
            line_h = fnt.metrics('linespace')
        except Exception:
            line_h = 16
        # 控件高度取指示器与文字行高的较大者
        h = max(s, line_h + 4)
        w = self.SIZE + self.GAP + fnt.measure(self._text) + 2
        self.configure(width=w, height=h)
        # 外框（垂直居中）
        top = (h - s) // 2
        if self._is_checkbox():
            self.create_rectangle(2, top + 2, s - 2, top + s - 2, outline=border, width=2,
                                  fill=CLR_CARD)
        else:
            self.create_oval(2, top + 2, s - 2, top + s - 2, outline=border, width=2, fill=CLR_CARD)
        # 选中
        if self._is_checked():
            if self._is_checkbox():
                self.create_rectangle(2, top + 2, s - 2, top + s - 2, outline=self.PRIM, width=2,
                                      fill=self.PRIM)
                # 白色对勾
                self.create_line(s * 0.27, top + s * 0.52, s * 0.43, top + s * 0.68,
                                 s * 0.73, top + s * 0.34, fill='#ffffff', width=2.5,
                                 capstyle='round', joinstyle='round')
            else:
                self.create_oval(s * 0.27, top + s * 0.27, s * 0.73, top + s * 0.73,
                                 fill=self.PRIM, outline='')
        # 文字（垂直居中）
        self.create_text(s + self.GAP, h / 2 + 1, text=self._text, anchor='w',
                         font=(FONT_FAMILY, 9), fill=text_fill)

    def set_text(self, text):
        """动态更新控件文字（热键更改等场景），自动重算宽度并重绘。"""
        try:
            self._text = text
            fnt = tkfont.Font(family=FONT_FAMILY, size=9)
            tw = fnt.measure(text)
            self.configure(width=self.SIZE + self.GAP + tw + 2)
            self._draw()
        except Exception:
            pass

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
        # 注意：不要设置 SetCurrentProcessExplicitAppUserModelID！
        # 实测 Win11 上设置 AUMID 后，任务栏按钮改用 AUMID 关联图标
        # （回退 exe 编译时的图标），不再跟随窗口图标，红/蓝切换失效。
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
        self._top = None
        self._top_drag = None
        self._prog_top = None
        self._prog_top_dodged = False    # 进度窗是否处于避让（右上角）状态
        self._prog_top_user = None       # 进度窗用户拖拽位置（避让后回归用）
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
        self.v_count = tk.StringVar(value='100')
        self.v_cd_min = tk.StringVar(value='0')
        self.v_cd_sec = tk.StringVar(value='10')
        self.v_until = tk.StringVar(value='00:00:00')
        # 停止条件单选：none=不自动停止 / count=点击次数 / cd=倒计时 / until=运行到
        self.v_stop_mode = tk.StringVar(value='none')
        self.v_win_on = tk.BooleanVar(value=True)
        self.v_win_mode = tk.StringVar(value='title')
        self.v_win_text = tk.StringVar(value='')
        self.v_top = tk.BooleanVar(value=False)
        self.v_resize = tk.BooleanVar(value=False)
        # 语言选择：简体中文(zh) / English(en)，默认中文
        self.v_lang = tk.StringVar(value='zh')
        # 历史记录开关：记录本次运行日志到 logs/ 会话文件（默认开启）
        self.v_history_log = tk.BooleanVar(value=True)
        # 脚本播放进度置顶显示开关（更多设置页）
        self.v_progress_top = tk.BooleanVar(value=False)
        # 脚本播放选项
        self.v_script_once = tk.BooleanVar(value=True)   # 只执行一轮脚本（默认开启）
        self.v_script_loop = tk.StringVar(value='1')      # 循环次数
        self.v_script_infinite = tk.BooleanVar(value=False)  # 无限循环
        self.v_script_rate = tk.StringVar(value='1.0')    # 速度倍率
        self.v_script_loop_gap = tk.StringVar(value='500')  # 循环间隔(ms)
        self.v_script_relative = tk.BooleanVar(value=False)  # 相对坐标
        self.v_script_keys = tk.BooleanVar(value=True)    # 记录键盘输入（默认开启）
        self.v_script_sort = tk.StringVar(value='time')   # 脚本排序：name/time
        self.v_script_order = tk.StringVar(value='desc')  # 顺序：asc/desc
        self.v_script_format = tk.StringVar(value='xml')  # 脚本格式：xml（默认）/dcs
        self.v_script_max = tk.StringVar(value='50000')   # 最大录制步骤数（可自定义）
        # 置顶显示字体与透明度（默认字体均 16 号）
        self.v_top_font = tk.StringVar(value='16')        # 连点模式置顶计数 字体大小
        self.v_top_alpha = tk.StringVar(value='92')       # 连点模式置顶计数 透明度(%)
        self.v_prog_font = tk.StringVar(value='16')       # 脚本模式置顶进度 字体大小
        self.v_prog_alpha = tk.StringVar(value='92')      # 脚本模式置顶进度 透明度(%)

        self._status_text = tk.StringVar(value=tr('已停止'))
        self._count_text = tk.StringVar(value='0')
        self._total_text = tk.StringVar(value=tr('历史累计: 0 次'))
        self._script_session_text = tk.StringVar(value='0')
        self._script_total_text = tk.StringVar(value=tr('历史累计: 0 次'))
        self._hint_text = tk.StringVar(value='')
        # 热键配置（默认 Ctrl+F9 启停 / Ctrl+Alt+F10 强退 / Ctrl+Shift+F8 捕获）
        self.hotkey_cfg = {k: [m, v] for k, (m, v) in HK_DEFAULTS.items()}
        self._capturing = None          # 正在自定义的热键 key
        self._hk_entries = {}           # key -> Entry
        self._hk_status_lbl = None
        self._hk_card_labels = {}       # 运行状态页热键说明卡片 label
        self._lbl_hotkey_stop = None    # 连点模式页热键提示（固定开启）
        self._lbl_cap = None            # 连点模式页捕获坐标热键提示
        # 脚本录制/播放 状态
        self.recorder = None            # ScriptRecorder
        self.player = None              # ScriptPlayer
        self._recording = False
        self._playing = False
        self._play_progress = '0/0'
        self._script_dir = SCRIPT_DIR
        self._script_run_session = 0     # 本次打开共执行脚本次数
        self._script_run_total = 0       # 历史累计执行脚本次数
        self._run_start_ts = 0.0
        self._stop_reason = tr('手动停止')
        self._manual_stop = False
        self._last_paused = False

        # 动态更新
        for v in (self.v_interval, self.v_rmin, self.v_rmax, self.v_hold, self.v_gap, self.v_mode):
            v.trace_add('write', self._update_hint)
        self.v_mode.trace_add('write', self._sync_mode_fields)
        self.v_strategy.trace_add('write', self._sync_enabled)
        self.v_top.trace_add('write', self._on_top_toggled)
        self.v_resize.trace_add('write', lambda *a: self._apply_resize())
        # 守卫：只执行一轮开启时，"无限循环"不可为 True（任何途径）
        self.v_script_infinite.trace_add('write', lambda *a: self._guard_script_infinite())

        self._load_config()
        self.eff = (self.dpi / 96.0) * self.scale_opt.get() * self._dpi_factor()
        self._apply_font_scale()

        self.root.title(tr(APP_NAME))
        self.root.protocol('WM_DELETE_WINDOW', self._quit)
        # 窗口/托盘图标：默认蓝色；连点/录制/播放时切换红色（redtubiao）
        self._icon_paths = {}
        self._cur_hicons = []
        self._cur_icon_path = None
        try:
            p_default = resource_path('icon.ico')
            p_run = resource_path('icon_run.ico')
            self._icon_paths['default'] = p_default if os.path.exists(p_default) else None
            self._icon_paths['run'] = p_run if os.path.exists(p_run) else None
        except Exception:
            pass

        # 历史日志文件：开关开启时，每次启动生成独立的会话日志文件，记录本次运行全部日志
        self._log_file = None
        if self.v_history_log.get():
            self._log_file = os.path.join(BASE_DIR, 'logs',
                                          'dotconnector_%s.log' % time.strftime('%Y%m%d_%H%M%S'))
            try:
                d = os.path.dirname(self._log_file)
                os.makedirs(d, exist_ok=True)
                with open(self._log_file, 'a', encoding='utf-8') as f:
                    f.write(tr('== DotConnector v%s 启动于 %s ==\n') % (
                        VERSION, time.strftime('%Y-%m-%d %H:%M:%S')))
            except Exception:
                self._log_file = None

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
        if self.v_progress_top.get():
            self._maybe_create_progress_top()

        self.tray = Tray(self)
        self.tray.start()
        self.root.after(150, self._poll_queue)
        self.root.after(200, self._poll)
        # 窗口映射后应用默认图标（Win32 方式，确保任务栏生效）
        self.root.after(300, lambda: self._apply_window_icon(self._icon_paths.get('default')))

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

        # 构建 5 个标签页（运行状态第1默认打开，连点模式第2，脚本模式第3）
        self._build_page_status()      # 1 运行状态（默认）
        self._build_page_click()       # 2 连点模式
        self._build_page_log()         # 3 脚本模式
        self._build_page_hotkeys()     # 4 热键设置
        self._build_page_ui()          # 5 更多设置

        self.show_page(getattr(self, '_current_page', '运行状态'))

    TAB_ITEMS = ['运行状态', '连点模式', '脚本模式', '热键设置', '更多设置']

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
        # 英文模式下 5 个标签比中文更宽, 缩字号与左右留白, 避免超出窗口边界
        en = LANG == 'en'
        tab_font = (FONT_FAMILY, 8 if en else 10, 'bold')
        tab_padx = P(8 if en else 14)
        for name in self.TAB_ITEMS:
            btn = tk.Label(bar, text=tr(name),
                           font=tab_font,
                           bg=CLR_BG, fg=CLR_SUB, cursor='hand2',
                           padx=tab_padx, pady=P(6))
            btn.pack(side='left', padx=P(1))
            btn.bind('<Button-1>', lambda e, n=name: self.show_page(n))
            self._tab_btns[name] = btn

    def show_page(self, name):
        """切换标签页：高亮当前标签 + 显示对应页面。"""
        if name not in self._pages:
            name = '运行状态'
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

    # ---------- 标签页 1：运行状态 ----------
    def _build_page_status(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        self._pages['运行状态'] = page
        P = self.P

        # 运行状态：点击次数记录 与 脚本运行记录
        sf = ttk.LabelFrame(page, text=tr('运行状态'), padding=P(6), style='Card.TLabelframe')
        sf.pack(fill='x', pady=(0, P(3)))
        # 行0：点击次数记录（左对齐，本次/历史累计）
        cnt = ttk.Frame(sf, style='Card.TFrame')
        cnt.pack(anchor='w', fill='x')
        ttk.Label(cnt, text=tr('点击次数记录：'), style='Top.Sub.TLabel').pack(side='left')
        ttk.Label(cnt, text=tr('本次:'), style='Top.Sub.TLabel').pack(side='left', padx=(P(8), 0))
        ttk.Label(cnt, textvariable=self._count_text, style='Top.Count.TLabel').pack(side='left')
        ttk.Label(cnt, textvariable=self._total_text, style='Top.Sub.TLabel').pack(side='left', padx=(P(10), 0))
        self._lbl_counts = ttk.Label(sf, text='', style='Top.Sub.TLabel')
        # 行1：脚本运行记录（左对齐，本次/历史累计，格式与点击次数记录一致）
        scnt = ttk.Frame(sf, style='Card.TFrame')
        scnt.pack(anchor='w', fill='x', pady=(P(6), 0))
        ttk.Label(scnt, text=tr('脚本运行记录：'), style='Top.Sub.TLabel').pack(side='left')
        ttk.Label(scnt, text=tr('本次:'), style='Top.Sub.TLabel').pack(side='left', padx=(P(8), 0))
        ttk.Label(scnt, textvariable=self._script_session_text, style='Top.Count.TLabel').pack(side='left')
        ttk.Label(scnt, textvariable=self._script_total_text, style='Top.Sub.TLabel').pack(side='left', padx=(P(10), 0))

        # 热键说明（3 列：连点模式热键 / 脚本模式热键 / 强制退出软件热键）
        hk_card = ttk.LabelFrame(page, text=tr('热键说明'), padding=P(6), style='Card.TLabelframe')
        hk_card.pack(fill='x', pady=P(3))
        hk_card.columnconfigure(0, weight=1)
        hk_card.columnconfigure(1, weight=1)
        hk_card.columnconfigure(2, weight=1)
        # 三列标题（第0行）
        ttk.Label(hk_card, text=tr('连点模式热键'), foreground=CLR_PRIMARY, style='Card.TLabel',
                  font=(FONT_FAMILY, 9, 'bold')).grid(row=0, column=0, sticky='w', padx=P(6), pady=(P(2), P(2)))
        ttk.Label(hk_card, text=tr('脚本模式热键'), foreground=CLR_PRIMARY, style='Card.TLabel',
                  font=(FONT_FAMILY, 9, 'bold')).grid(row=0, column=1, sticky='w', padx=P(14), pady=(P(2), P(2)))
        ttk.Label(hk_card, text=tr('强制退出软件热键'), foreground=CLR_PRIMARY, style='Card.TLabel',
                  font=(FONT_FAMILY, 9, 'bold')).grid(row=0, column=2, sticky='w', padx=P(14), pady=(P(2), P(2)))
        self._hk_card_labels = {}
        # 每列两个热键：标签行 + 值行（toggle/capture 在列0；record/play 在列1；force 在列2）
        hk_grid = {
            'toggle': (1, 0), 'capture': (3, 0),
            'record': (1, 1), 'play': (3, 1),
            'force': (1, 2),
        }
        for key, (row, col) in hk_grid.items():
            label = tr(HK_LABELS[key])
            px = P(6) if col == 0 else P(14)
            ttk.Label(hk_card, text=label + ':', style='Card.TLabel').grid(
                row=row, column=col, sticky='w', padx=(px, 0), pady=(P(1), 0))
            m, v = self.hotkey_cfg[key]
            lbl = ttk.Label(hk_card, text=fmt_hotkey(m, v), foreground=CLR_PRIMARY,
                            style='Card.TLabel', font=(FONT_EN, 9, 'bold'))
            lbl.grid(row=row + 1, column=col, sticky='w', padx=(px, 0), pady=(0, P(3)))
            self._hk_card_labels[key] = lbl

        # 运行日志模块（加入运行状态最下方，实时显示日志）
        logf = ttk.LabelFrame(page, text=tr('运行日志'), padding=P(6), style='Card.TLabelframe')
        logf.pack(fill='both', expand=True, pady=(P(3), 0))
        self._log_box = scrolledtext.ScrolledText(
            logf, height=5, wrap='word', state='disabled',
            font=(FONT_MONO, 9), bg='#ffffff', fg=CLR_TEXT,
            insertbackground=CLR_TEXT, relief='flat', bd=0)
        self._log_box.pack(fill='both', expand=True)
        self._log_boxes.append(self._log_box)
        # 操作按钮（置于运行日志模块最下方）：清空日志 / 历史记录 / 导出 TXT / 导出 MD
        logbtns = ttk.Frame(logf, style='Card.TFrame')
        logbtns.pack(fill='x', pady=(P(4), 0))
        ttk.Button(logbtns, text=tr('清空日志'), command=self._clear_log,
                   style='Small.TButton').pack(side='right', padx=P(2))
        ttk.Button(logbtns, text=tr('历史记录'), command=self._open_history,
                   style='Small.TButton').pack(side='right', padx=P(2))
        ttk.Button(logbtns, text=tr('导出 TXT'), command=lambda: self._export_log('txt'),
                   style='Small.TButton').pack(side='right', padx=P(2))
        ttk.Button(logbtns, text=tr('导出 MD'), command=lambda: self._export_log('md'),
                   style='Small.TButton').pack(side='right', padx=P(2))
        if not getattr(self, '_startup_logged', False):
            self._log(tr('程序已启动，按热键（默认 Ctrl+F9）启动/停止连点'))
            self._startup_logged = True

    # ---------- 标签页 2：连点模式 ----------
    def _build_page_click(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        page.columnconfigure(0, weight=1)
        self._pages['连点模式'] = page
        self._click_inner = page    # 供 _apply_minsize 计算默认窗口尺寸
        P = self.P
        inner = page
        row = 0

        # ① 点击模式
        lf = ttk.LabelFrame(inner, text=tr('① 点击模式'), padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        for i, (txt, val) in enumerate([(tr('固定间隔'), 'fixed'), (tr('随机间隔'), 'random'), (tr('长按模式'), 'hold')]):
            ModernRadio(lf, txt, self.v_mode, val).grid(
                row=0, column=i, sticky='w', padx=P(6))

        # ② 鼠标按键
        lf = ttk.LabelFrame(inner, text=tr('② 鼠标按键'), padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        for i, txt in enumerate([tr('左键'), tr('中键'), tr('右键')]):
            ModernRadio(lf, txt, self.v_button, i).grid(
                row=0, column=i, sticky='w', padx=P(6))

        # ③ 点击速度（pack 布局：每组「标签+输入框」紧贴，提示紧跟其后）
        lf = ttk.LabelFrame(inner, text=tr('③ 点击速度'), padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        speed_row = ttk.Frame(lf, style='Card.TFrame')
        speed_row.pack(fill='x', pady=(0, P(4)))
        # 固定间隔组
        self._grp_fixed = ttk.Frame(speed_row, style='Card.TFrame')
        self._lbl_interval = ttk.Label(self._grp_fixed, text=tr('间隔(ms):'))
        self._ent_interval = ttk.Entry(self._grp_fixed, textvariable=self.v_interval,
                                       width=6, justify='center')
        self._lbl_interval.pack(side='left')
        self._ent_interval.pack(side='left', padx=(2, 0))
        # 随机间隔组：最小 / 最大
        self._grp_random = ttk.Frame(speed_row, style='Card.TFrame')
        self._lbl_rmin = ttk.Label(self._grp_random, text=tr('最小(ms):'))
        self._ent_rmin = ttk.Entry(self._grp_random, textvariable=self.v_rmin,
                                   width=6, justify='center')
        self._lbl_rmax = ttk.Label(self._grp_random, text=tr('最大(ms):'))
        self._ent_rmax = ttk.Entry(self._grp_random, textvariable=self.v_rmax,
                                   width=6, justify='center')
        self._lbl_rmin.pack(side='left')
        self._ent_rmin.pack(side='left', padx=(2, 0))
        self._lbl_rmax.pack(side='left', padx=(8, 0))
        self._ent_rmax.pack(side='left', padx=(2, 0))
        # 长按模式组：按住 / 松开
        self._grp_hold = ttk.Frame(speed_row, style='Card.TFrame')
        self._lbl_hold = ttk.Label(self._grp_hold, text=tr('按住(ms):'))
        self._ent_hold = ttk.Entry(self._grp_hold, textvariable=self.v_hold,
                                   width=6, justify='center')
        self._lbl_gap = ttk.Label(self._grp_hold, text=tr('松开(ms):'))
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
        ttk.Label(qf, text=tr('常用:')).pack(side='left', padx=(P(6), P(4)))
        self._preset_btns = {}
        for txt, ms in [(tr('1秒1下'), 1000), (tr('1秒10下'), 100), (tr('1秒20下'), 50),
                        (tr('1秒50下'), 20), (tr('1秒100下'), 10)]:
            b = ttk.Button(qf, text=txt, width=9, command=lambda m=ms: self._quick(m))
            b.pack(side='left', padx=P(2))
            self._preset_btns[ms] = b

        # ④ 点击位置
        lf = ttk.LabelFrame(inner, text=tr('④ 点击位置'), padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=P(3)); row += 1
        ModernRadio(lf, tr('跟随鼠标'), self.v_strategy, 'follow').grid(
            row=0, column=0, sticky='w', padx=P(6))
        ModernRadio(lf, tr('锁定坐标'), self.v_strategy, 'lock').grid(
            row=0, column=1, sticky='w', padx=P(12))
        self._lbl_cap = ttk.Label(lf, text=tr('按 %s 捕获当前坐标') % fmt_hotkey(*self.hotkey_cfg['capture']),
                                  foreground=CLR_SUB)
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
        self._chk_offset = ModernCheck(lf, tr('锁定后每次点击 ±5 像素随机偏移'), self.v_offset)
        self._chk_offset.grid(row=2, column=0, columnspan=3, sticky='w', padx=P(6), pady=P(2))

        # ⑤ 停止条件
        lf = ttk.LabelFrame(inner, text=tr('⑤ 停止条件'), padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=(P(3), 0)); row += 1
        # 热键开启/停止强制启用（不可关闭，仅作提示）
        self._lbl_hotkey_stop = ttk.Label(
            lf, text=tr('热键 %s 开启/停止（固定开启）') % fmt_hotkey(*self.hotkey_cfg['toggle']),
            foreground=CLR_SUB, style='Card.Sub.TLabel')
        self._lbl_hotkey_stop.grid(
            row=0, column=0, columnspan=5, sticky='w', padx=P(6), pady=(0, P(2)))
        # 停止条件三选一（单选框，天然互斥）：不自动停止/点击次数/倒计时/运行到
        # 行距对齐：下面三行含输入框行高较高，"不自动停止"行只有单选框，需额外垂直补偿使行距一致
        ModernRadio(lf, tr('不自动停止'), self.v_stop_mode, 'none').grid(
            row=1, column=0, sticky='w', padx=P(6), pady=(P(1) + 7, P(1) + 7))
        ModernRadio(lf, tr('点击次数:'), self.v_stop_mode, 'count').grid(
            row=2, column=0, sticky='w', padx=P(6), pady=P(1))
        ttk.Entry(lf, textvariable=self.v_count, width=8, justify='center').grid(
            row=2, column=1, sticky='w', padx=P(4))
        ttk.Label(lf, text=tr('次')).grid(row=2, column=2, sticky='w', padx=P(2))
        ModernRadio(lf, tr('倒计时:'), self.v_stop_mode, 'cd').grid(
            row=3, column=0, sticky='w', padx=P(6), pady=P(1))
        ttk.Entry(lf, textvariable=self.v_cd_min, width=5, justify='center').grid(
            row=3, column=1, sticky='w', padx=P(4))
        ttk.Label(lf, text=tr('分')).grid(row=3, column=2, sticky='w', padx=P(2))
        ttk.Entry(lf, textvariable=self.v_cd_sec, width=5, justify='center').grid(
            row=3, column=3, sticky='w', padx=P(4))
        ttk.Label(lf, text=tr('秒')).grid(row=3, column=4, sticky='w', padx=P(2))
        ModernRadio(lf, tr('运行到:'), self.v_stop_mode, 'until').grid(
            row=4, column=0, sticky='w', padx=P(6), pady=P(1))
        ttk.Entry(lf, textvariable=self.v_until, width=10, justify='center').grid(
            row=4, column=1, sticky='w', padx=P(4))
        ttk.Label(lf, text=tr('(时:分:秒, 到点自动停止)')).grid(
            row=4, column=2, columnspan=3, sticky='w', padx=P(2))

        # ⑥ 窗口检测（由原"运行状态"页移入）
        lf = ttk.LabelFrame(inner, text=tr('⑥ 窗口检测'), padding=P(6), style='Card.TLabelframe')
        lf.grid(row=row, column=0, sticky='ew', pady=(P(3), 0)); row += 1
        lf.columnconfigure(1, weight=1)
        self._chk_win = ModernCheck(lf, tr('仅当指定窗口激活时连点，否则自动暂停'), self.v_win_on)
        self._chk_win.grid(row=0, column=0, columnspan=2, sticky='w', padx=P(6))
        ttk.Button(lf, text=tr('选择运行中的程序…'), command=self._pick_window).grid(
            row=1, column=0, sticky='w', padx=P(6), pady=(P(2), 0))
        self._chk_win_selected = ttk.Label(lf, text='', foreground=CLR_PRIMARY)
        self._chk_win_selected.grid(row=2, column=0, columnspan=2, sticky='w', padx=P(6), pady=(P(2), 0))

        self._sync_mode_fields()
        self._sync_enabled()

    # ---------- 标签页 3：脚本模式（录制 + 播放，热键控制 + 导入导出） ----------
    def _build_page_log(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        page.columnconfigure(0, weight=1)
        self._pages['脚本模式'] = page
        P = self.P

        # ===== 脚本录制模块（热键控制，无按钮） =====
        recf = ttk.LabelFrame(page, text=tr('脚本录制'), padding=P(6), style='Card.TLabelframe')
        recf.grid(row=0, column=0, sticky='ew', pady=(0, P(4)))
        self._lbl_rec_status = ttk.Label(recf, text=tr('空闲'), foreground=CLR_SUB,
                                         style='Card.Sub.TLabel')
        self._lbl_rec_status.grid(row=0, column=0, columnspan=4, sticky='w', padx=P(4), pady=(0, P(2)))
        self._lbl_rec_hk = ttk.Label(recf, text=tr('开始/停止录制：按 %s') % fmt_hotkey(*self.hotkey_cfg['record']),
                                     foreground=CLR_PRIMARY, style='Card.TLabel',
                                     font=(FONT_EN, 9, 'bold'))
        self._lbl_rec_hk.grid(row=1, column=0, sticky='w', padx=P(4), pady=P(1))
        # 键盘录制（第1行）
        self._chk_rec_keys = ModernCheck(recf, tr('记录键盘输入（常用键+符号键）'), self.v_script_keys)
        self._chk_rec_keys.grid(row=2, column=0, columnspan=4, sticky='w', padx=P(4), pady=(P(2), 0))
        # 最大步骤（另起一行）
        max_row = ttk.Frame(recf, style='Card.TFrame')
        max_row.grid(row=3, column=0, columnspan=4, sticky='w', padx=P(4), pady=(P(2), 0))
        ttk.Label(max_row, text=tr('最大步骤:'), style='Card.TLabel').pack(side='left')
        ttk.Entry(max_row, textvariable=self.v_script_max, width=8, justify='center').pack(side='left', padx=P(2))
        # 记录格式（另起一行）
        fmt_row = ttk.Frame(recf, style='Card.TFrame')
        fmt_row.grid(row=4, column=0, columnspan=4, sticky='w', padx=P(4), pady=(P(2), 0))
        ttk.Label(fmt_row, text=tr('记录格式:'), style='Card.TLabel').pack(side='left')
        ModernRadio(fmt_row, 'XML', self.v_script_format, 'xml').pack(side='left', padx=P(4))
        ModernRadio(fmt_row, tr('二进制'), self.v_script_format, 'dcs').pack(side='left')

        # ===== 脚本播放模块（热键控制，无按钮） =====
        playf = ttk.LabelFrame(page, text=tr('脚本播放'), padding=P(6), style='Card.TLabelframe')
        playf.grid(row=1, column=0, sticky='ew', pady=(0, P(4)))
        playf.columnconfigure(1, weight=1)
        # 脚本选择 + 刷新 + 打开脚本文件夹
        row0 = ttk.Frame(playf, style='Card.TFrame')
        row0.grid(row=0, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(1))
        ttk.Label(row0, text=tr('脚本:'), style='Card.TLabel').pack(side='left', padx=(P(2), P(2)))
        self._script_combo = ttk.Combobox(row0, width=22, state='readonly')
        self._script_combo.pack(side='left', fill='x', expand=True, padx=(0, P(2)))
        self._script_combo.bind('<<ComboboxSelected>>', lambda e: self._update_script_info())
        ttk.Button(row0, text=tr('刷新'), command=self._refresh_script_list,
                   style='Small.TButton').pack(side='left')
        ttk.Button(row0, text=tr('打开脚本文件夹'), command=self._open_script_folder,
                   style='Small.TButton').pack(side='left', padx=(P(2), 0))
        # 导入/导出提示（非按钮）
        ttk.Label(playf, text=tr('导入/导出脚本：可放入或移动文件到软件同名目录下的 Scripts 文件夹'),
                  foreground=CLR_SUB, style='Card.Sub.TLabel').grid(
            row=1, column=0, columnspan=6, sticky='w', padx=P(4), pady=(0, P(1)))
        # 脚本说明（选中脚本后显示：步数 / 总时长 / 是否键盘录制）
        self._lbl_script_info = ttk.Label(playf, text='', foreground=CLR_PRIMARY,
                                          style='Card.Sub.TLabel')
        self._lbl_script_info.grid(row=2, column=0, columnspan=6, sticky='w',
                                   padx=P(4), pady=(P(2), P(1)))
        # 排序（名称/时间 与 正序/倒序）
        sort_row = ttk.Frame(playf, style='Card.TFrame')
        sort_row.grid(row=3, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(2))
        ttk.Label(sort_row, text=tr('排序:'), style='Card.TLabel').pack(side='left', padx=(P(2), P(2)))
        ModernRadio(sort_row, tr('名称'), self.v_script_sort, 'name').pack(side='left')
        ModernRadio(sort_row, tr('时间'), self.v_script_sort, 'time').pack(side='left', padx=(P(8), 0))
        ttk.Label(sort_row, text=tr('顺序:'), style='Card.TLabel').pack(side='left', padx=(P(12), P(2)))
        ModernRadio(sort_row, tr('正序'), self.v_script_order, 'asc').pack(side='left')
        ModernRadio(sort_row, tr('倒序'), self.v_script_order, 'desc').pack(side='left', padx=(P(8), 0))
        # 播放/停止（热键提示）
        self._lbl_play_hk = ttk.Label(playf, text=tr('开始/停止播放：按 %s') % fmt_hotkey(*self.hotkey_cfg['play']),
                                      foreground=CLR_PRIMARY, style='Card.TLabel',
                                      font=(FONT_EN, 9, 'bold'))
        self._lbl_play_hk.grid(row=4, column=0, columnspan=3,
                               sticky='w', padx=P(4), pady=(P(4), P(2)))
        # 只执行一轮脚本（默认开启，开启时循环次数与循环间隔不可输入）
        once_row = ttk.Frame(playf, style='Card.TFrame')
        once_row.grid(row=5, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(2))
        self._chk_script_once = ModernCheck(once_row, tr('只执行一轮脚本'), self.v_script_once)
        self._chk_script_once.pack(side='left', padx=P(2))
        self.v_script_once.trace_add('write', self._sync_script_once)
        # 循环次数 / 无限循环
        self._loop_row = ttk.Frame(playf, style='Card.TFrame')
        self._loop_row.grid(row=6, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(2))
        ttk.Label(self._loop_row, text=tr('循环次数:'), style='Card.TLabel').pack(side='left', padx=(P(2), P(2)))
        self._ent_script_loop = ttk.Entry(self._loop_row, textvariable=self.v_script_loop,
                                          width=5, justify='center')
        self._ent_script_loop.pack(side='left')
        self._chk_script_infinite = ModernCheck(self._loop_row, tr('无限循环'), self.v_script_infinite)
        self._chk_script_infinite.pack(side='left', padx=(P(10), 0))
        # 循环间隔（移动到速度倍率前一行）
        self._gap_row = ttk.Frame(playf, style='Card.TFrame')
        self._gap_row.grid(row=7, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(2))
        ttk.Label(self._gap_row, text=tr('循环间隔:'), style='Card.TLabel').pack(side='left', padx=(P(2), P(2)))
        self._ent_script_gap = ttk.Entry(self._gap_row, textvariable=self.v_script_loop_gap,
                                         width=6, justify='center')
        self._ent_script_gap.pack(side='left')
        ttk.Label(self._gap_row, text='ms', style='Card.TLabel').pack(side='left', padx=P(2))
        # 速度倍率（循环间隔下一行）
        rate_row = ttk.Frame(playf, style='Card.TFrame')
        rate_row.grid(row=8, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(2))
        ttk.Label(rate_row, text=tr('速度倍率:'), style='Card.TLabel').pack(side='left', padx=(P(2), P(2)))
        ttk.Entry(rate_row, textvariable=self.v_script_rate, width=5, justify='center').pack(side='left')
        ttk.Label(rate_row, text='x', style='Card.TLabel').pack(side='left', padx=P(2))
        # 相对移动（速度倍率下一行）
        rel_row = ttk.Frame(playf, style='Card.TFrame')
        rel_row.grid(row=9, column=0, columnspan=6, sticky='ew', padx=P(2), pady=P(2))
        self._chk_script_relative = ModernCheck(rel_row, tr('相对移动（不跳到录制坐标）'), self.v_script_relative)
        self._chk_script_relative.pack(side='left', padx=P(2))
        # 播放进度条已移到运行状态页（此处不创建 _play_bar）
        self._sync_script_once()

        self._refresh_script_list()

    # ---------- 标签页 4：热键设置（分区：连点模式 / 脚本模式 / 强制退出软件） ----------
    def _build_page_hotkeys(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        page.columnconfigure(0, weight=1)
        self._pages['热键设置'] = page
        P = self.P
        row = 0
        # 连点模式热键区
        hkf = ttk.LabelFrame(page, text=tr('连点模式热键'), padding=P(6), style='Card.TLabelframe')
        hkf.grid(row=row, column=0, sticky='ew', pady=(0, P(4))); row += 1
        # 用空列(column 3)吸收剩余空间，"设置"按钮紧贴热键框右侧而非推到最右
        hkf.columnconfigure(3, weight=1)
        for i, key in enumerate(('toggle', 'capture')):
            ttk.Label(hkf, text=tr(HK_LABELS[key]) + ':', style='Card.TLabel').grid(
                row=i, column=0, sticky='w', padx=P(4), pady=P(1))
            ent = ttk.Entry(hkf, width=15, justify='center', state='readonly')
            ent.grid(row=i, column=1, sticky='w', padx=P(2), pady=P(1))
            self._hk_entries[key] = ent
            self._update_hk_entry(key)
            ttk.Button(hkf, text=tr('设置'), width=5,
                       command=lambda k=key: self._capture_hotkey(k)).grid(
                row=i, column=2, sticky='w', padx=P(4), pady=P(1))
        # 脚本模式热键区
        hkf2 = ttk.LabelFrame(page, text=tr('脚本模式热键'), padding=P(6), style='Card.TLabelframe')
        hkf2.grid(row=row, column=0, sticky='ew', pady=(0, P(4))); row += 1
        hkf2.columnconfigure(3, weight=1)
        for i, key in enumerate(('record', 'play')):
            ttk.Label(hkf2, text=tr(HK_LABELS[key]) + ':', style='Card.TLabel').grid(
                row=i, column=0, sticky='w', padx=P(4), pady=P(1))
            ent = ttk.Entry(hkf2, width=15, justify='center', state='readonly')
            ent.grid(row=i, column=1, sticky='w', padx=P(2), pady=P(1))
            self._hk_entries[key] = ent
            self._update_hk_entry(key)
            ttk.Button(hkf2, text=tr('设置'), width=5,
                       command=lambda k=key: self._capture_hotkey(k)).grid(
                row=i, column=2, sticky='w', padx=P(4), pady=P(1))
        # 强制退出软件（居最下方）
        hkf3 = ttk.LabelFrame(page, text=tr('强制退出软件'), padding=P(6), style='Card.TLabelframe')
        hkf3.grid(row=row, column=0, sticky='ew', pady=(0, P(4))); row += 1
        hkf3.columnconfigure(3, weight=1)
        ttk.Label(hkf3, text=tr('强制退出:'), style='Card.TLabel').grid(
            row=0, column=0, sticky='w', padx=P(4), pady=P(1))
        ent = ttk.Entry(hkf3, width=15, justify='center', state='readonly')
        ent.grid(row=0, column=1, sticky='w', padx=P(2), pady=P(1))
        self._hk_entries['force'] = ent
        self._update_hk_entry('force')
        ttk.Button(hkf3, text=tr('设置'), width=5,
                   command=lambda k='force': self._capture_hotkey(k)).grid(
            row=0, column=2, sticky='w', padx=P(4), pady=P(1))
        ttk.Label(hkf3, text=tr('失控应急，立即结束进程'), foreground=CLR_SUB,
                  style='Card.Sub.TLabel').grid(row=1, column=0, columnspan=3,
                                                 sticky='w', padx=P(4), pady=(P(1), 0))
        # 状态提示 + 恢复默认（标签直接位于页面背景上，背景须与页面 CLR_BG 一致）
        self._hk_status_lbl = ttk.Label(page, text=tr('点击"设置"自定义热键'), foreground=CLR_SUB,
                                        background=CLR_BG)
        self._hk_status_lbl.grid(row=row, column=0, sticky='w', padx=P(4), pady=(0, P(2))); row += 1
        ttk.Button(page, text=tr('恢复默认热键'), command=self._reset_hotkeys).grid(
            row=row, column=0, sticky='w', padx=P(4), pady=(0, P(2)))

    # ---------- 标签页 5：更多设置 ----------
    def _build_page_ui(self):
        page = ttk.Frame(self._page_host, style='App.TFrame')
        self._pages['更多设置'] = page
        P = self.P
        # 语言模块：简体中文 / English（默认中文）
        langf = ttk.LabelFrame(page, text=tr('语言'), padding=P(6), style='Card.TLabelframe')
        langf.pack(fill='x', pady=(0, P(4)))
        ModernRadio(langf, tr('简体中文'), self.v_lang, 'zh',
                    command=self._on_lang_changed).grid(row=0, column=0, sticky='w', padx=P(4))
        ModernRadio(langf, tr('English'), self.v_lang, 'en',
                    command=self._on_lang_changed).grid(row=0, column=1, sticky='w', padx=P(12))
        # 界面缩放模块（仅缩放选项）
        vf = ttk.LabelFrame(page, text=tr('界面缩放'), padding=P(6), style='Card.TLabelframe')
        vf.pack(fill='x', pady=(0, P(4)))
        for i, (txt, val) in enumerate([('100%', 1.0), ('150%', 1.5), ('200%', 2.0)]):
            ModernRadio(vf, txt, self.scale_opt, val,
                        command=self._on_scale_change).grid(row=0, column=i, sticky='w', padx=P(4))
        self._chk_resize = ModernCheck(vf, tr('界面拖拽（可调整窗口大小）'), self.v_resize)
        self._chk_resize.grid(row=1, column=0, columnspan=3, sticky='w', padx=P(4), pady=(P(2), 0))
        # 日志设置模块（历史记录开关）
        lf2 = ttk.LabelFrame(page, text=tr('日志设置'), padding=P(6), style='Card.TLabelframe')
        lf2.pack(fill='x', pady=(0, P(4)))
        self._chk_history_log = ModernCheck(
            lf2, tr('历史记录（记录每次运行日志到 logs/ 会话文件）'), self.v_history_log)
        self._chk_history_log.pack(anchor='w', padx=P(4), pady=(P(2), 0))
        self.v_history_log.trace_add('write', lambda *a: self._save_config())
        # 置顶显示模块（连点模式置顶计数显示 / 脚本模式置顶进度显示）
        mf = ttk.LabelFrame(page, text=tr('置顶显示'), padding=P(6), style='Card.TLabelframe')
        mf.pack(fill='x', pady=(0, P(4)))
        self._chk_top = ModernCheck(mf, tr('连点模式置顶计数显示'), self.v_top)
        self._chk_top.pack(anchor='w', padx=P(4), pady=(P(2), 0))
        # 连点模式置顶：字体大小 + 透明度
        top_font_row = ttk.Frame(mf, style='Card.TFrame')
        top_font_row.pack(anchor='w', padx=P(22), pady=(P(2), 0))
        ttk.Label(top_font_row, text=tr('字体:'), style='Card.Sub.TLabel').pack(side='left')
        ttk.Entry(top_font_row, textvariable=self.v_top_font, width=5,
                  justify='center').pack(side='left', padx=P(2))
        ttk.Label(top_font_row, text=tr('透明度:'), style='Card.Sub.TLabel').pack(side='left', padx=(P(8), 0))
        ttk.Entry(top_font_row, textvariable=self.v_top_alpha, width=5,
                  justify='center').pack(side='left', padx=P(2))
        ttk.Label(top_font_row, text='%', style='Card.Sub.TLabel').pack(side='left')
        self.v_top_font.trace_add('write', lambda *a: self._save_config())
        self.v_top_alpha.trace_add('write', lambda *a: self._save_config())
        # 脚本模式置顶进度显示
        self._chk_progress_top = ModernCheck(mf, tr('脚本模式置顶进度显示'), self.v_progress_top)
        self._chk_progress_top.pack(anchor='w', padx=P(4), pady=(P(2), 0))
        prog_font_row = ttk.Frame(mf, style='Card.TFrame')
        prog_font_row.pack(anchor='w', padx=P(22), pady=(P(2), 0))
        ttk.Label(prog_font_row, text=tr('字体:'), style='Card.Sub.TLabel').pack(side='left')
        ttk.Entry(prog_font_row, textvariable=self.v_prog_font, width=5,
                  justify='center').pack(side='left', padx=P(2))
        ttk.Label(prog_font_row, text=tr('透明度:'), style='Card.Sub.TLabel').pack(side='left', padx=(P(8), 0))
        ttk.Entry(prog_font_row, textvariable=self.v_prog_alpha, width=5,
                  justify='center').pack(side='left', padx=P(2))
        ttk.Label(prog_font_row, text='%', style='Card.Sub.TLabel').pack(side='left')
        self.v_prog_font.trace_add('write', lambda *a: self._save_config())
        self.v_prog_alpha.trace_add('write', lambda *a: self._save_config())
        self.v_progress_top.trace_add('write', self._on_progress_top_toggled)
        # 位置恢复默认按钮
        ttk.Button(mf, text=tr('置顶位置恢复默认'), command=self._reset_top_positions,
                   style='Small.TButton').pack(anchor='w', padx=P(4), pady=(P(2), 0))
        # 当前版本模块（显示版本号 + 下载地址链接，置于所有功能最下方）
        cv = ttk.LabelFrame(page, text=tr('当前版本'), padding=P(6), style='Card.TLabelframe')
        cv.pack(fill='x', pady=(0, P(4)))
        ttk.Label(cv, text='DotConnector  v%s' % VERSION, foreground=CLR_SUB,
                  style='Card.Sub.TLabel').pack(anchor='w', padx=P(4), pady=(P(2), 0))
        # 软件下载地址（点击跳转网页）
        url = 'https://github.com/iop666/DotConnector'
        url_lbl = ttk.Label(cv, text=tr('软件下载地址：%s') % url, foreground=CLR_PRIMARY,
                            style='Card.Sub.TLabel', cursor='hand2')
        url_lbl.pack(anchor='w', padx=P(4), pady=(P(2), 0))
        url_lbl.bind('<Button-1>', lambda e: webbrowser.open(url))

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
                self._log(tr('日志为空，无可导出内容'))
                return
            ts = time.strftime('%Y%m%d_%H%M%S')
            if fmt == 'md':
                ext = 'md'
                body = tr('# DotConnector 运行日志\n\n> 导出时间：%s\n\n```\n%s\n```\n') % (
                    time.strftime('%Y-%m-%d %H:%M:%S'), content)
            else:
                ext = 'txt'
                body = tr('DotConnector 运行日志\n导出时间：%s\n%s\n') % (
                    time.strftime('%Y-%m-%d %H:%M:%S'), content)
            path = filedialog.asksaveasfilename(
                defaultextension='.%s' % ext,
                initialfile='dotconnector_log_%s.%s' % (ts, ext),
                filetypes=[(tr('%s 文件') % fmt.upper(), '*.%s' % ext)],
                title=tr('导出运行日志'))
            if path:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(body)
                self._log(tr('日志已导出：%s') % os.path.basename(path))
        except Exception as e:
            self._log(tr('导出日志失败：%s') % e)

    def _clear_log(self):
        for box in self._log_boxes:
            try:
                box.configure(state='normal')
                box.delete('1.0', 'end')
                box.configure(state='disabled')
            except Exception:
                pass
        self._log(tr('日志已清空'))

    # ---------- 历史记录 ----------
    def _list_history(self):
        """返回 logs 目录下按时间倒序的会话日志文件列表。"""
        try:
            d = os.path.join(BASE_DIR, 'logs')
            if not os.path.isdir(d):
                return []
            files = [f for f in os.listdir(d)
                     if f.startswith('dotconnector_') and f.endswith('.log')]
            files.sort(key=lambda f: os.path.getmtime(os.path.join(d, f)), reverse=True)
            return files
        except Exception:
            return []

    def _open_history(self):
        """打开历史记录窗口：列出所有会话日志文件，选中后查看内容。"""
        try:
            import tkinter as tk
            top = tk.Toplevel(self.root)
            top.title(tr('历史记录 - %s') % APP_NAME)
            top.configure(bg=CLR_BG)
            top.transient(self.root)
            top.grab_set()
            P = self.P

            files = self._list_history()
            # 左侧：文件列表
            lf = ttk.LabelFrame(top, text=tr('历史日志文件'), padding=P(6),
                                style='Card.TLabelframe')
            lf.pack(side='left', fill='y', padx=P(8), pady=P(8))
            listbox = tk.Listbox(lf, width=34, height=14, font=(FONT_MONO, 9),
                                 bg='#ffffff', fg=CLR_TEXT,
                                 selectbackground=CLR_PRIMARY,
                                 selectforeground='#ffffff', relief='flat', bd=0)
            listbox.pack(fill='both', expand=True)
            for i, f in enumerate(files):
                listbox.insert('end', f)
            if files:
                listbox.selection_set(0)

            # 右侧：内容预览
            rf = ttk.LabelFrame(top, text=tr('日志内容'), padding=P(6),
                                style='Card.TLabelframe')
            rf.pack(side='left', fill='both', expand=True, padx=(0, P(8)), pady=P(8))
            box = scrolledtext.ScrolledText(
                rf, width=56, height=14, wrap='word', state='disabled',
                font=(FONT_MONO, 9), bg='#ffffff', fg=CLR_TEXT,
                insertbackground=CLR_TEXT, relief='flat', bd=0)
            box.pack(fill='both', expand=True)

            def show_file(evt=None):
                sel = listbox.curselection()
                if not sel:
                    return
                fname = listbox.get(sel[0])
                path = os.path.join(BASE_DIR, 'logs', fname)
                box.configure(state='normal')
                box.delete('1.0', 'end')
                try:
                    with open(path, encoding='utf-8') as f:
                        box.insert('end', f.read())
                except Exception as e:
                    box.insert('end', tr('读取失败：%s') % e)
                box.configure(state='disabled')

            def delete_file():
                sel = listbox.curselection()
                if not sel:
                    return
                fname = listbox.get(sel[0])
                if not messagebox.askyesno(tr('删除历史记录'),
                                           tr('确定删除日志文件 %s 吗？') % fname,
                                           parent=top):
                    return
                try:
                    os.remove(os.path.join(BASE_DIR, 'logs', fname))
                except Exception as e:
                    messagebox.showerror(tr('删除失败'), str(e), parent=top)
                    return
                listbox.delete(sel[0])
                box.configure(state='normal')
                box.delete('1.0', 'end')
                box.configure(state='disabled')
                self._log(tr('已删除历史日志：%s') % fname)

            def open_folder():
                d = os.path.join(BASE_DIR, 'logs')
                os.makedirs(d, exist_ok=True)
                os.startfile(d)

            listbox.bind('<<ListboxSelect>>', show_file)
            if files:
                show_file()

            btnf = ttk.Frame(top, style='Card.TFrame')
            btnf.pack(side='bottom', fill='x', padx=P(8), pady=P(8))
            ttk.Button(btnf, text=tr('打开日志文件夹'), command=open_folder,
                       style='Small.TButton').pack(side='left', padx=P(2))
            ttk.Button(btnf, text=tr('删除选中'), command=delete_file,
                       style='Small.TButton').pack(side='right', padx=P(2))
            ttk.Button(btnf, text=tr('关闭'), command=top.destroy,
                       style='Small.TButton').pack(side='right', padx=P(2))
        except Exception as e:
            self._log(tr('打开历史记录失败：%s') % e)

    def _reset_hotkeys(self):
        """恢复默认热键并立即生效。"""
        self.hotkey_cfg = {k: [m, v] for k, (m, v) in HK_DEFAULTS.items()}
        for k in HK_LABELS:
            self._update_hk_entry(k)
        self._save_config()
        self._log(tr('热键已恢复默认'))
        if hasattr(self, 'tray') and self.tray.hwnd:
            user32.PostMessageW(self.tray.hwnd, Tray.WM_REFRESH_HOTKEYS, 0, 0)

    def _apply_minsize(self):
        """按「连点模式」页内容需求固定默认窗口尺寸，完整显示全部设置。"""
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
                self._hint_text.set(tr('按住 %.0f ms / 松开 %.0f ms') % (h, g))
            elif mode == 'random':
                lo = self._f(self.v_rmin)
                hi = self._f(self.v_rmax)
                if lo <= 0 or hi <= 0:
                    self._hint_text.set('')
                    return
                if lo > hi:
                    lo, hi = hi, lo
                self._hint_text.set(tr('≈ 1秒 %.1f ~ %.1f 下') % (1000.0 / hi, 1000.0 / lo))
            else:
                iv = self._f(self.v_interval)
                if iv <= 0:
                    self._hint_text.set('')
                    return
                self._hint_text.set(tr('≈ 1秒 %.1f 下') % (1000.0 / iv))
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
            self._log(tr('已捕获当前坐标 (%d, %d)') % (pt.x, pt.y))

    # ---------- 热键自定义 ----------
    def _update_hk_entry(self, key):
        ent = self._hk_entries.get(key)
        if ent is not None:
            m, v = self.hotkey_cfg[key]
            ent.configure(state='normal')
            ent.delete(0, 'end')
            ent.insert(0, fmt_hotkey(m, v))
            ent.configure(state='readonly')
        # 同步更新运行状态页「热键说明」卡片
        lbl = self._hk_card_labels.get(key)
        if lbl is not None:
            try:
                m, v = self.hotkey_cfg[key]
                lbl.config(text=fmt_hotkey(m, v))
            except Exception:
                pass
        # 同步更新连点模式页停止条件的热键提示文本
        if key == 'toggle' and self._lbl_hotkey_stop is not None:
            try:
                m, v = self.hotkey_cfg['toggle']
                self._lbl_hotkey_stop.config(
                    text=tr('热键 %s 开启/停止（固定开启）') % fmt_hotkey(m, v))
            except Exception:
                pass
        # 同步更新连点模式页点击位置的捕获坐标热键提示
        if key == 'capture' and self._lbl_cap is not None:
            try:
                m, v = self.hotkey_cfg['capture']
                self._lbl_cap.config(text=tr('按 %s 捕获当前坐标') % fmt_hotkey(m, v))
            except Exception:
                pass
        # 同步更新脚本模式页 录制/播放 热键标签
        if key == 'record' and getattr(self, '_lbl_rec_hk', None) is not None:
            try:
                m, v = self.hotkey_cfg['record']
                self._lbl_rec_hk.config(text=tr('开始/停止录制：按 %s') % fmt_hotkey(m, v))
            except Exception:
                pass
        elif key == 'play' and getattr(self, '_lbl_play_hk', None) is not None:
            try:
                m, v = self.hotkey_cfg['play']
                self._lbl_play_hk.config(text=tr('开始/停止播放：按 %s') % fmt_hotkey(m, v))
            except Exception:
                pass
        # 同步更新置顶窗热键提示（连点模式置顶计数 / 脚本模式置顶进度）
        if key in ('toggle', 'force'):
            if getattr(self, '_top_hint', None) is not None:
                try:
                    t = fmt_hotkey(*self.hotkey_cfg['toggle'])
                    f = fmt_hotkey(*self.hotkey_cfg['force'])
                    self._top_hint.config(text=tr('连点:%s  急停:%s') % (t, f))
                except Exception:
                    pass
        if key in ('play', 'force'):
            if getattr(self, '_prog_top_hint', None) is not None:
                try:
                    p = fmt_hotkey(*self.hotkey_cfg['play'])
                    f = fmt_hotkey(*self.hotkey_cfg['force'])
                    self._prog_top_hint.config(text=tr('脚本:%s  急停:%s') % (p, f))
                except Exception:
                    pass

    def _capture_hotkey(self, key):
        """点击"设置"后监听下一次按键组合作为新热键。"""
        if self._capturing:
            self._log(tr('请先完成当前热键设置'))
            return
        self._capturing = key
        ent = self._hk_entries[key]
        ent.configure(state='normal')
        ent.delete(0, 'end')
        ent.insert(0, tr('请按键…'))
        ent.configure(state='readonly')
        if self._hk_status_lbl is not None:
            self._hk_status_lbl.config(text=tr('正在设置[%s]，请按新的组合键…') % tr(HK_LABELS[key]),
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
                self._hk_status_lbl.config(text=tr('已取消'), foreground=CLR_SUB)
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
                    self._hk_status_lbl.config(text=tr('与[%s]冲突，请换一个') % tr(HK_LABELS[k]),
                                               foreground=CLR_STOP)
                return
        key = self._capturing
        self.hotkey_cfg[key] = [mods, vk]
        self._capturing = None
        self._update_hk_entry(key)
        if self._hk_status_lbl is not None:
            self._hk_status_lbl.config(text=tr('已更新，立即生效'), foreground=CLR_OK)
        self._save_config()
        self._log(tr('热键[%s]已改为 %s') % (tr(HK_LABELS[key]), fmt_hotkey(mods, vk)))
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
            self._chk_win_selected.config(text=tr('未发现可选的运行中窗口'), foreground=CLR_STOP)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(tr('选择运行中的程序'))
        dlg.transient(self.root)
        dlg.configure(bg=CLR_BG)
        dlg.resizable(True, True)
        P = self.P
        frm = ttk.Frame(dlg, padding=P(10), style='App.TFrame')
        frm.pack(fill='both', expand=True)

        ttk.Label(frm, text=tr('双击选择要检测的窗口（自动填充：有标题用标题，否则用进程名）'),
                  foreground=CLR_SUB, background=CLR_BG, wraplength=int(560 * self.eff),
                  justify='left').pack(anchor='w', pady=(0, P(4)))

        # 搜索框
        sf = ttk.Frame(frm, style='App.TFrame')
        sf.pack(fill='x', pady=(P(6), P(6)))
        ttk.Label(sf, text=tr('搜索:'), background=CLR_BG, foreground=CLR_TEXT).pack(side='left')
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
        tree.heading('title', text=tr('窗口标题'))
        tree.heading('proc', text=tr('进程名'))
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
        ttk.Button(btnf, text=tr('取消'), command=dlg.destroy).pack(side='right', padx=(P(4), 0))
        ttk.Button(btnf, text=tr('确定'), style='Accent.TButton',
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
            self._chk_win_selected.config(text=tr('已选择：%s [%s]') % (title, proc),
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
        """向日志窗口追加一行（含时间戳），并写入会话历史日志文件 logs/dotconnector_YYYYMMDD_HHMMSS.log。"""
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
            # 历史记录开关关闭时不再写入任何日志文件
            if not getattr(self, 'v_history_log', None) or not self.v_history_log.get():
                return
            logfile = getattr(self, '_log_file', None)
            if not logfile:
                d = os.path.join(BASE_DIR, 'logs')
                os.makedirs(d, exist_ok=True)
                logfile = os.path.join(d, 'dotconnector.log')
            d = os.path.dirname(logfile)
            os.makedirs(d, exist_ok=True)
            with open(logfile, 'a', encoding='utf-8') as f:
                f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
        except Exception:
            pass

    def _describe_cfg(self, cfg):
        """把一次运行的完整配置整理成日志文本。"""
        mode_name = {'fixed': tr('固定间隔'), 'random': tr('随机间隔'), 'hold': tr('长按模式')}.get(cfg['mode'], cfg['mode'])
        btn_name = {0: tr('左键'), 1: tr('中键'), 2: tr('右键')}.get(cfg['button'], '?')
        if cfg['mode'] == 'random':
            speed = '%d~%dms' % (cfg['rmin'], cfg['rmax'])
        elif cfg['mode'] == 'hold':
            speed = tr('按住%dms/松开%dms') % (cfg['hold'], cfg['gap'])
        else:
            speed = '%dms' % cfg['interval']
        pos = tr('跟随鼠标') if not cfg['lock'] else tr('锁定(%d,%d)%s') % (
            cfg['x'], cfg['y'], tr(' ±5随机') if cfg['rand_offset'] else '')
        stop = [tr('热键')]  # 热键强制开启
        if cfg['count_on']:
            stop.append(tr('次数%d') % cfg['count_n'])
        if cfg['end_time']:
            stop.append(tr('倒计时'))
        if cfg['until_ts']:
            stop.append(tr('运行到%s') % time.strftime('%H:%M:%S', time.localtime(cfg['until_ts'])))
        win = ''
        if cfg['win_on']:
            win = tr(' 窗口[%s:%s]') % (tr('标题') if cfg['win_mode'] == 'title' else tr('进程'), cfg['win_text'])
        return tr('按键=%s %s %s 位置=%s 停止条件=%s%s') % (
            btn_name, mode_name, speed, pos, ','.join(stop) or tr('无'), win)

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
            self._log(tr('⚠ 窗口检测已开启，但尚未选择运行窗口，已阻止启动'))
            try:
                messagebox.showwarning(tr('提示'), tr('还未选择运行窗口！\n请在「连点模式」页点击"选择运行中的程序…"绑定目标窗口。'),
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
        self._log(tr('▶ 开始连点  %s') % self._describe_cfg(cfg))

    def _stop_clicking_locked(self):
        if self._running and self.engine:
            self._manual_stop = True
            self._stop_reason = tr('手动停止（热键/托盘菜单）')
            self.engine.stop()

    def is_running(self):
        return self._running

    def _hotkey_toggle(self):
        # 热键开启/停止固定开启，始终响应
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
        elif action == 'record':
            self.q.put('script_record')
        elif action == 'play':
            self.q.put('script_play')
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

        stop_mode = self.v_stop_mode.get()
        count_on = (stop_mode == 'count')
        count_n = int(max(1, self._f(self.v_count)))
        self.v_count.set(str(count_n))

        cd_on = (stop_mode == 'cd')
        cd_s = int(self._f(self.v_cd_min)) * 60 + int(self._f(self.v_cd_sec))
        cd_s = max(0, cd_s)
        end_time = (time.time() + cd_s) if (cd_on and cd_s > 0) else None

        until_on = (stop_mode == 'until')
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
                elif item == 'script_record':
                    self._toggle_script_record()
                elif item == 'script_play':
                    self._toggle_script_play()
                elif item == 'quit':
                    self._quit()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    # ---------- 脚本录制 / 播放 控制 ----------
    def _script_dir_path(self):
        d = self._script_dir
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def _list_scripts(self):
        """列出脚本目录下所有 .dcs/.xml 脚本，按排序设置返回文件名列表。"""
        try:
            d = self._script_dir_path()
            files = [f for f in os.listdir(d)
                     if f.endswith('.dcs') or f.endswith('.xml')]
            if not files:
                return []
            by = self.v_script_sort.get()       # name / time
            order = self.v_script_order.get()   # asc / desc
            if by == 'time':
                files.sort(key=lambda f: os.path.getmtime(os.path.join(d, f)),
                           reverse=(order == 'desc'))
            else:
                files.sort(key=lambda f: f.lower(), reverse=(order == 'desc'))
            return files
        except Exception:
            return []

    def _refresh_script_list(self, keep=None):
        """刷新脚本下拉列表；keep 为当前选中名（若还在列表中则保持）。"""
        try:
            files = self._list_scripts()
            self._script_combo['values'] = files
            if not files:
                self._script_combo.set('')
                self._update_script_info()
                return
            cur = keep if keep is not None else self._script_combo.get()
            if cur in files:
                self._script_combo.set(cur)
            else:
                self._script_combo.current(0)
            self._update_script_info()
        except Exception:
            pass

    def _update_script_info(self):
        """显示选中脚本的说明：步数 / 总时长 / 是否键盘录制。"""
        try:
            name = self._script_combo.get()
            if not name:
                self._lbl_script_info.config(text='')
                return
            path = os.path.join(self._script_dir, name)
            sm = script_summary(path)
            if sm is None:
                self._lbl_script_info.config(text=tr('脚本：%s（无法读取）') % name)
                return
            count, total_ms, has_keys = sm
            sec = total_ms / 1000.0
            if sec >= 60:
                dur = tr('%d分%d秒') % (int(sec) // 60, int(sec) % 60)
            else:
                dur = tr('%.1f秒') % sec
            keys_txt = tr('已启用') if has_keys else tr('未启用')
            self._lbl_script_info.config(
                text=tr('脚本说明：录制 %d 步，总时长 %s，键盘录制 %s') % (
                    count, dur, keys_txt))
        except Exception:
            pass

    def _toggle_script_record(self):
        if self._recording:
            self._stop_script_record()
        else:
            self._start_script_record()

    def _start_script_record(self):
        if self._recording:
            return
        if self._playing:
            self._log(tr('⚠ 播放中，请先停止播放再录制'))
            return
        try:
            max_actions = max(1000, int(float(self.v_script_max.get())))
        except Exception:
            max_actions = SCRIPT_MAX_ACTIONS
        self.recorder = ScriptRecorder(record_keys=self.v_script_keys.get(),
                                       max_actions=max_actions)
        self.recorder.start()
        self._recording = True
        self._log(tr('● 开始录制脚本（%s，上限 %d 步）') % (
            tr('含键盘') if self.v_script_keys.get() else tr('仅鼠标'), max_actions))
        self._update_script_ui()

    def _stop_script_record(self):
        if not self._recording or self.recorder is None:
            return
        self.recorder.stop()
        n = self.recorder.count
        self._recording = False
        self._log(tr('■ 录制结束，共 %d 条动作') % n)
        self._update_script_ui()
        # 弹出保存对话框，默认保存到 Scripts 文件夹，格式按设置
        try:
            fmt = self.v_script_format.get()
            ext = 'xml' if fmt == 'xml' else 'dcs'
            d = self._script_dir_path()
            default = 'script_%s' % time.strftime('%Y%m%d_%H%M%S')
            path = filedialog.asksaveasfilename(
                parent=self.root,
                initialdir=d, initialfile=default,
                defaultextension='.%s' % ext,
                filetypes=[(tr('XML 脚本'), '*.xml'), (tr('二进制脚本'), '*.dcs')],
                title=tr('保存录制脚本'))
            if path:
                if path.lower().endswith('.xml'):
                    self.recorder.save(path, 'xml')
                elif path.lower().endswith('.dcs'):
                    self.recorder.save(path, 'dcs')
                else:
                    self.recorder.save(path, fmt)
                self._log(tr('✔ 脚本已保存：%s') % os.path.basename(path))
                self._refresh_script_list(keep=os.path.basename(path))
        except Exception as e:
            self._log(tr('保存脚本失败：%s') % e)
        finally:
            self.recorder = None

    def _guard_script_infinite(self, *a):
        """守卫：只执行一轮开启时，无限循环强制为 False（任何途径设置都会回退）。"""
        try:
            if self.v_script_once.get() and self.v_script_infinite.get():
                self.v_script_infinite.set(False)
        except Exception:
            pass

    def _sync_script_once(self, *a):
        """"只执行一轮脚本"开启时禁用循环次数/循环间隔输入与"无限循环"勾选。"""
        try:
            once = self.v_script_once.get()
            for ent in (getattr(self, '_ent_script_loop', None),
                        getattr(self, '_ent_script_gap', None)):
                if ent is not None:
                    ent.configure(state='disabled' if once else 'normal')
            chk = getattr(self, '_chk_script_infinite', None)
            if chk is not None:
                chk.state(['disabled'] if once else ['!disabled'])
            if once:
                self.v_script_infinite.set(False)
        except Exception:
            pass

    def _toggle_script_play(self):
        if self._playing:
            self._stop_script_play()
        else:
            self._start_script_play()

    def _start_script_play(self):
        if self._playing:
            return
        if self._recording:
            self._log(tr('⚠ 录制中，请先停止录制再播放'))
            return
        name = self._script_combo.get()
        if not name:
            self._log(tr('⚠ 请先在脚本列表中选择一个脚本'))
            return
        path = os.path.join(self._script_dir, name)
        if not os.path.exists(path):
            self._log(tr('⚠ 脚本文件不存在：%s') % name)
            self._refresh_script_list()
            return
        # 记录执行计数（本次/历史累计）
        self._script_run_session += 1
        self._script_run_total += 1
        self._save_config()
        # 只执行一轮：忽略循环次数与循环间隔
        once = self.v_script_once.get()
        if once:
            loops, gap = 1, 0
        else:
            try:
                loops = max(1, int(float(self.v_script_loop.get())))
            except Exception:
                loops = 1
            try:
                gap = max(0, int(float(self.v_script_loop_gap.get())))
            except Exception:
                gap = 0
        try:
            rate = float(self.v_script_rate.get())
        except Exception:
            rate = 1.0
        self.player = ScriptPlayer(
            path, loops=loops, infinite=(not once and self.v_script_infinite.get()),
            rate=rate, loop_gap=gap, relative=self.v_script_relative.get())
        self.player.start()
        self._playing = True
        self._log(tr('▶ 开始播放脚本 %s（倍率%.2fx，循环%s%s）') % (
            name, rate,
            tr('不循环') if once else ('∞' if self.v_script_infinite.get() else loops),
            '' if gap <= 0 else tr('，间隔%dms') % gap))
        self._update_script_ui()

    def _stop_script_play(self):
        if not self._playing or self.player is None:
            return
        self.player.stop()
        self._playing = False
        self._log(tr('■ 停止播放脚本'))
        self._update_script_ui()

    def _update_script_ui(self):
        """刷新脚本录制/播放相关控件状态与文字。"""
        try:
            # 录制
            if self._recording:
                self._lbl_rec_status.config(text=tr('录制中…'), foreground=CLR_STOP)
            else:
                self._lbl_rec_status.config(text=tr('空闲'), foreground=CLR_SUB)
        except Exception:
            pass
        # 图标随状态切换：录制/播放中→红色
        self._update_app_icon()

    # ---------- 导入/导出脚本 ----------
    def _open_script_folder(self):
        """打开 Scripts 脚本文件夹（导入/导出脚本用）。"""
        try:
            d = self._script_dir_path()
            os.startfile(d)
        except Exception as e:
            self._log(tr('打开脚本文件夹失败：%s') % e)

    def _screen_size(self):
        """返回 (屏幕宽, 屏幕高) 物理像素（DPI-aware）。"""
        try:
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080

    def _dodge_top_for_next(self, pos):
        """脚本下一步将点击的位置与置顶窗重叠时避让。
        - 连点模式置顶计数窗：下移避让。
        - 脚本模式置顶进度窗：默认左上角，若下一步点击位置落在屏幕左上角区域
          （避让目标），则移到屏幕右上角对齐（离边距离与左上角一致）；
          下一步不再点击该区域时自动回到左上角。"""
        try:
            if not pos:
                return
            px, py = pos
            margin = self.P(8)
            # 连点模式置顶计数窗：重叠则下移
            if self._top is not None:
                try:
                    x = self._top.winfo_rootx()
                    y = self._top.winfo_rooty()
                    w = self._top.winfo_width()
                    h = self._top.winfo_height()
                    if x <= px <= x + w and y <= py <= y + h:
                        new_y = y + h + 8
                        self._top.geometry('+%d+%d' % (x, new_y))
                        self._top_pos = (x, new_y)
                except Exception:
                    pass
            # 脚本模式置顶进度窗：左上角区域避让到右上角
            prog = getattr(self, '_prog_top', None)
            if prog is not None:
                try:
                    sw, sh = self._screen_size()
                    left_zone = px < sw * 0.3 and py < sh * 0.3
                    if left_zone:
                        # 避让到右上角（离右/上边距与左上角一致）
                        if not getattr(self, '_prog_top_dodged', False):
                            x = sw - prog.winfo_width() - margin
                            y = margin
                            prog.geometry('+%d+%d' % (x, y))
                            self._prog_top_dodged = True
                    else:
                        # 回到左上角（用户拖拽位置优先，否则默认左上角）
                        if getattr(self, '_prog_top_dodged', False):
                            if getattr(self, '_prog_top_user', None):
                                ux, uy = self._prog_top_user
                            else:
                                ux, uy = margin, margin
                            prog.geometry('+%d+%d' % (ux, uy))
                            self._prog_top_dodged = False
                except Exception:
                    pass
        except Exception:
            pass

    def _update_script_progress(self):
        """由 _refresh_state 调用：更新播放进度显示（运行状态、置顶小窗）。"""
        try:
            if self._playing and self.player is not None:
                total = max(1, self.player.total)
                idx = min(self.player.index, total)
                loop_txt = '%d/%d' % (self.player.loop_now + 1,
                                      self.player.loops if not self.player.infinite else 0)
                self._play_progress = '%d/%d' % (idx, total)
                # 循环轮数：打开循环显示"循环轮数：x/n"，只执行一轮显示"只执行一轮"
                if self.v_script_once.get():
                    loop_disp = tr('只执行一轮')
                elif self.player.infinite:
                    loop_disp = tr('循环轮数：%d/∞') % (self.player.loop_now + 1)
                else:
                    loop_disp = tr('循环轮数：%d/%d') % (self.player.loop_now + 1, self.player.loops)
                # 避让：下一步点击位置若与置顶窗重叠则下移
                if getattr(self.player, 'next_pos', None):
                    self._dodge_top_for_next(self.player.next_pos)
                # 运行状态页脚本运行记录：本次 / 历史累计（参考点击次数记录格式）
                try:
                    self._script_session_text.set(str(self._script_run_session))
                    self._script_total_text.set(tr('历史累计: %d 次') % self._script_run_total)
                except Exception:
                    pass
                # 置顶进度小窗：进度 + 热键提示行末尾显示循环轮数（与热键提示同大小样式）
                if getattr(self, '_prog_top', None) is not None:
                    try:
                        self._prog_top_val.config(text=self._play_progress)
                        p = fmt_hotkey(*self.hotkey_cfg['play'])
                        f = fmt_hotkey(*self.hotkey_cfg['force'])
                        self._prog_top_hint.config(
                            text=tr('脚本:%s  急停:%s  %s') % (p, f, loop_disp))
                    except Exception:
                        pass
            else:
                try:
                    self._script_session_text.set(str(self._script_run_session))
                    self._script_total_text.set(tr('历史累计: %d 次') % self._script_run_total)
                except Exception:
                    pass
                if getattr(self, '_prog_top', None) is not None:
                    try:
                        self._prog_top_val.config(text='—')
                        p = fmt_hotkey(*self.hotkey_cfg['play'])
                        f = fmt_hotkey(*self.hotkey_cfg['force'])
                        self._prog_top_hint.config(
                            text=tr('脚本:%s  急停:%s  只执行一轮') % (p, f))
                    except Exception:
                        pass
        except Exception:
            pass

    def _refresh_state(self):
        # 历史累计文本在切换语言后需重新翻译（不依赖引擎状态）
        try:
            self._total_text.set(tr('历史累计: %d 次') % self._total)
            self._script_total_text.set(tr('历史累计: %d 次') % self._script_run_total)
        except Exception:
            pass
        eng = self.engine
        if eng is not None:
            self._count_text.set(str(eng.count))
            if eng.finished.is_set() and not self._finalized:
                self._finalized = True
                self._running = False
                reason = self._stop_reason if self._manual_stop else self._guess_stop_reason()
                dur = (time.time() - self._run_start_ts) if self._run_start_ts else 0.0
                self._log(tr('■ 停止连点  本次 %d 次，耗时 %.1f 秒，原因：%s') % (eng.count, dur, reason))
                # 详细坐标汇总
                coord_txt = self._summarize_coords(eng.coord_counts)
                if coord_txt:
                    self._log(tr('  点击坐标: %s') % coord_txt)
                self._total += eng.count
                self._total_text.set(tr('历史累计: %d 次') % self._total)
                self._save_config()
        if self._running:
            paused = bool(eng and eng.paused)
            if paused and not self._last_paused:
                self._log(tr('⏸ 目标窗口失焦，自动暂停'))
            elif not paused and self._last_paused:
                self._log(tr('▶ 目标窗口恢复，继续连点'))
            self._last_paused = paused
            self._set_status(True, paused)
        else:
            if self._last_paused:
                self._log(tr('⏸ 连点已停止，暂停状态清除'))
            self._last_paused = False
            self._set_status(False)
        # 运行状态页：点击次数记录已单独显示本次/历史累计，此处只显示时长/坐标
        if getattr(self, '_lbl_counts', None) is not None:
            dur_txt = ''
            if self._running and self._run_start_ts:
                dur = time.time() - self._run_start_ts
                dur_txt = tr('已运行 %d 分 %d 秒') % (dur // 60, int(dur) % 60)
            coord_txt = ''
            if self._running and eng is not None and eng.last_coord:
                coord_txt = tr('最近坐标 (%d, %d)') % eng.last_coord
            parts = [t for t in (dur_txt, coord_txt) if t]
            self._lbl_counts.config(text='   '.join(parts))
        # 脚本播放进度刷新 + 播放完成检测
        if self._playing and self.player is not None:
            if self.player.finished.is_set():
                self._playing = False
                self._log(tr('✔ 脚本播放完成'))
                self._update_script_ui()
            else:
                self._update_script_progress()
        else:
            self._update_script_progress()

    def _guess_stop_reason(self):
        """根据上次配置推断引擎自然停止的原因。"""
        try:
            cfg = self._last_cfg or {}
            if cfg.get('count_on'):
                return tr('点击次数已达成')
            if cfg.get('end_time'):
                return tr('倒计时结束')
            if cfg.get('until_ts'):
                return tr('运行到指定时间')
        except Exception:
            pass
        return tr('停止')

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
                return tr('(%d,%d) × %d 次') % (x, y, n)
            for (x, y), n in items[:5]:
                parts.append('(%d,%d)×%d' % (x, y, n))
            if len(items) > 5:
                parts.append(tr('…共%d个坐标') % len(items))
            return tr('共%d次，主要坐标: %s') % (total, ' '.join(parts))
        except Exception:
            return ''

    def _update_app_icon(self):
        """按当前状态统一决定图标：连点运行/录制/播放 → 红色，否则蓝色默认。
        同时切换系统托盘图标与软件左上角（窗口）图标。"""
        try:
            red = bool(self._running or self._recording or self._playing)
            if getattr(self, 'tray', None) is not None:
                self.tray.set_state(red)
            path = self._icon_paths.get('run') if red else self._icon_paths.get('default')
            if path and path != self._cur_icon_path:
                self._apply_window_icon(path)
        except Exception:
            pass

    def _apply_window_icon(self, path, force_refresh=False):
        """用 Win32 WM_SETICON 设置窗口图标（tkinter iconbitmap 在打包环境不生效）。
        关键（实测 + 微软官方 Q&A 确认）：
        - 不能设置 AppUserModelID，否则任务栏按钮改用 AUMID 关联图标不跟随窗口；
        - ICON_SMALL 必须加载 256x256 大图标，Win11 上 16x16 小图标只更新窗口装饰
          不会更新任务栏按钮；
        - winfo_id() 返回 TkChild 内部窗口，任务栏读的是顶层窗口，必须用
          GetAncestor(hwnd, GA_ROOT) 取真正的 TkTopLevel 再发 WM_SETICON。
        force_refresh=True 时最小化再恢复，强制任务栏重建按钮读取新图标。"""
        try:
            if not path or not os.path.exists(path):
                path = self._icon_paths.get('default')
            if not path or not os.path.exists(path):
                return
            hwnd = self.root.winfo_id()
            if not hwnd:
                return
            # 取真正顶层窗口（任务栏图标跟随它）
            top = user32.GetAncestor(hwnd, GA_ROOT)
            target = top if top else hwnd
            # 按尺寸加载：ICON_SMALL 用 256x256（Win11 任务栏要求大图），ICON_BIG 用 32x32
            h_small = user32.LoadImageW(None, path, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
            h_big = user32.LoadImageW(None, path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            # 方式1：设置窗口类图标 GCL_HICON/GCL_HICONSM
            if h_big:
                user32.SetClassLongPtrW(target, GCL_HICON, h_big)
            if h_small:
                user32.SetClassLongPtrW(target, GCL_HICONSM, h_small)
            # 方式2：WM_SETICON（标题栏/Alt+Tab/任务栏）—— ICON_SMALL 传 256 大图
            if h_small:
                user32.SendMessageW(target, WM_SETICON, ICON_SMALL, h_small)
            if h_big:
                user32.SendMessageW(target, WM_SETICON, ICON_BIG, h_big)
            # 保留句柄不销毁（任务栏可能仍引用旧句柄，销毁会导致图标空白）
            self._cur_hicons = [h for h in (h_small, h_big) if h]
            self._cur_icon_path = path
            # 强制刷新：重绘边框 + SetWindowPos(FRAMECHANGED) 让系统重算非客户区
            user32.RedrawWindow(target, None, None, RDW_FRAME | RDW_INVALIDATE)
            user32.SetWindowPos(target, None, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER |
                                SWP_NOACTIVATE | SWP_FRAMECHANGED)
            # 任务栏按钮图标有独立缓存：最小化再恢复，强制任务栏重建按钮读新图标
            # 注意：必须用不激活的组合（SW_SHOWMINNOACTIVE + SW_SHOWNOACTIVATE），
            # 否则 SW_RESTORE 会把窗口激活到前台，图标切换时窗口跳到最前干扰使用。
            if force_refresh:
                user32.ShowWindow(target, SW_SHOWMINNOACTIVE)
                self.root.after(80, lambda: user32.ShowWindow(target, SW_SHOWNOACTIVATE))
        except Exception:
            pass

    def _set_status(self, running, paused=False):
        if running:
            if paused:
                self._status_text.set(tr('运行中（窗口失焦暂停）'))
            else:
                self._status_text.set(tr('运行中'))
        else:
            self._status_text.set(tr('已停止'))
        # 窗口标题带状态标记 → 任务栏可直观看到是否在运行
        try:
            if running:
                self.root.title('● %s - %s' % (self._status_text.get(), tr(APP_NAME)))
            else:
                self.root.title(tr(APP_NAME))
        except Exception:
            pass
        # 图标随状态切换：连点开启→红色
        self._update_app_icon()

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
    def _on_lang_changed(self):
        """切换语言：更新全局 LANG、保存配置、重建界面。"""
        global LANG
        LANG = self.v_lang.get()
        self._save_config()
        self._rebuild_ui()
        self._log(tr('语言已切换'))

    def _on_scale_change(self):
        self._save_config()
        self._rebuild_ui()

    def _rebuild_ui(self):
        top_wanted = self.v_top.get()
        progress_top_wanted = self.v_progress_top.get()
        self._destroy_top()
        self._destroy_progress_top()
        cur_page = getattr(self, '_current_page', '运行状态')
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
        self._lbl_counts = None
        self._tab_btns = {}
        self._pages = {}
        self._hk_entries = {}
        self._hk_status_lbl = None
        self._hk_card_labels = {}
        self._lbl_hotkey_stop = None
        self._lbl_cap = None
        self._lbl_rec_hk = None
        self._lbl_play_hk = None
        self._top_hint = None
        self._prog_top_hint = None
        self._log_box = None
        self._log_boxes = []
        self._build_ui()
        self._update_script_ui()
        self._refresh_script_list()
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
        if progress_top_wanted:
            self._maybe_create_progress_top()

    def _on_top_toggled(self, *a):
        if self.v_top.get():
            self._maybe_create_top()
        else:
            self._destroy_top()

    def _make_top_window(self, title_text):
        """创建置顶小窗公共结构，返回 (top, bar, val_label, hint_label)。"""
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes('-topmost', True)
        top.configure(bg='#2b2b2b')
        bar = tk.Frame(top, bg='#2b2b2b', cursor='fleur')
        bar.pack(fill='x')
        tk.Label(bar, text=title_text, fg='#9aa0a6', bg='#2b2b2b',
                 font=('Microsoft YaHei UI', 9)).pack(side='left', padx=6, pady=2)
        tk.Button(bar, text='✕', command=None, bg='#2b2b2b', fg='#cccccc',
                  relief='flat', bd=0, activebackground='#4a4a4a', cursor='hand2',
                  font=('Microsoft YaHei UI', 9)).pack(side='right', padx=2)
        val = tk.Label(top, text='—', fg='#4fc3f7', bg='#2b2b2b', justify='center',
                       font=('Consolas', int(round(16 * self.scale_opt.get()))))
        val.pack(padx=10, pady=(0, 4))
        hint = tk.Label(top, text='', fg='#6b7280', bg='#2b2b2b', justify='center',
                        font=('Microsoft YaHei UI', 9))
        hint.pack(padx=8, pady=(0, 4))
        return top, bar, val, hint

    def _all_top_children(self, w):
        """递归收集 w 下所有子控件。"""
        kids = []
        for c in w.winfo_children():
            kids.append(c)
            kids.extend(self._all_top_children(c))
        return kids

    def _bind_top_drag(self, top, on_move):
        """把整窗（标题栏/值/提示）都绑定拖动，on_move(x,y) 保存位置。"""
        def drag_start(e):
            self._top_drag = (e.x_root - top.winfo_x(), e.y_root - top.winfo_y())

        def drag_move(e):
            if getattr(self, '_top_drag', None):
                nx = e.x_root - self._top_drag[0]
                ny = e.y_root - self._top_drag[1]
                top.geometry('+%d+%d' % (nx, ny))
                on_move(nx, ny)

        for w in [top] + self._all_top_children(top):
            try:
                w.bind('<Button-1>', drag_start)
                w.bind('<B1-Motion>', drag_move)
            except Exception:
                pass

    def _apply_top_alpha(self, top, alpha_str):
        try:
            a = max(30, min(100, int(float(alpha_str))))
            top.attributes('-alpha', a / 100.0)
        except Exception:
            top.attributes('-alpha', 0.92)

    def _position_top_left(self, top, pos_attr):
        """默认置于屏幕左上角；若用户拖拽过则沿用上次位置。"""
        top.update_idletasks()
        if getattr(self, pos_attr, None):
            x, y = getattr(self, pos_attr)
        else:
            x, y = self.P(8), self.P(8)
            setattr(self, pos_attr, (x, y))
        top.geometry('+%d+%d' % (x, y))

    def _maybe_create_top(self):
        if self._top is not None:
            return
        top, bar, val, hint = self._make_top_window(tr('连点模式置顶计数显示'))
        # 关闭按钮绑定
        for c in bar.winfo_children():
            if c.winfo_class() == 'Button':
                c.config(command=self._close_top)
        val.config(textvariable=self._count_text,
                   font=('Consolas', int(round(max(8, int(self.v_top_font.get())) * self.scale_opt.get()))))
        # 热键提示（弱化，非重要说明）：连点模式热键 + 急停热键
        toggle_hk = fmt_hotkey(*self.hotkey_cfg['toggle'])
        force_hk = fmt_hotkey(*self.hotkey_cfg['force'])
        hint.config(text=tr('连点:%s  急停:%s') % (toggle_hk, force_hk))
        self._top_hint = hint
        self._apply_top_alpha(top, self.v_top_alpha.get())

        # 整窗可拖动（标题栏/值/提示都能拖），位置持久化到 config
        def on_move(nx, ny):
            self._top_pos = (nx, ny)
            self._save_config()

        self._bind_top_drag(top, on_move)

        # 位置：优先用户拖拽/持久化位置，否则默认左上角
        if getattr(self, '_top_pos', None):
            x, y = self._top_pos
            top.geometry('+%d+%d' % (x, y))
        else:
            self._position_top_left(top, '_top_pos')
        self._top = top

    def _reset_top_positions(self):
        """将两个置顶窗位置恢复默认（左上角），并清除持久化位置。"""
        self._top_pos = None
        self._prog_top_pos = None
        self._prog_top_user = None
        self._prog_top_dodged = False
        if self._top is not None:
            self._position_top_left(self._top, '_top_pos')
        if getattr(self, '_prog_top', None) is not None:
            self._position_top_left(self._prog_top, '_prog_top_pos')
        self._save_config()
        self._log(tr('置顶位置已恢复默认（左上角）'))

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

    # ---------- 播放进度置顶小窗（类似置顶计数） ----------
    def _on_progress_top_toggled(self, *a):
        if self.v_progress_top.get():
            self._maybe_create_progress_top()
        else:
            self._destroy_progress_top()

    def _maybe_create_progress_top(self):
        if getattr(self, '_prog_top', None) is not None:
            return
        top, bar, val, hint = self._make_top_window(tr('脚本模式置顶进度显示'))
        for c in bar.winfo_children():
            if c.winfo_class() == 'Button':
                c.config(command=self._close_progress_top)
        self._prog_top_val = val
        val.config(font=('Consolas', int(round(max(8, int(self.v_prog_font.get())) * self.scale_opt.get()))))
        # 热键提示（弱化）：脚本模式热键 + 急停热键 + 循环轮数（循环次数显示在提示行末尾，同大小样式）
        play_hk = fmt_hotkey(*self.hotkey_cfg['play'])
        force_hk = fmt_hotkey(*self.hotkey_cfg['force'])
        hint.config(text=tr('脚本:%s  急停:%s  只执行一轮') % (play_hk, force_hk))
        self._prog_top_hint = hint
        self._apply_top_alpha(top, self.v_prog_alpha.get())

        # 整窗可拖动，位置持久化到 config
        def on_move(nx, ny):
            self._prog_top_pos = (nx, ny)
            self._prog_top_user = (nx, ny)
            self._save_config()

        self._bind_top_drag(top, on_move)

        # 位置：优先用户拖拽/持久化位置，否则默认左上角（与连点模式一致）
        if getattr(self, '_prog_top_pos', None):
            x, y = self._prog_top_pos
            top.geometry('+%d+%d' % (x, y))
        else:
            self._position_top_left(top, '_prog_top_pos')
        self._prog_top = top

    def _close_progress_top(self):
        self.v_progress_top.set(False)
        self._destroy_progress_top()

    def _destroy_progress_top(self):
        if getattr(self, '_prog_top', None) is not None:
            try:
                self._prog_top.destroy()
            except Exception:
                pass
            self._prog_top = None

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
        self._script_run_total = int(float(gi(g, 'script_run_total', 0)))
        # 默认缩放档：第一次打开固定为 100%（1.0），之后记住用户选择
        self.scale_opt.set(float(gi(g, 'scale', 1.0)))
        # 语言：简体中文(zh) 默认 / English(en)
        global LANG
        self.v_lang.set(gi(g, 'lang', 'zh') if gi(g, 'lang', 'zh') in ('zh', 'en') else 'zh')
        LANG = self.v_lang.get()
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
        self.v_count.set(gi(s, 'count', '100'))
        self.v_cd_min.set(gi(s, 'countdown_min', '0'))
        self.v_cd_sec.set(gi(s, 'countdown_sec', '10'))
        self.v_until.set(gi(s, 'until', '00:00:00'))
        # 停止条件单选：优先读 stop_mode，兼容旧版三个布尔字段
        sm = gi(s, 'stop_mode', '')
        if sm in ('none', 'count', 'cd', 'until'):
            self.v_stop_mode.set(sm)
        elif gi(s, 'count_enabled', 'false') == 'true':
            self.v_stop_mode.set('count')
        elif gi(s, 'countdown_enabled', 'false') == 'true':
            self.v_stop_mode.set('cd')
        elif gi(s, 'until_enabled', 'false') == 'true':
            self.v_stop_mode.set('until')
        else:
            self.v_stop_mode.set('none')
        self.v_win_on.set(gi(w, 'check_enabled', 'true') == 'true')
        self.v_win_mode.set(gi(w, 'match', 'title'))
        self.v_win_text.set(gi(w, 'target', ''))
        self.v_top.set(gi(v, 'top_counter', 'false') == 'true')
        self.v_resize.set(gi(v, 'resize_enabled', 'false') == 'true')
        self.v_history_log.set(gi(v, 'history_log', 'true') == 'true')
        self.v_progress_top.set(gi(v, 'progress_top', 'false') == 'true')
        # 置顶显示 字体/透明度（默认字体均 16 号）
        self.v_top_font.set(gi(v, 'top_font', '16'))
        self.v_top_alpha.set(gi(v, 'top_alpha', '92'))
        self.v_prog_font.set(gi(v, 'prog_font', '16'))
        self.v_prog_alpha.set(gi(v, 'prog_alpha', '92'))
        # 置顶窗位置（用户拖拽后持久化）
        self._top_pos = None
        tp = gi(v, 'top_pos', '').strip()
        if tp:
            try:
                tx, ty = tp.split(',')
                self._top_pos = (int(tx), int(ty))
            except Exception:
                pass
        self._prog_top_pos = None
        pp = gi(v, 'prog_pos', '').strip()
        if pp:
            try:
                px2, py2 = pp.split(',')
                self._prog_top_pos = (int(px2), int(py2))
                self._prog_top_user = self._prog_top_pos
            except Exception:
                pass
        # 脚本设置
        sc = cp['script'] if cp.has_section('script') else {}
        self.v_script_once.set(gi(sc, 'once', 'true') == 'true')
        self.v_script_loop.set(gi(sc, 'loop', '1'))
        self.v_script_infinite.set(gi(sc, 'infinite', 'false') == 'true')
        self.v_script_rate.set(gi(sc, 'rate', '1.0'))
        self.v_script_loop_gap.set(gi(sc, 'loop_gap', '500'))
        self.v_script_relative.set(gi(sc, 'relative', 'false') == 'true')
        self.v_script_keys.set(gi(sc, 'keys', 'true') == 'true')   # 键盘录制默认开启
        self.v_script_sort.set(gi(sc, 'sort', 'time'))
        self.v_script_order.set(gi(sc, 'order', 'desc'))
        self.v_script_format.set(gi(sc, 'format', 'xml'))
        self.v_script_max.set(gi(sc, 'max_actions', '50000'))
        # 热键自定义配置
        for hk in ('toggle', 'force', 'capture', 'record', 'play'):
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
                'script_run_total': str(int(getattr(self, '_script_run_total', 0))),
                'scale': str(self.scale_opt.get()),
                'lang': self.v_lang.get(),
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
            stop_mode = self.v_stop_mode.get()
            cp['stop'] = {
                'stop_mode': stop_mode,
                'count_enabled': 'true' if stop_mode == 'count' else 'false',
                'count': self.v_count.get(),
                'countdown_enabled': 'true' if stop_mode == 'cd' else 'false',
                'countdown_min': self.v_cd_min.get(),
                'countdown_sec': self.v_cd_sec.get(),
                'until_enabled': 'true' if stop_mode == 'until' else 'false',
                'until': self.v_until.get(),
                'hotkey_stop': 'true',  # 热键固定开启
            }
            cp['window'] = {
                'check_enabled': 'true' if self.v_win_on.get() else 'false',
                'match': self.v_win_mode.get(),
                'target': self.v_win_text.get(),
            }
            cp['view'] = {
                'top_counter': 'true' if self.v_top.get() else 'false',
                'resize_enabled': 'true' if self.v_resize.get() else 'false',
                'history_log': 'true' if self.v_history_log.get() else 'false',
                'progress_top': 'true' if self.v_progress_top.get() else 'false',
                'top_font': self.v_top_font.get(),
                'top_alpha': self.v_top_alpha.get(),
                'prog_font': self.v_prog_font.get(),
                'prog_alpha': self.v_prog_alpha.get(),
                'top_pos': ('%d,%d' % self._top_pos) if getattr(self, '_top_pos', None) else '',
                'prog_pos': ('%d,%d' % self._prog_top_pos) if getattr(self, '_prog_top_pos', None) else '',
            }
            cp['script'] = {
                'once': 'true' if self.v_script_once.get() else 'false',
                'loop': self.v_script_loop.get(),
                'infinite': 'true' if self.v_script_infinite.get() else 'false',
                'rate': self.v_script_rate.get(),
                'loop_gap': self.v_script_loop_gap.get(),
                'relative': 'true' if self.v_script_relative.get() else 'false',
                'keys': 'true' if self.v_script_keys.get() else 'false',
                'sort': self.v_script_sort.get(),
                'order': self.v_script_order.get(),
                'format': self.v_script_format.get(),
                'max_actions': self.v_script_max.get(),
            }
            cp['hotkey'] = {k: '%d,%d' % (self.hotkey_cfg[k][0], self.hotkey_cfg[k][1])
                            for k in ('toggle', 'force', 'capture', 'record', 'play')}
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
            # 停止脚本引擎（录制/播放）
            if self.recorder is not None:
                self.recorder.stop()
            if self.player is not None:
                self.player.stop()
            self._save_config()
        except Exception:
            pass
        self._destroy_top()
        self._destroy_progress_top()
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
    print(tr('DotConnector 引擎自测（模拟模式，不产生真实点击）...'))
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
    check(tr('固定间隔25次 → count=%d') % e.count, e.count == 25)
    check(tr('25次×30ms≈0.75s, 实际 %.3fs') % dt, 0.5 <= dt <= 2.0)

    # 2. 随机间隔
    cfg = dict(base); cfg.update(mode='random', rmin=1, rmax=10, count_on=True, count_n=60)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check(tr('随机间隔60次 → count=%d') % e.count, e.count == 60)

    # 3. 长按模式
    cfg = dict(base); cfg.update(mode='hold', hold=15, gap=5, count_on=True, count_n=12)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check(tr('长按模式12次 → count=%d') % e.count, e.count == 12)

    # 4. 倒计时停止
    cfg = dict(base); cfg.update(interval=5, count_on=False, end_time=time.time() + 0.3)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check(tr('倒计时0.3s自动停止 → count=%d') % e.count, e.finished.is_set() and e.count >= 1)

    # 5. 定时停止
    cfg = dict(base); cfg.update(interval=5, count_on=False, until_ts=time.time() + 0.3)
    e = ClickEngine(cfg, sim=True)
    e.start(); e.finished.wait(15)
    check(tr('定时0.3s自动停止 → count=%d') % e.count, e.finished.is_set() and e.count >= 1)

    # 6. 窗口检测暂停
    cfg = dict(base); cfg.update(win_on=True, win_mode='title', win_text='__NEVER_MATCH_XYZ__',
                                 count_on=False, end_time=None, interval=10)
    e = ClickEngine(cfg, sim=True)
    e.start(); time.sleep(0.4); e.stop(); e.finished.wait(5)
    check(tr('窗口检测(不匹配)暂停 → count=%d paused=%s') % (e.count, e.paused),
          e.count == 0 and e.paused is True)

    # 7. 快速停止响应
    cfg = dict(base); cfg.update(interval=200, count_on=False, end_time=None)
    e = ClickEngine(cfg, sim=True)
    e.start(); time.sleep(0.1); e.stop()
    t0 = time.monotonic(); e.finished.wait(5); dt = time.monotonic() - t0
    check(tr('运行中手动停止, 0.1s内响应') if dt < 0.1 else tr('停止响应耗时 %.3fs') % dt, dt < 0.1)

    print(tr('自测结果: ') + (tr('全部通过') if ok else tr('存在失败')))
    return 0 if ok else 1


# ---------------------------------------------------------------------------
def main():
    if '--selftest' in sys.argv:
        return run_selftest()
    set_dpi_aware()
    if not single_instance_check():
        return 1
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