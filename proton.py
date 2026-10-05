import os
import sys
import subprocess
import platform
import shutil
import tarfile
import tempfile
from pathlib import Path
try:
    import requests
except ImportError:
    print("\033[91m[ERROR]\033[0m El módulo 'requests' no está instalado.")
    print("Instálalo con: pip install requests")
    sys.exit(1)

# Detectar sistema operativo y arquitectura
SYSTEM = platform.system()
ARCH = platform.machine()

# Mapeo de arquitecturas para mostrar nombres más claros
ARCH_NAMES = {
    "x86_64":  "x86_64 (64-bit)",
    "AMD64":   "x86_64 (64-bit)",
    "aarch64": "ARM64 (64-bit)",
    "arm64":   "ARM64 (64-bit)",
    "i386":    "x86 (32-bit)",
    "i686":    "x86 (32-bit)"
}
ARCH_DISPLAY = ARCH_NAMES.get(ARCH, ARCH)

# Mapeo de arquitecturas para filtrar assets
ARCH_FILTERS = {
    "x86_64":  ["x86_64", "x86-64", "amd64", "AMD64"],
    "AMD64":   ["x86_64", "x86-64", "amd64", "AMD64"],
    "aarch64": ["aarch64", "arm64", "ARM64"],
    "arm64":   ["aarch64", "arm64", "ARM64"],
    "i386":    ["i386", "i686", "x86"],
    "i686":    ["i386", "i686", "x86"]
}

# Configuración de launchers y sus rutas
LAUNCHERS = {
    "steam_native": {
        "name":       "Steam (Nativo)",
        "path":       Path.home() / ".local/share/Steam/compatibilitytools.d",
        "flatpak_id": None
    },
    "steam_flatpak": {
        "name":       "Steam (Flatpak)",
        "path":       Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",
        "flatpak_id": "com.valvesoftware.Steam"
    },
    "lutris_flatpak": {
        "name":       "Lutris (Flatpak)",
        "path":       Path.home() / ".var/app/net.lutris.Lutris/data/lutris/runners/proton",
        "flatpak_id": "net.lutris.Lutris"
    },
    "heroic_flatpak": {
        "name":       "Heroic Games Launcher (Flatpak)",
        "path":       Path.home() / ".var/app/com.heroicgameslauncher.hgl/config/heroic/tools/proton",
        "flatpak_id": "com.heroicgameslauncher.hgl"
    },
    "faugus_flatpak": {
        "name":       "Faugus Launcher (Flatpak)",
        "path":       Path.home() / ".var/app/com.faugus.Launcher/data/faugus-launcher/proton",
        "flatpak_id": "com.faugus.Launcher"
    }
}

# Nombres fijos de instalación + prefijo para detectar carpetas viejas
REPOS = {
    "1": {
        "name":          "Proton-GE",
        "owner":         "GloriousEggroll",
        "repo":          "proton-ge-custom",
        "install_name":  "Proton-GE Latest",
        "folder_prefix": "GE-Proton"
    },
    "2": {
        "name":          "Proton-CachyOS",
        "owner":         "CachyOS",
        "repo":          "proton-cachyos",
        "install_name":  "Proton-CachyOS Latest",
        "folder_prefix": "proton-cachyos"
    }
}


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    print("\033[95m" + "=" * 50)
    print("  INSTALADOR DE PROTON (GE / CACHYOS)")
    print(f"  Sistema: \033[96m{SYSTEM}\033[95m | Arquitectura: \033[96m{ARCH_DISPLAY}\033[95m")
    print("=" * 50 + "\033[0m")


def check_architecture_compatibility():
    """Verifica si la arquitectura es compatible con Proton."""
    compatible_archs = ["x86_64", "AMD64", "aarch64", "arm64"]
    if ARCH not in compatible_archs:
        print(f"\n\033[93m[ADVERTENCIA]\033[0m La arquitectura detectada ({ARCH_DISPLAY}) puede no ser totalmente compatible con Proton.")
        print("\033[93m[INFO]\033[0m Proton está optimizado principalmente para x86_64.")
        continue_choice = input("¿Deseas continuar de todos modos? (s/n): ").strip().lower()
        if continue_choice != 's':
            print("\033[91m[Cancelado]\033[0m Saliendo del script.")
            sys.exit(0)


