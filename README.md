# Desktop Mate Controller

A Python application that launches DesktopMate through Steam and manages its window visibility, keeping it visible on your desktop while hiding it from the taskbar.

## Features

- Launches DesktopMate through Steam automatically
- Makes the character visible on desktop but hidden from taskbar
- Provides system tray icon for easy control
- Monitors the application and exits when DesktopMate closes
- Includes restart functionality
- Detailed logging for troubleshooting

## Requirements

- Windows operating system
- Steam installed with DesktopMate in your library
- Python 3.8 or higher
- Required Python packages:
  - psutil
  - pywin32
  - pystray
  - pillow

## Installation

1. Clone or download this repository
2. Install the required dependencies:
