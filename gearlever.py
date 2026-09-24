#!/usr/bin/env python3
import urllib.request
import re
import subprocess
import sys
import os
import tempfile

REPO_URL = "https://builds.garudalinux.org/repos/chaotic-aur/x86_64/"
MAIN_PKG = "gearlever"

def get_repo_index():
    """Obtiene el índice HTML del repositorio de Chaotic-AUR."""
    print("🔍 Obteniendo índice del repositorio...")
    try:
        req = urllib.request.Request(REPO_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"❌ Error al conectar con el repositorio: {e}")
        sys.exit(1)

def find_package_file(html_index, pkg_name):
    """Busca el archivo .pkg.tar.zst más reciente para un nombre de paquete dado."""
    # Busca patrones como: pkg-1.0-1-x86_64.pkg.tar.zst
    pattern = rf"({re.escape(pkg_name)}-\d+.*?\.pkg\.tar\.zst)"
    matches = re.findall(pattern, html_index)
    if matches:
        # Devolver el último match, que suele ser el más reciente en listados de directorio
        return matches[-1]
    return None

def download_file(filename, dest_dir):
    """Descarga un archivo desde el repositorio mostrando progreso."""
    url = f"{REPO_URL}{filename}"
    dest_path = os.path.join(dest_dir, filename)
    print(f"⬇️ Descargando {filename}...")
    try:
        def reporthook(block_num, block_size, total_size):
            if total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, int(downloaded * 100 / total_size))
                print(f"\r   Progreso: {percent}% ({downloaded // 1024} KB / {total_size // 1024} KB)", end="")
            else:
                print(f"\r   Descargando... ({block_num * block_size // 1024} KB)", end="")
        
        urllib.request.urlretrieve(url, dest_path, reporthook)
        print()  # Salto de línea al finalizar
        return dest_path
    except Exception as e:
        print(f"\n❌ Error al descargar {filename}: {e}")
        return None

