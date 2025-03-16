; HideDesktopMate.ahk - Launches DesktopMate through Steam and manages visibility via tray icon

; Script settings
#SingleInstance Force   ; Only allow one instance of this script to run

; Replace with the actual Steam AppID for DesktopMate
SteamAppID := "3301060"  ; Steam AppID for DesktopMate
AppTitle := "ahk_exe DesktopMate.exe"  ; Match by executable name
MaxWaitTime := 60  ; Maximum wait time in seconds
isHidden := true   ; Track if window is hidden
MaxRetries := 3    ; Number of retries for critical operations

; Show initial notification
ToolTip("Starting DesktopMate, please wait...", 200, 200)

; Launch the game through Steam
Run("steam://run/" . SteamAppID)

; Wait for Steam to initialize - reduced to 5 seconds
Sleep(5000)

; Show waiting notification
ToolTip("Waiting for DesktopMate to launch...", 200, 200)

; Wait for the application window to appear
WinWaitStatus := WinWait(AppTitle,, MaxWaitTime)
if !WinWaitStatus {
    ToolTip()
    MsgBox("Could not detect DesktopMate window after " MaxWaitTime " seconds.", "Error", "T3")
    ExitApp()
}

; Give the window time to fully initialize
Sleep(3000)

; Get process information for icon
ProcessPath := GetProcessPath("DesktopMate.exe")

; Initialize tray menu with the correct icon path
InitTrayMenu(ProcessPath)

; Hide the window with retry logic
ToolTip("DesktopMate found! Now configuring window...", 200, 200)
Sleep(1000)

; Try hiding with retries
retryCount := 0
success := false

while (!success && retryCount < MaxRetries) {
    success := HideDesktopMate()
    if (!success) {
        retryCount++
        ToolTip("Retry attempt " retryCount "...", 200, 200)
        Sleep(2000)
    }
}

if (!success) {
    ToolTip("Warning: Had trouble fully configuring window. Will continue anyway.", 200, 200)
    Sleep(3000)
}

; Display success notification
ToolTip("DesktopMate is now running hidden. Use the tray icon to control it.", 200, 200)
Sleep(3000)
ToolTip()

; Set up a timer to check if DesktopMate is still running
SetTimer(CheckIfAppRunning, 2000)  ; Check every 2 seconds

; Keep script running to maintain tray icon
return

; Function to check if DesktopMate is still running
CheckIfAppRunning() {
    global AppTitle
    if !WinExist(AppTitle) {
        ; DesktopMate has been closed, exit the script too
        ToolTip("DesktopMate has closed. Exiting script...", 200, 200)
        Sleep(1500)
        ToolTip()
        ExitApp()
    }
}

; Function to get the full path of a running process
GetProcessPath(exeName) {
    try {
        for process in ComObject("WbemScripting.SWbemLocator").ConnectServer().ExecQuery("SELECT ExecutablePath FROM Win32_Process WHERE Name = '" exeName "'")
            return process.ExecutablePath
    } catch Error as e {
        ; Silently fail and return empty string
    }
    return ""  ; Return empty string if process not found
}

InitTrayMenu(iconPath := "") {
    ; Set a nicer tray icon tooltip name
    A_IconTip := "DesktopMate Controller"
    
    ; Try to use the application's icon for the tray
    if (iconPath && FileExist(iconPath)) {
        try {
            TraySetIcon(iconPath)  ; Use the full path to the executable
        } catch {
            ; If that fails, use a system icon
        }
    }

    ; If no icon was found or it failed to set, try to use a system icon
    if (!iconPath || !FileExist(iconPath)) {
        try {
            ; Use a system icon that looks nice - 5 is the "computer" icon
            TraySetIcon("shell32.dll", 5)  
        } catch {
            ; Even if that fails, the script will continue
        }
    }
    
    ; Create custom tray menu
    A_TrayMenu.Delete()  ; Clear default menu
    A_TrayMenu.Add("Exit DesktopMate", ExitScript)  ; Only exit option
    
    ; Optional: Add a restart option
    A_TrayMenu.Add("Restart DesktopMate", RestartApp)
    
    ; Set default menu item
    A_TrayMenu.Default := "Exit DesktopMate"
}

