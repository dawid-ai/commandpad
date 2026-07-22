# scripts/install_autostart.py
"""Create a Startup shortcut that runs commandpad at login (no console window)."""
import os
import sys

def main():
    startup = os.path.join(os.environ["APPDATA"],
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    target = os.path.join(repo, "src", "main.py")
    shortcut = os.path.join(startup, "commandpad.lnk")

    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    lnk = shell.CreateShortCut(shortcut)
    lnk.Targetpath = pythonw
    lnk.Arguments = f'"{target}"'
    lnk.WorkingDirectory = repo
    lnk.save()
    print(f"Installed autostart: {shortcut}")

if __name__ == "__main__":
    main()
