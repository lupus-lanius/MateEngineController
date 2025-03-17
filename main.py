import subprocess
import time
import psutil
import sys
import os
import logging
import threading
from PIL import Image, ImageDraw
import pystray
import tkinter as tk
from tkinter import scrolledtext
from tkinter import font as tkfont

# Win32 imports
import win32gui
import win32con
import win32process
import win32api

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("desktop_mate.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DesktopMateController")

class LogViewer:
    def __init__(self, log_file):
        self.log_file = log_file
        self.window = None
        self.text_area = None
        self.auto_refresh = True
        self.refresh_rate = 1000  # ms
    
    def show(self):
        # If window already exists, just focus it
        if self.window and self.window.winfo_exists():
            self.window.focus_force()
            return
            
        # Create new window
        self.window = tk.Tk()
        self.window.title("DesktopMate Controller - Logs")
        self.window.geometry("800x500")
        
        # Configure font
        log_font = tkfont.Font(family="Consolas", size=10)
        
        # Create menu bar with options
        menu_bar = tk.Menu(self.window)
        options_menu = tk.Menu(menu_bar, tearoff=0)
        
        # Add auto-refresh toggle
        self.refresh_var = tk.BooleanVar(value=self.auto_refresh)
        options_menu.add_checkbutton(label="Auto-refresh", variable=self.refresh_var, 
                                    command=self.toggle_auto_refresh)
        
        # Add refresh now option
        options_menu.add_command(label="Refresh now", command=self.refresh_logs)
        
        # Add clear logs option
        options_menu.add_command(label="Clear display", command=self.clear_display)
        
        menu_bar.add_cascade(label="Options", menu=options_menu)
        self.window.config(menu=menu_bar)
        
        # Create scrolled text widget
        self.text_area = scrolledtext.ScrolledText(self.window, font=log_font, wrap=tk.WORD)
        self.text_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initial load of logs
        self.refresh_logs()
        
        # Set up auto-refresh
        if self.auto_refresh:
            self.schedule_refresh()
        
        # When window is closed, just hide it instead of destroying
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
    
    def hide(self):
        if self.window:
            self.window.withdraw()
    
    def toggle_auto_refresh(self):
        self.auto_refresh = self.refresh_var.get()
        if self.auto_refresh:
            self.schedule_refresh()
    
    def schedule_refresh(self):
        if self.auto_refresh and self.window and self.window.winfo_exists():
            self.refresh_logs()
            self.window.after(self.refresh_rate, self.schedule_refresh)
    
    def refresh_logs(self):
        if not self.window or not self.window.winfo_exists():
            return
            
        if not self.text_area:
            return
            
        try:
            # Get content from the log file
            with open(self.log_file, 'r') as file:
                content = file.read()
            
            # Save current position
            current_pos = self.text_area.yview()
            
            # Update text area
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, content)
            
            # Auto-scroll to end if we were already near the end
            if current_pos[1] > 0.9:
                self.text_area.see(tk.END)
            else:
                # Otherwise maintain the previous view position
                self.text_area.yview_moveto(current_pos[0])
                
        except Exception as e:
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(tk.END, f"Error loading log file: {e}")
    
    def clear_display(self):
        if self.text_area:
            self.text_area.delete(1.0, tk.END)

