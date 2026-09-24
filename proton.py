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

# Rutas de Steam según el SO
if SYSTEM == "Linux":
    STEAM_DIR = Path.home() / ".local/share/Steam/compatibilitytools.d"
elif SYSTEM == "Darwin":  # macOS
    STEAM_DIR = Path.home() / "Library/Application Support/Steam/compatibilitytools.d"
elif SYSTEM == "Windows":
    STEAM_DIR = Path("C:/Program Files (x86)/Steam/compatibilitytools.d")
else:
    print(f"\033[91m[ERROR]\033[0m Sistema operativo no soportado: {SYSTEM}")
    sys.exit(1)

REPOS = {
    "1": {"name": "Proton-GE", "owner": "GloriousEggroll", "repo": "proton-ge-custom"},
    "2": {"name": "Proton-CachyOS", "owner": "CachyOS", "repo": "proton-cachyos"}
}

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("\033[95m" + "="*50)
    print("  INSTALADOR DE PROTON (GE / CACHYOS)")
    print(f"  Sistema: \033[96m{SYSTEM}\033[95m | Arquitectura: \033[96m{ARCH_DISPLAY}\033[95m")
    print("="*50 + "\033[0m")

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

def ensure_steam_dir():
    """Crea el directorio de herramientas de compatibilidad si no existe."""
    if not STEAM_DIR.exists():
        print(f"\033[93m[INFO]\033[0m Creando directorio: {STEAM_DIR}")
        STEAM_DIR.mkdir(parents=True, exist_ok=True)

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
        "brew": ["brew", "install", "aria2"]  # macOS
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
    
    # Ejecutar con sudo en Linux (excepto brew en macOS que no lo necesita)
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
    
    # Primero buscar assets específicos para la arquitectura
    for asset in assets:
        asset_name = asset['name'].lower()
        if asset_name.endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
            # Verificar si el nombre del asset contiene palabras clave de la arquitectura
            for keyword in arch_keywords:
                if keyword.lower() in asset_name:
                    print(f"\033[92m[OK]\033[0m Asset compatible encontrado: {asset['name']}")
                    return asset['browser_download_url'], asset['name']
    
    # Si no encuentra específico, buscar assets genéricos (sin arquitectura en el nombre)
    for asset in assets:
        asset_name = asset['name'].lower()
        if asset_name.endswith(('.tar.gz', '.tar.xz', '.tar.zst')):
            # Verificar que NO contenga otras arquitecturas
            other_archs = ["aarch64", "arm64", "i386", "i686"]
            if ARCH in ["x86_64", "AMD64"]:
                # Para x86_64, aceptar si no tiene otras arquitecturas
                if not any(other in asset_name for other in other_archs):
                    print(f"\033[93m[INFO]\033[0m Usando asset genérico: {asset['name']}")
                    return asset['browser_download_url'], asset['name']
    
    return None, None

def install_proton(choice_key):
    """Flujo principal para descargar e instalar una versión de Proton."""
    repo_info = REPOS[choice_key]
    print(f"\n\033[92m[INFO]\033[0m Buscando última versión de {repo_info['name']}...")
    
    release = get_latest_release(repo_info['owner'], repo_info['repo'])
    if not release:
        return

    tag_name = release['tag_name']
    print(f"\033[92m[ÉXITO]\033[0m Última versión encontrada: \033[1m{tag_name}\033[0m")

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

        install_path = STEAM_DIR / root_folder

        if install_path.exists():
            print(f"\n\033[93m[ATENCIÓN]\033[0m La versión '{root_folder}' ya está instalada.")
            overwrite = input("¿Deseas sobreescribir? (s/n): ").strip().lower()
            if overwrite != 's':
                print("\033[91m[Cancelado]\033[0m La instalación no se realizará.")
                return
            print(f"\033[93m[INFO]\033[0m Eliminando versión anterior...")
            shutil.rmtree(install_path)

        print(f"\n\033[96m[EXTRAYENDO]\033[0m Instalando en {STEAM_DIR}...")
        try:
            subprocess.run(
                ["tar", "-xf", str(tmp_path), "-C", str(STEAM_DIR)], 
                check=True, 
                stdout=subprocess.DEVNULL
            )
            print(f"\n\033[92m[ÉXITO]\033[0m {repo_info['name']} {tag_name} instalado correctamente.")
            print("\033[92m[RECUERDA]\033[0m Reinicia Steam para ver la nueva herramienta.")
        except subprocess.CalledProcessError:
            print("\033[91m[ERROR]\033[0m Falló la extracción del archivo.")

def check_updates():
    """Compara las versiones instaladas con las últimas de GitHub."""
    print("\n\033[96m[BÚSQUEDA]\033[0m Comprobando actualizaciones...\n")
    ensure_steam_dir()
    
    for key, repo_info in REPOS.items():
        release = get_latest_release(repo_info['owner'], repo_info['repo'])
        if not release:
            continue
            
        latest_tag = release['tag_name']
        
        installed = False
        for folder in STEAM_DIR.iterdir():
            if folder.is_dir() and (latest_tag in folder.name or repo_info['repo'].split('-')[0] in folder.name):
                installed = True
                print(f" - {repo_info['name']}:")
                print(f"   Instalada: \033[92m{folder.name}\033[0m")
                print(f"   GitHub:    \033[94m{latest_tag}\033[0m")
                if folder.name == latest_tag:
                    print(f"   Estado:    \033[92m¡Actualizado!\033[0m\n")
                else:
                    print(f"   Estado:    \033[93mActualización disponible\033[0m\n")
                break
        
        if not installed:
            print(f" - {repo_info['name']}: \033[91mNo instalado\033[0m (Última: {latest_tag})\n")

def main():
    clear_screen()
    print_header()
    
    # Verificar compatibilidad de arquitectura
    check_architecture_compatibility()
    
    ensure_steam_dir()
    
    # Verificar e instalar aria2 al inicio
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