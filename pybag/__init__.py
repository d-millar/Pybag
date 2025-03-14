import ctypes
import pathlib
import platform
import shutil
import os
import winreg

__all__ = ['UserDbg', 'KernelDbg', 'CrashDbg', 'DbgEng']

def get_arch():
    if platform.architecture()[0] == '64bit':
        return 'amd64'
    else:
        return 'x86'

def append_arch(dbgroot):
    if platform.architecture()[0] == '64bit':
        return os.path.join(dbgroot, r'Debuggers\x64')
    else:
        return os.path.join(dbgroot, r'Debuggers\x86')

def create_cachedir(cachedir, _dbg_dir):
    '''Creates a cache of DLL files from WinDbg.  Necessary for the version of WinDbg installed from
       the Microsoft Store, due to file permission issues.'''

    # Create the cache directory.
    os.mkdir(cachedir)

    # Copy the DLL files we need to the new cache dir.
    shutil.copy(os.path.join(_dbg_dir, "dbgeng.dll"), cachedir)
    shutil.copy(os.path.join(_dbg_dir, "dbghelp.dll"), cachedir)
    shutil.copy(os.path.join(_dbg_dir, "dbgmodel.dll"), cachedir)

    # Create version.txt in the cache dir with the full filesystem path that we copied the DLLs from.
    # This way we can detect if the cache is stale and needs to be re-created (as the full source path
    # contains the WinDbg version number).
    with open(os.path.join(cachedir, "version.txt"), "w") as f:
        f.write(_dbg_dir)


def get_appdir_cache():
    appdir = find_app_install()
    if not appdir:
        return appdir

    # For versions of WinDbg installed from the Microsoft Store, we need to copy the DLL files we need
    # into a separate directory, otherwise permission problems will prevent us from loading them.
    # We'll copy them to a folder named "pybag_cache" in the user's home directory.
    cachedir = os.path.join(str(os.environ['LOCALAPPDATA']), "pybag_cache")
    if not os.path.isdir(cachedir):
        create_cachedir(cachedir, appdir)
    else:
        saved_dbgdir = ""
        with open(os.path.join(cachedir, "version.txt"), "r") as f:
            saved_dbgdir = f.read()
        # If the full filesystem path of WinDbg differs from where the contents of the cache dir were
        # obtained, then a newer version of WinDbg was installed on this system and the cache is stale.
        # In that case we will re-build the cache entirely using the new version.
        if saved_dbgdir != appdir:
            shutil.rmtree(cachedir)
            create_cachedir(cachedir, appdir)
    return cachedir


def find_app_install():
    # Loop through the keys in this registry path.  Any key names that refer to WinDbg likely correspond
    # to the install directory in C:\Program Files\WindowsApps\.
    packages_key = winreg.OpenKey(
        winreg.HKEY_CLASSES_ROOT,
        r"Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\PackageRepository\Packages")
    continue_flag = True
    i = 0
    while continue_flag:
        try:
            package_name = winreg.EnumKey(packages_key, i)
            if package_name.find("WinDbg") != -1 and package_name.find("_neutral_") == -1:
                dir = os.path.join("C:\\Program Files\\WindowsApps", package_name, get_arch())
                if os.path.exists(dir):
                    winreg.CloseKey(packages_key)
                    return dir
        except OSError:  # No more subkeys exist.
            continue_flag = False

        i += 1

    winreg.CloseKey(packages_key)
    return ''


def find_dbgdir():
    dbgdir = os.getenv('WINDBG_DIR')
    if dbgdir is not None and os.path.exists(dbgdir):
        return dbgdir
    try:
        roots_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SOFTWARE\Microsoft\Windows Kits\Installed Roots')
        dbgroot = winreg.QueryValueEx(roots_key, 'KitsRoot10')[0]
        dbgdir = append_arch(dbgroot)
        if os.path.exists(dbgdir):
            return dbgdir
    except FileNotFoundError:
        pass
    default_roots = [r'C:\Program Files\Windows Kits\10',
                     r'C:\Program Files (x86)\Windows Kits\10']
    for dbgroot in default_roots:
        dbgdir = append_arch(dbgroot)
        if os.path.exists(dbgdir):
            return dbgdir

    dbgdir = get_appdir_cache()
    if os.path.exists(dbgdir):
        return dbgdir

    raise RuntimeError("Windbg install directory not found!")


dbgdir = find_dbgdir()


# preload these to get correct DLLs loaded
try:
    ctypes.windll.LoadLibrary(os.path.join(dbgdir, 'dbgmodel.dll'))
except:
    pass

ctypes.windll.LoadLibrary(os.path.join(dbgdir, 'dbghelp.dll'))
ctypes.windll.LoadLibrary(os.path.join(dbgdir, 'dbgeng.dll'))

del platform
del os
del dbgdir
del ctypes
del winreg

from .pydbg      import DbgEng
from .crashdbg   import CrashDbg
from .kerneldbg  import KernelDbg
from .userdbg    import UserDbg