def detect_installed_launchers():
    """Detecta qué launchers están instalados en el sistema."""
    detected = []
    steam_native_path = Path.home() / ".local/share/Steam"
    if steam_native_path.exists():
        detected.append("steam_native")

    if shutil.which("flatpak"):
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True, text=True, check=True
            )
            installed_apps = result.stdout.strip().split('\n')
            for launcher_key, launcher_info in LAUNCHERS.items():
                if launcher_info.get("flatpak_id") and launcher_info["flatpak_id"] in installed_apps:
                    detected.append(launcher_key)
        except subprocess.CalledProcessError:
            pass
    return detected


def select_install_location():
    """Permite al usuario seleccionar dónde instalar Proton."""
    detected_launchers = detect_installed_launchers()
    if not detected_launchers:
        print("\n\033[91m[ERROR]\033[0m No se detectó ningún launcher compatible.")
        print("\033[93m[INFO]\033[0m Instala Steam, Lutris, Heroic o Faugus para continuar.")
        return None

    print("\n\033[96m[SELECCIÓN]\033[0m Launchers detectados:\n")
    options = []
    for i, launcher_key in enumerate(detected_launchers, 1):
        launcher_info = LAUNCHERS[launcher_key]
        print(f"  {i}. {launcher_info['name']}")
        print(f"     Ruta: \033[90m{launcher_info['path']}\033[0m")
        options.append(launcher_key)
    print(f"\n  0. Cancelar")

    while True:
        choice = input("\nSelecciona dónde instalar (0 para cancelar): ").strip()
        if choice == "0":
            return None
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                selected_key = options[choice_idx]
                selected_launcher = LAUNCHERS[selected_key]
                print(f"\n\033[92m[OK]\033[0m Instalando en: {selected_launcher['name']}")
                return selected_launcher['path']
            else:
                print("\033[91mOpción no válida.\033[0m")
        except ValueError:
            print("\033[91mPor favor, ingresa un número.\033[0m")


def ensure_dir(directory):
    """Crea el directorio si no existe."""
    if not directory.exists():
        print(f"\033[93m[INFO]\033[0m Creando directorio: {directory}")
        directory.mkdir(parents=True, exist_ok=True)


def detect_package_manager():
    """Detecta el gestor de paquetes disponible en el sistema."""
    managers = {
        "pacman":       ["pacman", "-S", "--noconfirm", "aria2"],
        "apt":          ["apt", "install", "-y", "aria2"],
        "dnf":          ["dnf", "install", "-y", "aria2"],
        "zypper":       ["zypper", "install", "-y", "aria2"],
        "apk":          ["apk", "add", "aria2"],
        "xbps-install": ["xbps-install", "-y", "aria2"],
        "emerge":       ["emerge", "--ask=n", "net-misc/aria2"],
        "brew":         ["brew", "install", "aria2"]
    }
    for manager, cmd in managers.items():
        if shutil.which(manager):
            return manager, cmd
    return None, None


