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
    "x86_64": "x86_64 (64-bit)",
    "AMD64": "x86_64 (64-bit)",
    "aarch64": "ARM64 (64-bit)",
    "arm64": "ARM64 (64-bit)",
    "i386": "x86 (32-bit)",
    "i686": "x86 (32-bit)"
}
ARCH_DISPLAY = ARCH_NAMES.get(ARCH, ARCH)

# Mapeo de arquitecturas para filtrar assets
ARCH_FILTERS = {
    "x86_64": ["x86_64", "x86-64", "amd64", "AMD64"],
    "AMD64": ["x86_64", "x86-64", "amd64", "AMD64"],
    "aarch64": ["aarch64", "arm64", "ARM64"],
    "arm64": ["aarch64", "arm64", "ARM64"],
    "i386": ["i386", "i686", "x86"],
    "i686": ["i386", "i686", "x86"]
}

# Configuración de launchers y sus rutas
LAUNCHERS = {
    "steam_native": {
        "name": "Steam (Nativo)",
        "path": Path.home() / ".local/share/Steam/compatibilitytools.d",
        "flatpak_id": None
    },
    "steam_flatpak": {
        "name": "Steam (Flatpak)",
        "path": Path.home() / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d",
        "flatpak_id": "com.valvesoftware.Steam"
    },
    "lutris_flatpak": {
        "name": "Lutris (Flatpak)",
        "path": Path.home() / ".var/app/net.lutris.Lutris/data/lutris/runners/proton",
        "flatpak_id": "net.lutris.Lutris"
    },
    "heroic_flatpak": {
        "name": "Heroic Games Launcher (Flatpak)",
        "path": Path.home() / ".var/app/com.heroicgameslauncher.hgl/config/heroic/tools/proton",
        "flatpak_id": "com.heroicgameslauncher.hgl"
    },
    "faugus_flatpak": {
        "name": "Faugus Launcher (Flatpak)",
        "path": Path.home() / ".var/app/com.faugus.Launcher/data/faugus-launcher/proton",
        "flatpak_id": "com.faugus.Launcher"
    }
}

