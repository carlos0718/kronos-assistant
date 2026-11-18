"""Dónde están las carpetas del usuario en Windows, aunque las haya movido."""

import ctypes
import sys
import uuid
from pathlib import Path

from kronos_engine.core.platform import Folder

# Los identificadores que Windows les da a sus carpetas conocidas (KNOWNFOLDERID).
KNOWN_FOLDER_IDS = {
    Folder.DESKTOP: uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641"),
    Folder.DOCUMENTS: uuid.UUID("FDD39AD0-238F-46AF-ADB4-6C85480369C7"),
    Folder.DOWNLOADS: uuid.UUID("374DE290-123F-4565-9164-39C4925E467B"),
    Folder.PICTURES: uuid.UUID("33E28130-4E1E-4676-835A-98395C3BC3BB"),
    Folder.MUSIC: uuid.UUID("4BD8D571-6D19-48D3-BE97-422220080E43"),
    Folder.VIDEOS: uuid.UUID("18989B1D-99B5-455B-841C-AB7C74E4DDFC"),
    Folder.HOME: uuid.UUID("5E6C858F-0E22-4760-9AFE-EA3317B67173"),
}


def known_folder(folder: Folder) -> Path:
    """La ruta de la carpeta. Si Windows no la sabe, la de siempre dentro del perfil."""
    if sys.platform == "win32":
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.c_char_p,
            wintypes.DWORD,
            wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        found = ctypes.c_wchar_p()
        # El identificador va en el orden de bytes de Windows.
        result = shell32.SHGetKnownFolderPath(
            KNOWN_FOLDER_IDS[folder].bytes_le, 0, None, ctypes.byref(found)
        )
        try:
            if result == 0 and found.value:
                return Path(found.value)
        finally:
            ctypes.windll.ole32.CoTaskMemFree(found)
    return _fallback(folder)


def _fallback(folder: Folder) -> Path:
    home = Path.home()
    names = {
        Folder.DESKTOP: "Desktop",
        Folder.DOCUMENTS: "Documents",
        Folder.DOWNLOADS: "Downloads",
        Folder.PICTURES: "Pictures",
        Folder.MUSIC: "Music",
        Folder.VIDEOS: "Videos",
    }
    return home / names[folder] if folder in names else home