def install_aria2():
    """Detecta el SO e instala aria2 si no está presente."""
    if shutil.which("aria2c"):
        print("\033[92m[OK]\033[0m aria2 ya está instalado.")
        return True

    print("\n\033[93m[AVISO]\033[0m aria2 no está instalado. Se necesita para descargas multihilo.")
    if SYSTEM == "Windows":
        print("\033[91m[ERROR]\033[0m La instalación automática de aria2 no está soportada en Windows.")
        print("Descárgalo manualmente de: https://aria2.github.io/")
        return False

    manager, cmd = detect_package_manager()
    if not manager:
        print("\033[91m[ERROR]\033[0m No se pudo detectar un gestor de paquetes compatible.")
        print("Instala aria2 manualmente.")
        return False

    print(f"\n\033[96m[INFO]\033[0m Gestor de paquetes detectado: \033[1m{manager}\033[0m")
    install_choice = input("¿Deseas instalar aria2 automáticamente? (s/n): ").strip().lower()
    if install_choice != 's':
        print("\033[93m[INFO]\033[0m Instalación cancelada. Se usará curl (1 hilo) como fallback.")
        return False

    if SYSTEM == "Linux" and manager != "brew":
        cmd = ["sudo"] + cmd

    print(f"\n\033[96m[INSTALANDO]\033[0m Ejecutando: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("\033[92m[ÉXITO]\033[0m aria2 instalado correctamente.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\033[91m[ERROR]\033[0m Falló la instalación de aria2: {e}")
        return False
    except FileNotFoundError:
        print("\033[91m[ERROR]\033[0m No se encontró el comando sudo. Ejecuta el script con permisos adecuados.")
        return False


def check_zstd_support():
    """Verifica si el sistema puede descomprimir archivos .tar.zst."""
    if shutil.which("zstd") or shutil.which("unzstd"):
        return True
    try:
        result = subprocess.run(
            ["tar", "--help"], capture_output=True, text=True, timeout=5
        )
        if "zstd" in result.stdout.lower():
            return True
    except Exception:
        pass
    return False


def install_zstd():
    """Ofrece instalar zstd si no está disponible."""
    if check_zstd_support():
        return True

    print("\n\033[93m[AVISO]\033[0m zstd no está disponible. Es necesario para descomprimir Proton-CachyOS (.tar.zst).")
    manager, cmd = detect_package_manager()
    if not manager:
        print("\033[91m[ERROR]\033[0m Instala zstd manualmente desde tu gestor de paquetes.")
        return False

    pkg_cmd = [c.replace("aria2", "zstd") for c in cmd]
    print(f"\n\033[96m[INFO]\033[0m Gestor detectado: \033[1m{manager}\033[0m")
    install_choice = input("¿Deseas instalar zstd automáticamente? (s/n): ").strip().lower()
    if install_choice != 's':
        print("\033[91m[ERROR]\033[0m Sin zstd no se podrá descomprimir el archivo.")
        return False

    if SYSTEM == "Linux" and manager != "brew":
        pkg_cmd = ["sudo"] + pkg_cmd

    try:
        subprocess.run(pkg_cmd, check=True)
        print("\033[92m[ÉXITO]\033[0m zstd instalado correctamente.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\033[91m[ERROR]\033[0m Falló la instalación de zstd: {e}")
        return False


def get_latest_release(owner, repo):
    """Obtiene la información de la última release desde la API de GitHub."""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"\033[91m[ERROR]\033[0m No se pudo conectar a GitHub: {e}")
        return None


def download_with_progress(url, dest_path):
    """Descarga el archivo usando aria2 (16 hilos) o curl (fallback)."""
    print(f"\n\033[96m[DESCARGA]\033[0m Iniciando descarga con aceleración...")
    if shutil.which("aria2c"):
        cmd = [
            "aria2c", "-x", "16", "-s", "16", "-j", "16",
            "--console-log-level=warn", "--summary-interval=1",
            "-d", str(dest_path.parent), "-o", dest_path.name, url
        ]
    else:
        print("\033[93m[AVISO]\033[0m Usando curl (1 hilo) como fallback.")
        cmd = ["curl", "-L", "-#", "-o", str(dest_path), url]

    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        print("\033[91m[ERROR]\033[0m La descarga falló.")
        return False


def get_archive_root_folder(archive_path):
    """Obtiene el nombre de la carpeta raíz dentro del archivo comprimido."""
    try:
        with tarfile.open(archive_path, 'r:*') as tar:
            root = tar.getnames()[0].split('/')[0]
            return root
    except Exception:
        return None


def find_compatible_asset(assets):
    """Busca el asset compatible con la arquitectura del sistema."""
    arch_keywords = ARCH_FILTERS.get(ARCH, [])

    for asset in assets:
        asset_name = asset['name'].lower()
        if asset_name.endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
            for keyword in arch_keywords:
                if keyword.lower() in asset_name:
                    print(f"\033[92m[OK]\033[0m Asset compatible encontrado: {asset['name']}")
                    return asset['browser_download_url'], asset['name']

    for asset in assets:
        asset_name = asset['name'].lower()
        if asset_name.endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
            other_archs = ["aarch64", "arm64", "i386", "i686"]
            if ARCH in ["x86_64", "AMD64"]:
                if not any(other in asset_name for other in other_archs):
                    print(f"\033[93m[INFO]\033[0m Usando asset genérico: {asset['name']}")
                    return asset['browser_download_url'], asset['name']

    return None, None


# ============================================================
#  LECTURA Y COMPARACIÓN INTELIGENTE DEL ARCHIVO "version"
# ============================================================

def get_installed_version(install_path):
    """Lee el archivo 'version' de una instalación de Proton.
    Devuelve el contenido crudo o None si no existe."""
    version_file = install_path / "version"
    if not version_file.exists():
        return None
    try:
        with open(version_file, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception as e:
        print(f"\033[93m[AVISO]\033[0m No se pudo leer {version_file}: {e}")
        return None


def is_version_up_to_date(installed_content, latest_tag):
    """Compara el contenido del archivo 'version' con el tag de GitHub.
    Maneja formatos como:
      - 'GE-Proton11-7'                          (GE puro)
      - '1791146054 cachyos-11.0-20261005-slr'    (CachyOS con timestamp)
      - 'cachyos-11.0-20261005-slr'               (CachyOS sin timestamp)
    Devuelve True si están actualizados."""
    if not installed_content or not latest_tag:
        return False

    installed_clean = installed_content.strip()
    latest_clean = latest_tag.strip()

    # 1) Coincidencia exacta
    if installed_clean == latest_clean:
        return True

    # 2) El tag está contenido en el contenido del archivo
    if latest_clean in installed_clean:
        return True

    # 3) Comparar la última palabra (después del timestamp)
    installed_parts = installed_clean.split()
    if len(installed_parts) > 1 and installed_parts[-1] == latest_clean:
        return True

    return False


def clean_version_display(version_string):
    """Quita el timestamp inicial para mostrar solo la versión legible."""
    if not version_string:
        return "Desconocida"
    parts = version_string.strip().split()
    if len(parts) > 1 and parts[0].isdigit():
        return " ".join(parts[1:])
    return version_string


# ============================================================
#  MANEJO DE CARPETAS VIEJAS (versiones con nombre dinámico)
# ============================================================

def find_previous_versions(install_dir, folder_prefix, install_name):
    """Busca carpetas viejas del mismo Proton que NO sean el nombre fijo."""
    previous_versions = []
    if not install_dir.exists():
        return previous_versions
    for folder in install_dir.iterdir():
        if not folder.is_dir():
            continue
        if folder.name == install_name:
            continue
        if folder_prefix.lower() not in folder.name.lower():
            continue
        previous_versions.append(folder)
    return previous_versions


def handle_previous_versions(install_dir, folder_prefix, install_name):
    """Ofrece eliminar carpetas viejas con nombre dinámico."""
    previous_versions = find_previous_versions(install_dir, folder_prefix, install_name)
    if not previous_versions:
        return True

    print(f"\n\033[93m[VERSIONES ANTERIORES]\033[0m Se encontraron {len(previous_versions)} carpeta(s) vieja(s):\n")
    for i, version in enumerate(previous_versions, 1):
        print(f"  {i}. {version.name}")
    print(f"\n\033[96m[ACCIÓN]\033[0m ¿Qué deseas hacer?")
    print("  1. Eliminar todas las versiones anteriores")
    print("  2. Mantener todas")
    print("  3. Seleccionar cuáles eliminar")

    while True:
        choice = input("\nSelecciona una opción (1-3): ").strip()
        if choice == "1":
            for version in previous_versions:
                try:
                    shutil.rmtree(version)
                    print(f"  \033[92m✓\033[0m {version.name} eliminada")
                except Exception as e:
                    print(f"  \033[91m✗\033[0m Error al eliminar {version.name}: {e}")
            return True
        elif choice == "2":
            print(f"\n\033[93m[INFO]\033[0m Manteniendo todas.")
            return True
        elif choice == "3":
            selection = input("Ingresa los números separados por comas (ej: 1,3): ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                to_delete = [previous_versions[i] for i in indices if 0 <= i < len(previous_versions)]
                if not to_delete:
                    print("\033[91m[ERROR]\033[0m No se seleccionaron versiones válidas.")
                    continue
                for version in to_delete:
                    try:
                        shutil.rmtree(version)
                        print(f"  \033[92m✓\033[0m {version.name} eliminada")
                    except Exception as e:
                        print(f"  \033[91m✗\033[0m Error: {e}")
                return True
            except (ValueError, IndexError):
                print("\033[91m[ERROR]\033[0m Selección inválida.")
                continue
        else:
            print("\033[91mOpción no válida.\033[0m")


# ============================================================
#  INSTALACIÓN PRINCIPAL
# ============================================================

def install_proton(choice_key, force=False):
    """Flujo principal para descargar e instalar una versión de Proton."""
    repo_info = REPOS[choice_key]
    install_name = repo_info['install_name']

    print(f"\n\033[92m[INFO]\033[0m Buscando última versión de {repo_info['name']}...")
    release = get_latest_release(repo_info['owner'], repo_info['repo'])
    if not release:
        return

    tag_name = release['tag_name']
    print(f"\033[92m[ÉXITO]\033[0m Última versión en GitHub: \033[1m{tag_name}\033[0m")

    # Seleccionar ubicación de instalación
    install_dir = select_install_location()
    if not install_dir:
        print("\033[91m[Cancelado]\033[0m Instalación abortada.")
        return
    ensure_dir(install_dir)

    install_path = install_dir / install_name

    # Verificar versión instalada leyendo el archivo "version"
    installed_version = get_installed_version(install_path)
    if installed_version:
        print(f"\033[96m[INFO]\033[0m Versión instalada: \033[1m{clean_version_display(installed_version)}\033[0m")

        if is_version_up_to_date(installed_version, tag_name) and not force:
            print(f"\033[92m[OK]\033[0m {repo_info['name']} ya está en la última versión.")
            print("\033[93m[INFO]\033[0m Usa 'forzar reinstalación' si quieres reinstalar de todos modos.")
            return

        if not is_version_up_to_date(installed_version, tag_name):
            print(f"\033[93m[UPDATE]\033[0m Nueva versión disponible: \033[1m{tag_name}\033[0m")
            print(f"           Actualmente instalada: {clean_version_display(installed_version)}")
    else:
        print(f"\033[93m[INFO]\033[0m {install_name} no está instalado.")

    # Verificar zstd si el asset es .tar.zst (CachyOS)
    for asset in release.get('assets', []):
        if asset['name'].lower().endswith('.tar.zst'):
            if not install_zstd():
                print("\033[91m[Cancelado]\033[0m No se puede continuar sin zstd.")
                return
            break

    # Ofrecer limpiar carpetas viejas con nombre dinámico
    handle_previous_versions(install_dir, repo_info['folder_prefix'], install_name)

    # Eliminar la carpeta fija si ya existe (antes de extraer la nueva)
    if install_path.exists():
        print(f"\n\033[93m[INFO]\033[0m Eliminando versión anterior: {install_path}")
        try:
            shutil.rmtree(install_path)
            print(f"\033[92m[OK]\033[0m Carpeta anterior eliminada.")
        except Exception as e:
            print(f"\033[91m[ERROR]\033[0m No se pudo eliminar: {e}")
            if input("¿Continuar de todos modos? (s/n): ").strip().lower() != 's':
                return

    # Buscar asset compatible
    asset_url, asset_name = find_compatible_asset(release['assets'])
    if not asset_url:
        print("\033[91m[ERROR]\033[0m No se encontró un archivo compatible con tu arquitectura.")
        print(f"\033[93m[INFO]\033[0m Arquitectura: {ARCH_DISPLAY}")
        print("\033[93m[INFO]\033[0m Assets disponibles:")
        for asset in release['assets']:
            if asset['name'].endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
                print(f"  - {asset['name']}")
        return

    # Descargar y extraer
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / asset_name
        if not download_with_progress(asset_url, tmp_path):
            return

        print(f"\n\033[96m[EXTRAYENDO]\033[0m Instalando en: \033[1m{install_path}\033[0m")
        try:
            # PASO 1: Extraer normalmente (sin --transform, evita el bug del espacio)
            subprocess.run(
                ["tar", "-xf", str(tmp_path), "-C", str(install_dir)],
                check=True,
                stdout=subprocess.DEVNULL
            )

            # PASO 2: Detectar la carpeta que creó tar y renombrarla
            root_folder = get_archive_root_folder(tmp_path)
            if root_folder:
                extracted_path = install_dir / root_folder
                if extracted_path.exists() and extracted_path.name != install_name:
                    # Si por alguna razón ya existe la carpeta destino, borrarla
                    if install_path.exists():
                        shutil.rmtree(install_path)
                    extracted_path.rename(install_path)
                    print(f"\033[92m[OK]\033[0m Carpeta renombrada: {root_folder} → {install_name}")
            else:
                # Fallback: buscar la carpeta más reciente que no sea la nuestra
                candidates = [
                    d for d in install_dir.iterdir()
                    if d.is_dir() and d.name != install_name
                    and repo_info['folder_prefix'].lower() in d.name.lower()
                ]
                if candidates:
                    newest = max(candidates, key=lambda p: p.stat().st_mtime)
                    if install_path.exists():
                        shutil.rmtree(install_path)
                    newest.rename(install_path)

            # Verificar resultado
            final_version = get_installed_version(install_path)
            print(f"\n\033[92m[ÉXITO]\033[0m {repo_info['name']} instalado correctamente.")
            if final_version:
                print(f"\033[92m[VERSIÓN]\033[0m {clean_version_display(final_version)}")
            print(f"\033[92m[RUTA]\033[0m    {install_path}")
            print("\033[92m[RECUERDA]\033[0m Reinicia el launcher para ver la nueva herramienta.")

        except subprocess.CalledProcessError as e:
            print(f"\033[91m[ERROR]\033[0m Falló la extracción del archivo: {e}")
            if install_path.exists():
                try:
                    shutil.rmtree(install_path)
                except Exception:
                    pass


# ============================================================
#  COMPROBAR ACTUALIZACIONES
# ============================================================

def check_updates():
    """Compara las versiones instaladas con las últimas de GitHub."""
    print("\n\033[96m[BÚSQUEDA]\033[0m Comprobando actualizaciones...\n")
    detected_launchers = detect_installed_launchers()
    if not detected_launchers:
        print("\033[91m[ERROR]\033[0m No se detectó ningún launcher compatible.\n")
        return

    for launcher_key in detected_launchers:
        launcher_info = LAUNCHERS[launcher_key]
        install_dir = launcher_info['path']
        if not install_dir.exists():
            continue

        print(f"\033[95m[{launcher_info['name']}]\033[0m")
        for key, repo_info in REPOS.items():
            install_name = repo_info['install_name']
            install_path = install_dir / install_name

            release = get_latest_release(repo_info['owner'], repo_info['repo'])
            if not release:
                continue
            latest_tag = release['tag_name']

            installed_version = get_installed_version(install_path)
            print(f"  - {repo_info['name']} ({install_name}):")
            print(f"    GitHub:    \033[94m{latest_tag}\033[0m")

            if installed_version:
                print(f"    Instalada: \033[92m{clean_version_display(installed_version)}\033[0m")
                if is_version_up_to_date(installed_version, latest_tag):
                    print(f"    Estado:    \033[92m¡Actualizado! ✓\033[0m")
                else:
                    print(f"    Estado:    \033[93mActualización disponible\033[0m")
            else:
                # También buscar carpetas viejas con nombre dinámico
                old_folders = find_previous_versions(install_dir, repo_info['folder_prefix'], install_name)
                if old_folders:
                    print(f"    Instalada: \033[93m{old_folders[0].name}\033[0m (carpeta vieja)")
                    print(f"    Estado:    \033[93mMigrar a nombre fijo recomendado\033[0m")
                else:
                    print(f"    Instalada: \033[91mNo instalado\033[0m")
        print()


# ============================================================
#  MENÚ PRINCIPAL
# ============================================================

def main():
    clear_screen()
    print_header()
    check_architecture_compatibility()
    install_aria2()

    while True:
        clear_screen()
        print_header()
        print("  1. Instalar / Actualizar Proton-GE")
        print("  2. Instalar / Actualizar Proton-CachyOS")
        print("  3. Comprobar actualizaciones")
        print("  4. Forzar reinstalación de Proton-GE")
        print("  5. Forzar reinstalación de Proton-CachyOS")
        print("  6. Salir")
        print("-" * 50)
        choice = input("  Selecciona una opción (1-6): ").strip()

        if choice in ["1", "2"]:
            install_proton(choice, force=False)
            input("\n\033[90mPresiona Enter para volver al menú...\033[0m")
        elif choice in ["4", "5"]:
            repo_key = "1" if choice == "4" else "2"
            confirm = input(f"\n\033[93m[AVISO]\033[0m Reinstalar {REPOS[repo_key]['name']} aunque esté al día. ¿Continuar? (s/n): ").strip().lower()
            if confirm == 's':
                install_proton(repo_key, force=True)
            input("\n\033[90mPresiona Enter para volver al menú...\033[0m")
        elif choice == "3":
            check_updates()
            input("\n\033[90mPresiona Enter para volver al menú...\033[0m")
        elif choice == "6":
            print("\n\033[92m¡Hasta luego!\033[0m\n")
            break
        else:
            print("\033[91mOpción no válida.\033[0m")
            input("\n\033[90mPresiona Enter para intentar de nuevo...\033[0m")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n\033[91m[INTERRUMPIDO]\033[0m Saliendo del script.")
        sys.exit(0)