REPOS = {
    "1": {
        "name": "Proton-GE",
        "owner": "GloriousEggroll",
        "repo": "proton-ge-custom",
        "folder_prefix": "GE-Proton"
    },
    "2": {
        "name": "Proton-CachyOS",
        "owner": "CachyOS",
        "repo": "proton-cachyos",
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
    
    # Detectar Steam nativo
    steam_native_path = Path.home() / ".local/share/Steam"
    if steam_native_path.exists():
        detected.append("steam_native")
    
    # Detectar Flatpaks instalados
    if shutil.which("flatpak"):
        try:
            result = subprocess.run(
                ["flatpak", "list", "--app", "--columns=application"],
                capture_output=True,
                text=True,
                check=True
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
        "pacman": ["pacman", "-S", "--noconfirm", "aria2"],
        "apt": ["apt", "install", "-y", "aria2"],
        "dnf": ["dnf", "install", "-y", "aria2"],
        "zypper": ["zypper", "install", "-y", "aria2"],
        "apk": ["apk", "add", "aria2"],
        "xbps-install": ["xbps-install", "-y", "aria2"],
        "emerge": ["emerge", "--ask=n", "net-misc/aria2"],
        "brew": ["brew", "install", "aria2"]
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

    print(f"\033[96m[INFO]\033[0m Gestor de paquetes detectado: \033[1m{manager}\033[0m")
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


def find_previous_versions(install_dir, folder_prefix, current_version):
    """Busca versiones anteriores del mismo Proton en el directorio de instalación."""
    previous_versions = []
    
    if not install_dir.exists():
        return previous_versions
    
    for folder in install_dir.iterdir():
        if not folder.is_dir():
            continue
        
        # Verificar si la carpeta pertenece a este Proton
        if folder_prefix.lower() not in folder.name.lower():
            continue
        
        # Excluir la versión actual que se va a instalar
        if folder.name == current_version:
            continue
        
        previous_versions.append(folder)
    
    return previous_versions


def handle_previous_versions(install_dir, folder_prefix, new_version):
    """Maneja las versiones anteriores: pregunta si eliminarlas o mantenerlas."""
    previous_versions = find_previous_versions(install_dir, folder_prefix, new_version)
    
    if not previous_versions:
        return True  # No hay versiones anteriores, continuar normalmente
    
    print(f"\n\033[93m[VERSIONES ANTERIORES]\033[0m Se encontraron {len(previous_versions)} versión(es) anterior(es):\n")
    
    for i, version in enumerate(previous_versions, 1):
        print(f"  {i}. {version.name}")
    
    print(f"\n\033[96m[ACCIÓN]\033[0m ¿Qué deseas hacer con las versiones anteriores?")
    print("  1. Eliminar todas las versiones anteriores")
    print("  2. Mantener todas las versiones anteriores")
    print("  3. Seleccionar cuáles eliminar")
    
    while True:
        choice = input("\nSelecciona una opción (1-3): ").strip()
        
        if choice == "1":
            print(f"\n\033[93m[INFO]\033[0m Eliminando versiones anteriores...")
            for version in previous_versions:
                try:
                    shutil.rmtree(version)
                    print(f"  \033[92m✓\033[0m {version.name} eliminada")
                except Exception as e:
                    print(f"  \033[91m✗\033[0m Error al eliminar {version.name}: {e}")
            return True
        
        elif choice == "2":
            print(f"\n\033[93m[INFO]\033[0m Manteniendo todas las versiones anteriores.")
            return True
        
        elif choice == "3":
            print(f"\n\033[96m[SELECCIÓN]\033[0m Marca las versiones que quieres eliminar (ej: 1,3):")
            selection = input("Ingresa los números separados por comas: ").strip()
            
            try:
                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                versions_to_delete = [previous_versions[i] for i in indices if 0 <= i < len(previous_versions)]
                
                if not versions_to_delete:
                    print("\033[91m[ERROR]\033[0m No se seleccionaron versiones válidas.")
                    continue
                
                print(f"\n\033[93m[INFO]\033[0m Eliminando versiones seleccionadas...")
                for version in versions_to_delete:
                    try:
                        shutil.rmtree(version)
                        print(f"  \033[92m✓\033[0m {version.name} eliminada")
                    except Exception as e:
                        print(f"  \033[91m✗\033[0m Error al eliminar {version.name}: {e}")
                return True
            except (ValueError, IndexError):
                print("\033[91m[ERROR]\033[0m Selección inválida. Intenta de nuevo.")
                continue
        
        else:
            print("\033[91mOpción no válida.\033[0m")


def install_proton(choice_key):
    """Flujo principal para descargar e instalar una versión de Proton."""
    repo_info = REPOS[choice_key]
    print(f"\n\033[92m[INFO]\033[0m Buscando última versión de {repo_info['name']}...")

    release = get_latest_release(repo_info['owner'], repo_info['repo'])
    if not release:
        return

    tag_name = release['tag_name']
    print(f"\033[92m[ÉXITO]\033[0m Última versión encontrada: \033[1m{tag_name}\033[0m")

    # Seleccionar ubicación de instalación
    install_dir = select_install_location()
    if not install_dir:
        print("\033[91m[Cancelado]\033[0m Instalación abortada.")
        return

    ensure_dir(install_dir)

    # Manejar versiones anteriores antes de descargar
    prefix = repo_info['folder_prefix']
    if not handle_previous_versions(install_dir, prefix, tag_name):
        print("\033[91m[Cancelado]\033[0m Instalación abortada.")
        return

    # Buscar asset compatible con la arquitectura
    asset_url, asset_name = find_compatible_asset(release['assets'])
    if not asset_url:
        print("\033[91m[ERROR]\033[0m No se encontró un archivo compatible con tu arquitectura.")
        print(f"\033[93m[INFO]\033[0m Arquitectura del sistema: {ARCH_DISPLAY}")
        print("\033[93m[INFO]\033[0m Assets disponibles en la release:")
        for asset in release['assets']:
            if asset['name'].endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
                print(f"  - {asset['name']}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / asset_name
        if not download_with_progress(asset_url, tmp_path):
            return

        root_folder = get_archive_root_folder(tmp_path)
        if not root_folder:
            root_folder = tag_name

        install_path = install_dir / root_folder
        if install_path.exists():
            print(f"\n\033[93m[ATENCIÓN]\033[0m La versión '{root_folder}' ya está instalada.")
            overwrite = input("¿Deseas sobreescribir? (s/n): ").strip().lower()
            if overwrite != 's':
                print("\033[91m[Cancelado]\033[0m La instalación no se realizará.")
                return
            print(f"\033[93m[INFO]\033[0m Eliminando versión anterior...")
            shutil.rmtree(install_path)

        print(f"\n\033[96m[EXTRAYENDO]\033[0m Instalando en {install_dir}...")
        try:
            subprocess.run(
                ["tar", "-xf", str(tmp_path), "-C", str(install_dir)],
                check=True,
                stdout=subprocess.DEVNULL
            )
            print(f"\n\033[92m[ÉXITO]\033[0m {repo_info['name']} {tag_name} instalado correctamente.")
            print("\033[92m[RECUERDA]\033[0m Reinicia el launcher para ver la nueva herramienta.")
        except subprocess.CalledProcessError:
            print("\033[91m[ERROR]\033[0m Falló la extracción del archivo.")


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
            release = get_latest_release(repo_info['owner'], repo_info['repo'])
            if not release:
                continue

            latest_tag = release['tag_name']
            prefix = repo_info['folder_prefix']
            installed = False

            for folder in install_dir.iterdir():
                if not folder.is_dir():
                    continue

                if prefix.lower() not in folder.name.lower():
                    continue

                installed = True
                print(f"  - {repo_info['name']}:")
                print(f"    Instalada: \033[92m{folder.name}\033[0m")
                print(f"    GitHub:    \033[94m{latest_tag}\033[0m")

                if latest_tag in folder.name:
                    print(f"    Estado:    \033[92m¡Actualizado!\033[0m")
                else:
                    print(f"    Estado:    \033[93mActualización disponible\033[0m")
                break

            if not installed:
                print(f"  - {repo_info['name']}: \033[91mNo instalado\033[0m (Última: {latest_tag})")
        
        print()


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
        print("  4. Salir")
        print("-" * 50)
        choice = input("  Selecciona una opción (1-4): ").strip()

        if choice in ["1", "2"]:
            install_proton(choice)
            input("\n\033[90mPresiona Enter para volver al menú...\033[0m")
        elif choice == "3":
            check_updates()
            input("\n\033[90mPresiona Enter para volver al menú...\033[0m")
        elif choice == "4":
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