; Hide the DesktopMate window with improved error handling
HideDesktopMate() {
    global isHidden, AppTitle
    
    ; Ensure window exists and get a fresh handle
    hwnd := WinExist(AppTitle)
    if (!hwnd) {
        ; Try to find the window by process name as fallback
        for window in WinGetList() {
            ProcessName := WinGetProcessName(window)
            if (ProcessName = "DesktopMate.exe") {
                hwnd := window
                break
            }
        }
        
        if (!hwnd) {
            return false
        }
    }
    
    try {
        ; Ensure window is not minimized
        if (WinGetMinMax(hwnd) = -1) {
            WinRestore(hwnd)
            Sleep(300)
        }
        
        ; Make window visible and active with multiple attempts
        retryActivate := 0
        while (retryActivate < 3) {
            WinShow(hwnd)
            WinActivate(hwnd)
            Sleep(300)
            
            ; Check if window is active
            if (WinActive(hwnd)) {
                break
            }
            retryActivate++
            Sleep(300)
        }
        
        ; Set window to be fully visible
        WinSetTransparent(255, hwnd)
        Sleep(100)
        
        ; Make it a desktop component rather than a tool window
        WinSetExStyle("-0x00040000", hwnd)  ; Remove WS_EX_APPWINDOW
        Sleep(50)
        WinSetExStyle("+0x00000080", hwnd)  ; Add WS_EX_TOOLWINDOW
        Sleep(50)
        
        ; Add WS_EX_NOACTIVATE to prevent stealing focus
        WinSetExStyle("+0x08000000", hwnd)  ; Add WS_EX_NOACTIVATE
        Sleep(50)
        
        ; Set as child of desktop with retry logic
        retry := 0
        parentSuccess := false
        
        while (!parentSuccess && retry < 3) {
            parentSuccess := SetParentToDesktop(hwnd)
            if (!parentSuccess) {
                retry++
                Sleep(300)
            }
        }
        
        ; Final step - ensure window stays visible but not in taskbar
        ; Use alternative approaches to ensure it works
        
        ; First try with ShowWindow API
        DllCall("ShowWindow", "Ptr", hwnd, "Int", 4) ; SW_SHOWNOACTIVATE
        Sleep(100)
        
        ; Then make sure it's still visible
        if (!WinExist(hwnd)) {
            WinShow(hwnd)
        }
        
        ; Remove from Alt-Tab list
        WinSetExStyle("+0x00000080", hwnd)  ; WS_EX_TOOLWINDOW
        
        isHidden := true
        return true
    } catch Error as e {
        ToolTip("Warning: " e.Message, 200, 200)
        Sleep(2000)
        ToolTip()
        return false
    }
}

SetParentToDesktop(targetHwnd) {
    try {
        ; Find desktop window (Program Manager or WorkerW)
        desktopHwnd := WinExist("ahk_class Progman")
        
        if (!desktopHwnd) {
            ; Try alternative desktop window
            desktopHwnd := WinExist("ahk_class WorkerW")
        }
        
        if (!desktopHwnd) {
            ; Last resort - try to find Shell_TrayWnd's parent
            shellHwnd := WinExist("ahk_class Shell_TrayWnd")
            if (shellHwnd) {
                desktopHwnd := DllCall("GetParent", "Ptr", shellHwnd, "Ptr")
            }
        }
        
        if (desktopHwnd && targetHwnd) {
            ; Set the desktop as parent using DllCall
            result := DllCall("SetParent", "Ptr", targetHwnd, "Ptr", desktopHwnd)
            return result > 0
        }
        return false
    } catch {
        return false
    }
}

; Exit both applications
ExitScript(*) {
    try {
        ; Show the window before closing to ensure it closes properly
        WinShow(AppTitle)
        Sleep(500)
        WinClose(AppTitle)
        
        ; If app doesn't close cleanly, force it after 3 seconds
        Sleep(3000)
        if WinExist(AppTitle) {
            ProcessClose("DesktopMate.exe")
        }
    } catch {
        ; Ignore errors if window doesn't exist
    }
    
    ExitApp()
}

; Restart the application
RestartApp(*) {
    try {
        ; Close current instance
        WinClose(AppTitle)
        Sleep(2000)
        
        ; If app doesn't close cleanly, force it
        if WinExist(AppTitle) {
            ProcessClose("DesktopMate.exe")
            Sleep(1000)
        }
        
        ; Relaunch the script itself
        Run(A_ScriptFullPath)
    } catch {
        ; Ignore errors
    }
    
    ExitApp()
}