class DesktopMateController:
    def __init__(self):
        self.steam_app_id = "3301060"  # Steam AppID for DesktopMate
        self.process_name = "DesktopMate.exe"
        self.hwnd = None
        self.is_running = True
        self.icon = None
        self.log_viewer = None
        
        # Try to locate the icon file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(script_dir, "61bfbe1ba191abe79bf73e5a889071f8.ico")
        
    def start(self):
        logger.info("Starting DesktopMate Controller")
        
        # Launch DesktopMate through Steam
        self.launch_through_steam()
        
        # Wait for the application to start
        if not self.wait_for_application():
            logger.error("Failed to detect DesktopMate application")
            return False
        
        # Find the window and hide it from taskbar
        if not self.find_and_modify_window():
            logger.warning("Could not fully configure window, but will continue")
        
        # Start the monitoring thread
        self.start_monitoring()
        
        # Create and run the system tray icon
        self.create_tray_icon()
        
        return True
    
    def launch_through_steam(self):
        """Launch the application through Steam"""
        logger.info(f"Launching Steam app ID: {self.steam_app_id}")
        try:
            subprocess.Popen(f"start steam://run/{self.steam_app_id}", shell=True)
        except Exception as e:
            logger.error(f"Failed to launch Steam: {e}")
    
    def wait_for_application(self):
        """Wait for the application process to appear"""
        logger.info("Waiting for DesktopMate to launch...")
        
        max_wait_time = 60  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() == self.process_name.lower():
                        logger.info(f"DesktopMate process found (PID: {proc.info['pid']})")
                        # Increase wait time from 3 to 10 seconds to ensure the app is fully initialized
                        logger.info("Waiting 10 seconds for application to fully initialize...")
                        time.sleep(10)  # Give the window more time to initialize
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            time.sleep(0.5)
        
        return False
    
    def find_and_modify_window(self):
        """Find the application window and modify its properties"""
        logger.info("Searching for DesktopMate window...")
        
        # First attempt with more specific information
        retry_count = 0
        max_retries = 3
        success = False
        
        while not success and retry_count < max_retries:
            if self.find_window():
                # Add a short additional wait after finding the window
                logger.info("Window found, waiting a moment before modifying...")
                time.sleep(1)
                success = self.modify_window()
            
            if not success:
                retry_count += 1
                logger.info(f"Retry attempt {retry_count}...")
                time.sleep(2)
        
        return success
    
    def find_window(self):
        """Find the window by process name"""
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, process_id = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(process_id)
                    if process.name().lower() == self.process_name.lower():
                        class_name = win32gui.GetClassName(hwnd)
                        title = win32gui.GetWindowText(hwnd)
                        logger.info(f"Found window - PID: {process_id}, Class: {class_name}, Title: '{title}'")
                        windows.append((hwnd, class_name, title))
                except (psutil.NoSuchProcess, psutil.AccessDenied, Exception) as e:
                    logger.debug(f"Error checking window: {e}")
            return True
        
        windows = []
        win32gui.EnumWindows(callback, windows)
        
        if not windows:
            logger.warning("No windows found for DesktopMate")
            return False
            
        if len(windows) > 1:
            logger.warning(f"Multiple windows found ({len(windows)}), using the first one with a Unity class if possible")
            # Prefer Unity windows if possible
            for hwnd, class_name, title in windows:
                if "Unity" in class_name:
                    self.hwnd = hwnd
                    logger.info(f"Selected Unity window: {hwnd}")
                    return True
        
        # Take the first window if we didn't find a Unity one
        self.hwnd = windows[0][0]
        logger.info(f"Selected window: {self.hwnd}")
        return True
    
    def modify_window(self):
        """Modify the window to hide from taskbar but remain visible"""
        if not self.hwnd:
            logger.error("No window handle available")
            return False
        
        try:
            # Make sure window is not minimized
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
            
            # Make window visible
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
            time.sleep(0.1)
            
            # Get current style
            style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            
            # Remove app window style and add tool window style to hide from taskbar
            new_style = (style & ~win32con.WS_EX_APPWINDOW) | win32con.WS_EX_TOOLWINDOW
            
            # Add no-activate style to prevent stealing focus
            new_style |= win32con.WS_EX_NOACTIVATE
            
            # Set the new style
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, new_style)
            time.sleep(0.2)
            
            # Try to set as child of desktop
            self.set_parent_to_desktop()
            
            # Make sure window is still visible but not activated
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOWNOACTIVATE)
            
            logger.info("Successfully modified window properties")
            return True
            
        except Exception as e:
            logger.error(f"Error modifying window: {e}")
            return False
    
    def set_parent_to_desktop(self):
        """Set the desktop as the parent window"""
        try:
            # Try Program Manager first
            desktop_hwnd = win32gui.FindWindow("Progman", None)
            
            if not desktop_hwnd:
                # Try WorkerW as alternative
                desktop_hwnd = win32gui.FindWindow("WorkerW", None)
            
            if desktop_hwnd and self.hwnd:
                win32gui.SetParent(self.hwnd, desktop_hwnd)
                logger.info(f"Set parent to desktop: {desktop_hwnd}")
                return True
                
            logger.warning("Could not find desktop window")
            return False
            
        except Exception as e:
            logger.error(f"Error setting parent: {e}")
            return False
    
    def start_monitoring(self):
        """Start monitoring thread to check if the application is still running"""
        monitor_thread = threading.Thread(target=self.monitor_process, daemon=True)
        monitor_thread.start()
        logger.info("Process monitoring started")
    
    def monitor_process(self):
        """Monitor if the process is still running"""
        while self.is_running:
            process_running = False
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() == self.process_name.lower():
                        process_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            if not process_running:
                logger.info("DesktopMate process ended, exiting controller")
                self.is_running = False
                if self.icon:
                    self.icon.stop()
                break
                
            time.sleep(2)
    
    def create_tray_icon(self):
        """Create system tray icon"""
        logger.info("Creating system tray icon")
        
        # Create icon image
        if os.path.isfile(self.icon_path):
            icon_image = Image.open(self.icon_path)
        else:
            # Create a simple blue square with "DM" text if icon not found
            icon_image = Image.new('RGB', (64, 64), color=(73, 109, 137))
            d = ImageDraw.Draw(icon_image)
            d.text((15, 20), "DM", fill=(255, 255, 255))
            logger.warning(f"Icon file not found: {self.icon_path}, using generated icon")
        
        # Define menu items
        def exit_app(icon):
            self.exit_application()
            
        def restart_app(icon):
            self.restart_application()
            
        def view_logs(icon):
            self.show_logs()
        
        # Create menu with View Logs option
        menu = pystray.Menu(
            pystray.MenuItem('View Logs', view_logs),
            pystray.MenuItem('Restart DesktopMate', restart_app),
            pystray.MenuItem('Exit DesktopMate', exit_app)
        )
        
        # Create icon
        self.icon = pystray.Icon(
            "desktop_mate_controller",
            icon=icon_image,
            title="DesktopMate Controller",
            menu=menu
        )
        
        logger.info("Running system tray icon")
        self.icon.run()
    
    def show_logs(self):
        """Show the log viewer window"""
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_mate.log")
        
        # Create log viewer if it doesn't exist
        if not self.log_viewer:
            self.log_viewer = LogViewer(log_file)
        
        # Show the log viewer
        self.log_viewer.show()
    
    def exit_application(self):
        """Exit both the controller and DesktopMate"""
        logger.info("Exiting DesktopMate and controller")
        self.is_running = False
        
        try:
            # Try to gracefully close the window
            if self.hwnd and win32gui.IsWindow(self.hwnd):
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
                
            # Wait a bit and check if process is still running
            time.sleep(3)
            
            # Force kill if still running
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() == self.process_name.lower():
                        logger.info(f"Force killing process: {proc.info['pid']}")
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.error(f"Error exiting application: {e}")
        
        if self.icon:
            self.icon.stop()
        
        sys.exit(0)
    
    def restart_application(self):
        """Restart the DesktopMate application"""
        logger.info("Restarting DesktopMate")
        
        # Close current instance
        try:
            if self.hwnd and win32gui.IsWindow(self.hwnd):
                win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            
            time.sleep(2)
            
            # Force kill if still running
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'].lower() == self.process_name.lower():
                        proc.kill()
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
                    
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error closing application: {e}")
        
        # Restart this script
        python = sys.executable
        script = os.path.abspath(__file__)
        
        if self.icon:
            self.icon.stop()
            
        os.execl(python, python, script)

if __name__ == "__main__":
    controller = DesktopMateController()
    controller.start()