def install_package(filepath):
    """Instala un paquete local con pacman. Devuelve (éxito, mensaje_de_error)."""
    print(f"🔧 Instalando {os.path.basename(filepath)}...")
    result = subprocess.run(
        ["sudo", "pacman", "-U", "--noconfirm", filepath],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stderr

def get_dependencies(pkg_name):
    """Obtiene la lista de dependencias de un paquete instalado (soporta salida en español/inglés)."""
    result = subprocess.run(["pacman", "-Qi", pkg_name], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    
    deps = []
    lines = result.stdout.split('\n')
    in_depends = False
    for line in lines:
        if line.startswith("Depende de") or line.startswith("Depends On"):
            in_depends = True
            parts = line.split(":", 1)
            if len(parts) > 1:
                deps.extend(re.findall(r"([a-zA-Z0-9_\-]+)", parts[1]))
        elif in_depends:
            if line.startswith(" ") or line.startswith("\t"):
                deps.extend(re.findall(r"([a-zA-Z0-9_\-]+)", line))
            else:
                # Llegó a otro campo (ej: "Depende opcionalmente de")
                break
    return list(set(deps))

def check_updates():
    """Comprueba actualizaciones de Gearlever y sus dependencias en Chaotic-AUR."""
    print("🔍 Comprobando actualizaciones de Gearlever y sus dependencias en Chaotic-AUR...")
    html_index = get_repo_index()
    
    # 1. Comprobar Gearlever
    latest_file = find_package_file(html_index, MAIN_PKG)
    if not latest_file:
        print("❌ No se encontró Gearlever en el repositorio.")
        return
    
    version_match = re.search(rf"{re.escape(MAIN_PKG)}-(.+)-(x86_64|any)\.pkg\.tar\.zst", latest_file)
    latest_version = version_match.group(1) if version_match else "desconocida"

    result = subprocess.run(["pacman", "-Q", MAIN_PKG], capture_output=True, text=True)
    if result.returncode == 0:
        installed_version = result.stdout.split()[1]
        print(f"\n📦 {MAIN_PKG}:")
        print(f"   Instalada: {installed_version}")
        print(f"   Repositorio: {latest_version}")
        if installed_version == latest_version:
            print("   ✅ Actualizado.")
        else:
            print("   🔄 ¡Actualización disponible!")
    else:
        print(f"\n⚠️ {MAIN_PKG} no está instalado. Versión en repositorio: {latest_version}")

    # 2. Comprobar dependencias
    print("\n🔍 Comprobando dependencias de Gearlever en Chaotic-AUR...")
    deps = get_dependencies(MAIN_PKG)
    if not deps:
        print("   ℹ️ No se pudieron obtener dependencias o Gearlever no está instalado.")
        return

    # Filtrar dependencias base que casi nunca están en Chaotic-AUR para ahorrar tiempo
    skip_deps = {'glibc', 'gcc', 'python', 'gtk4', 'glib2', 'zlib', 'pango', 'dconf', 
                 'binutils', '7zip', 'fuse2', 'gdk-pixbuf2', 'hicolor-icon-theme', 
                 'libadwaita', 'squashfs-tools', 'python-gobject', 'python-requests', 'Nada'}
    
    updated_count = 0
    checked_count = 0
    for dep in deps:
        if dep in skip_deps:
            continue
        
        dep_file = find_package_file(html_index, dep)
        if dep_file:
            checked_count += 1
            res = subprocess.run(["pacman", "-Q", dep], capture_output=True, text=True)
            if res.returncode == 0:
                inst_ver = res.stdout.split()[1]
                dep_ver_match = re.search(rf"{re.escape(dep)}-(.+)-(x86_64|any)\.pkg\.tar\.zst", dep_file)
                if dep_ver_match:
                    repo_ver = dep_ver_match.group(1)
                    if inst_ver != repo_ver:
                        print(f"   🔄 {dep}: instalado {inst_ver} -> repo {repo_ver}")
                        updated_count += 1
                    else:
                        print(f"   ✅ {dep}: actualizado ({inst_ver})")
    
    if checked_count == 0:
        print("   ℹ️ No se encontraron dependencias de este paquete en el índice de Chaotic-AUR.")
    elif updated_count == 0:
        print("   ✅ Todas las dependencias comprobadas de Chaotic-AUR están actualizadas.")
        
    print("\n💡 Recuerda: para una actualización completa y segura del sistema, usa: sudo pacman -Syu")

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 gestor_gearlever.py [--install | --check]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "--check":
        check_updates()
        return

    if command == "--install":
        print("⚠️ NOTA: Asegúrate de tener el keyring de Chaotic-AUR instalado.")
        print("   Si no lo tienes, ejecuta primero: sudo pacman -S chaotic-keyring\n")
        
        html_index = get_repo_index()
        latest_file = find_package_file(html_index, MAIN_PKG)
        
        if not latest_file:
            print(f"❌ No se encontró el paquete principal '{MAIN_PKG}' en el repositorio.")
            sys.exit(1)

        with tempfile.TemporaryDirectory() as temp_dir:
            main_pkg_path = download_file(latest_file, temp_dir)
            if not main_pkg_path:
                sys.exit(1)

            max_retries = 15  # Límite para evitar bucles infinitos
            installed_successfully = False

            for attempt in range(max_retries):
                print(f"\n--- Intento de instalación {attempt + 1}/{max_retries} ---")
                success, stderr = install_package(main_pkg_path)
                
                if success:
                    installed_successfully = True
                    break
                
                # Analizar si el error es por una dependencia faltante (Soporte Español e Inglés)
                missing_dep_match = re.search(r"no se pudo resolver «([^»]+)»", stderr)
                if not missing_dep_match:
                    missing_dep_match = re.search(r"missing dependency: ['\"]?([^'\"\s]+)['\"]?", stderr)
                
                if not missing_dep_match:
                    print("❌ Error de instalación no relacionado con dependencias faltantes:")
                    print(stderr)
                    break
                
                missing_dep = missing_dep_match.group(1)
                print(f"⚠️ Pacman reporta que falta la dependencia: '{missing_dep}'")
                
                # Buscar esa dependencia específica en el repositorio de Chaotic-AUR
                dep_file = find_package_file(html_index, missing_dep)
                if not dep_file:
                    print(f"❌ No se encontró la dependencia '{missing_dep}' en el repositorio de Chaotic-AUR.")
                    print(f"   Es muy probable que sea una dependencia de los repositorios oficiales de Arch Linux.")
                    print(f"   Solución manual: Ejecuta 'sudo pacman -S {missing_dep}' y vuelve a intentar.")
                    break
                
                print(f"📦 Resolviendo dependencia desde Chaotic-AUR: {dep_file}")
                dep_path = download_file(dep_file, temp_dir)
                if not dep_path:
                    sys.exit(1)
                    
                # Instalar la dependencia encontrada
                dep_success, dep_stderr = install_package(dep_path)
                if not dep_success:
                    print(f"❌ Error al instalar la dependencia '{missing_dep}':")
                    print(dep_stderr)
                    break

            if installed_successfully:
                print("\n✅ ¡Gearlever y sus dependencias de Chaotic-AUR se instalaron exitosamente!")
            else:
                print("\n❌ No se pudo completar la instalación de Gearlever.")
                sys.exit(1)
    else:
        print("Opción no válida. Usa --install o --check")

if __name__ == "__main__":
    main()