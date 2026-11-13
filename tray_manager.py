import os
import sys
import threading
import ctypes
from ctypes import wintypes

try:
    import win32gui
    import win32con
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

WM_TRAY_CALLBACK = (win32con.WM_USER + 20) if HAS_WIN32 else 1044

class SysTrayManager:
    """
    Manages a Windows System Tray icon for Mount Everest Certificate Studio.
    Provides Show, Hide, Output Folder, Admin Portal, and Exit actions.
    """
    def __init__(self, app, title="Mount Everest Certificate Studio"):
        self.app = app
        self.title = title
        self.hwnd = None
        self.hicon = None
        self.thread = None
        self.running = False
        self._lock = threading.Lock()

    def start(self):
        if not HAS_WIN32:
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_tray_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.hwnd and HAS_WIN32:
            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
            self.hwnd = None

    def _run_tray_loop(self):
        try:
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = self._wnd_proc
            wc.lpszClassName = "MEC_CertificateStudio_Tray"
            wc.hInstance = win32gui.GetModuleHandle(None)

            try:
                atom = win32gui.RegisterClass(wc)
            except Exception:
                atom = win32gui.GetModuleHandle(None)

            self.hwnd = win32gui.CreateWindow(
                wc.lpszClassName,
                "MEC_Tray_Window",
                0, 0, 0, 0, 0, 0, 0,
                wc.hInstance,
                None
            )

            # Try to load official Mount Everest school logo icon or fallback to default
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "app_icon.ico")
            self.hicon = 0
            if os.path.exists(icon_path):
                try:
                    self.hicon = win32gui.LoadImage(
                        0,
                        icon_path,
                        win32con.IMAGE_ICON,
                        0, 0,
                        win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
                    )
                except Exception:
                    self.hicon = 0
            if not self.hicon:
                try:
                    self.hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
                except Exception:
                    self.hicon = 0

            nid = (
                self.hwnd,
                0,
                win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                WM_TRAY_CALLBACK,
                self.hicon,
                self.title[:127]
            )

            try:
                win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
            except Exception as e:
                # If non-interactive session or explorer not ready
                pass

            win32gui.PumpMessages()
        except Exception as e:
            pass

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY_CALLBACK:
            if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                # Left click: toggle or restore window
                self.app.after(10, self.app.restore_from_tray)
            elif lparam == win32con.WM_RBUTTONUP:
                # Right click: show context menu
                self._show_menu()
            return 0
        elif msg == win32con.WM_COMMAND:
            cmd = win32api.LOWORD(wparam)
            if cmd == 1001:
                self.app.after(10, self.app.restore_from_tray)
            elif cmd == 1002:
                from printer import open_output_folder
                self.app.after(10, open_output_folder)
            elif cmd == 1003:
                self.app.after(10, self.app._open_admin_portal)
            elif cmd == 1004:
                self.app.after(10, self.app.minimize_to_tray)
            elif cmd == 1005:
                self.app.after(10, self.app.exit_application)
            return 0
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _show_menu(self):
        try:
            pt = win32gui.GetCursorPos()
        except Exception:
            pt = (100, 100)

        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1001, "🎓 Certificate Studio")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1002, "📂 Open Output Folder")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1003, "🛠️ Admin Alignment Portal")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1004, "📥 Minimize to Tray")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1005, "❌ Exit Application")

        try:
            win32gui.SetForegroundWindow(self.hwnd)
            win32gui.TrackPopupMenu(
                menu,
                win32con.TPM_LEFTALIGN | win32con.TPM_RIGHTBUTTON,
                pt[0], pt[1], 0,
                self.hwnd,
                None
            )
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        finally:
            win32gui.DestroyMenu(menu)
