# PyInstaller spec for 360 SMART (onedir build; wrapped by Inno Setup into 360SmartSetup.exe).
# Build:  pyinstaller packaging/smart360.spec --noconfirm   (from the windows/ folder)
# onedir (not onefile): no self-extraction at start -> faster start, fewer antivirus false positives.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 - provided by PyInstaller
ASSETS = ROOT / "smart360" / "assets"

hidden = (
    collect_submodules("winrt.windows.media.ocr")
    + collect_submodules("winrt.windows.graphics.imaging")
    + collect_submodules("winrt.windows.storage.streams")
    + collect_submodules("winrt.windows.globalization")
    + collect_submodules("winrt.windows.foundation")
    + ["keyring.backends.Windows", "PySide6.QtMultimedia"]
)

# Qt modules we never use - excluding them saves ~150 MB.
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuick3D", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtBluetooth",
    "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtRemoteObjects",
    "tkinter", "matplotlib", "scipy", "pytest", "hypothesis", "IPython",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "smart360" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=[(str(ASSETS), "smart360/assets")],
    hiddenimports=hidden,
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="360Smart",
    icon=str(ASSETS / "icon.ico"),
    console=False,
    disable_windowed_traceback=False,
    version=str(ROOT / "packaging" / "version_info.txt"),
    upx=False,  # UPX-packed binaries are a classic antivirus trigger
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="360Smart")  # noqa: F821
