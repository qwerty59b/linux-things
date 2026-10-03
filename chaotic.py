#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import subprocess
import urllib.request
from pathlib import Path

# --- Configuración ---
REPO_URL = "https://builds.garudalinux.org/repos/chaotic-aur/x86_64/"
CONFIG_FILE = Path.home() / ".chaotic_script_packages.conf"

# Entorno limpio para subprocess para evitar "Argument list too long"
CLEAN_ENV = {
    "PATH": os.environ.get("PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"),
    "HOME": os.environ.get("HOME", "/root"),
    "USER": os.environ.get("USER", "root"),
    "LANG": os.environ.get("LANG", "C.UTF-8")
}

def check_root():
    if os.geteuid() != 0:
        print("Error: Este script necesita privilegios de root (sudo) para instalar paquetes.")
        print("Uso: sudo python3 chaotic.py")
        sys.exit(1)

def ensure_aria2():
    if not subprocess.run(["which", "aria2c"], capture_output=True, env=CLEAN_ENV).returncode == 0:
        print("aria2c no esta instalado. Instalando automaticamente...")
        subprocess.run(["pacman", "-S", "--noconfirm", "aria2"], check=True, env=CLEAN_ENV)
        print("aria2c instalado correctamente.")

def get_repo_index():
    try:
        req = urllib.request.Request(REPO_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"No se pudo conectar al repositorio: {e}")
        sys.exit(1)

def find_package_in_repo(pkg_name, html_index):
    escaped_name = re.escape(pkg_name)
    pattern = re.compile(rf'href="({escaped_name}-\d+[^"]*\.pkg\.tar\.(?:zst|xz))"')
    matches = pattern.findall(html_index)
    
    if not matches:
        return None
    
    valid_matches = [m for m in matches if len(m) < 200]
    if not valid_matches:
        return None
    
    return valid_matches[-1]

def download_package(filename):
    url = f"{REPO_URL}{filename}"
    print(f"Descargando: {filename}")
    cmd = ["aria2c", "-x", "16", "-s", "16", "--continue=true", url]
    result = subprocess.run(cmd, env=CLEAN_ENV)
    if result.returncode != 0:
        print(f"Fallo la descarga de {filename}")
        return False
    return True

def get_local_version(pkg_name):
    result = subprocess.run(["pacman", "-Q", pkg_name], capture_output=True, text=True, env=CLEAN_ENV)
    if result.returncode == 0:
        return result.stdout.strip().split()[1]
    return None

def save_to_config(pkg_name):
    pkgs = load_from_config()
    if pkg_name not in pkgs:
        pkgs.append(pkg_name)
        with open(CONFIG_FILE, "w") as f:
            f.write("\n".join(pkgs) + "\n")

def remove_from_config(pkg_name):
    pkgs = load_from_config()
    if pkg_name in pkgs:
        pkgs.remove(pkg_name)
        with open(CONFIG_FILE, "w") as f:
            if pkgs:
                f.write("\n".join(pkgs) + "\n")
            else:
                f.write("")

def load_from_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def install_packages(pkg_names):
    html_index = get_repo_index()
    to_install = list(pkg_names)
    installed_successfully = []
    retry_count = {}  # Contador de reintentos por paquete

    while to_install:
        pkg = to_install.pop(0)
        
        # Limitar reintentos a 3 para evitar bucles infinitos
        retry_count[pkg] = retry_count.get(pkg, 0) + 1
        if retry_count[pkg] > 3:
            print(f"[!] Se alcanzó el límite de reintentos para {pkg}. Saltando...")
            continue
        
        print(f"\n--- Procesando: {pkg} ---")
        
        filename = find_package_in_repo(pkg, html_index)
        if not filename:
            print(f"No se encontro '{pkg}' en el repositorio Chaotic-AUR.")
            print("Intentando instalar desde los repositorios oficiales de Arch (fallback)...")
            res = subprocess.run(["pacman", "-S", "--noconfirm", pkg], env=CLEAN_ENV)
            if res.returncode == 0:
                save_to_config(pkg)
                installed_successfully.append(pkg)
            continue

        if not download_package(filename):
            continue

        cmd = ["pacman", "-U", "--noconfirm", filename]
        result = subprocess.run(cmd, capture_output=True, text=True, env=CLEAN_ENV)
        
        if result.returncode == 0:
            print(f"[OK] {pkg} instalado correctamente.")
            save_to_config(pkg)
            installed_successfully.append(pkg)
            if Path(filename).exists():
                Path(filename).unlink()
        else:
            missing_deps = []
            missing_deps += re.findall(r'no se pudo resolver «([^»]+)»', result.stderr)
            missing_deps += re.findall(r"breaks dependency '([^']+)'", result.stderr)
            missing_deps += re.findall(r"could not satisfy dependency '([^']+)'", result.stderr)
            missing_deps += re.findall(r"missing dependency: '([^']+)'", result.stderr)
            
            clean_deps = [re.split(r'[<>=]+', dep)[0] for dep in missing_deps]
            clean_deps = list(set(clean_deps))

            if clean_deps:
                print(f"Dependencias faltantes detectadas para {pkg}: {', '.join(clean_deps)}")
                print("Buscando e instalando dependencias automaticamente...")
                
                # Primero agregar las dependencias
                for dep in clean_deps:
                    if dep not in to_install and dep not in installed_successfully:
                        to_install.append(dep)
                
                # Luego agregar el paquete original al final para reintentar
                to_install.append(pkg)
                print(f"Reintentando {pkg} después de instalar dependencias...")
            else:
                print(f"Error instalando {pkg}. Revisa la salida de pacman:")
                print(result.stderr)

def uninstall_packages(pkg_names):
    installed_pkgs = load_from_config()
    
    if not installed_pkgs:
        print("No hay paquetes registrados en el archivo de configuracion.")
        return
    
    print("\n--- Desinstalando paquetes ---")
    print(f"Paquetes instalados por este script: {', '.join(installed_pkgs)}\n")
    
    to_uninstall = []
    not_in_config = []
    
    for pkg in pkg_names:
        if pkg in installed_pkgs:
            to_uninstall.append(pkg)
        else:
            not_in_config.append(pkg)
    
    if not_in_config:
        print(f"[!] Los siguientes paquetes no fueron instalados por este script:")
        for pkg in not_in_config:
            print(f"   - {pkg}")
        print("   No se desinstalaran.\n")
    
    if not to_uninstall:
        print("No hay paquetes validos para desinstalar.")
        return
    
    print(f"Se desinstalaran los siguientes paquetes junto con sus dependencias:")
    for pkg in to_uninstall:
        print(f"   - {pkg}")
    
    print("\n¿Continuar con la desinstalacion? (s/n): ", end="")
    choice = input().strip().lower()
    
    if choice not in ['s', 'si', 'yes', 'y']:
        print("Desinstalacion cancelada.")
        return
    
    for pkg in to_uninstall:
        print(f"\n--- Desinstalando: {pkg} ---")
        cmd = ["pacman", "-Rns", "--noconfirm", pkg]
        result = subprocess.run(cmd, capture_output=True, text=True, env=CLEAN_ENV)
        
        if result.returncode == 0:
            print(f"[OK] {pkg} desinstalado correctamente.")
            remove_from_config(pkg)
        else:
            print(f"Error desinstalando {pkg}:")
            print(result.stderr)
            print(f"{pkg} permanece en la lista de configuracion.")

def check_updates():
    installed_pkgs = load_from_config()
    if not installed_pkgs:
        print(f"No hay paquetes registrados en {CONFIG_FILE}")
        return

    print("\n--- Verificando actualizaciones ---")
    html_index = get_repo_index()
    updates_available = []

    for pkg in installed_pkgs:
        local_ver = get_local_version(pkg)
        if not local_ver:
            print(f"{pkg}: No esta instalado localmente.")
            continue

        filename = find_package_in_repo(pkg, html_index)
        if not filename:
            continue

        remote_file = filename.replace(f"{pkg}-", "").replace("-x86_64.pkg.tar.zst", "").replace("-x86_64.pkg.tar.xz", "")
        remote_ver = remote_file.rsplit('-', 1)[0]

        cmp_result = subprocess.run(["vercmp", local_ver, remote_ver], capture_output=True, text=True, env=CLEAN_ENV)
        
        try:
            cmp_val = int(cmp_result.stdout.strip())
            if cmp_val < 0:
                updates_available.append({
                    'name': pkg,
                    'local': local_ver,
                    'remote': remote_ver
                })
        except ValueError:
            print(f"Error comparando versiones de {pkg}")

    if updates_available:
        print(f"\n[!] Se encontraron {len(updates_available)} actualizacion(es) disponible(s):\n")
        print("-" * 60)
        for i, update in enumerate(updates_available, 1):
            print(f"{i}. {update['name']}")
            print(f"   Local: {update['local']} -> Remoto: {update['remote']}")
        print("-" * 60)
        
        print("\n¿Deseas instalar todas las actualizaciones? (s/n): ", end="")
        choice = input().strip().lower()
        
        if choice in ['s', 'si', 'yes', 'y']:
            pkg_names = [u['name'] for u in updates_available]
            install_packages(pkg_names)
        else:
            print("Actualizaciones canceladas.")
    else:
        print("\n[OK] Todos los paquetes gestionados por este script estan actualizados!")

def main():
    check_root()
    ensure_aria2()

    while True:
        print("\n" + "="*50)
        print("  Gestor de Paquetes Chaotic-AUR (via aria2)")
        print("="*50)
        print("  1. Instalar paquetes (ej: pkg1 pkg2)")
        print("  2. Verificar actualizaciones")
        print("  3. Desinstalar paquetes (ej: pkg1 pkg2)")
        print("  4. Salir")
        print("="*50)
        
        choice = input("Selecciona una opcion [1-4]: ").strip()
        
        if choice == '1':
            pkgs_input = input("Ingresa los nombres de los paquetes (separados por espacio): ").strip()
            if not pkgs_input:
                continue
            pkg_list = [p.strip() for p in pkgs_input.split() if p.strip()]
            install_packages(pkg_list)
        elif choice == '2':
            check_updates()
        elif choice == '3':
            pkgs_input = input("Ingresa los nombres de los paquetes a desinstalar (separados por espacio): ").strip()
            if not pkgs_input:
                continue
            pkg_list = [p.strip() for p in pkgs_input.split() if p.strip()]
            uninstall_packages(pkg_list)
        elif choice == '4':
            print("Saliendo del script. Hasta luego!")
            sys.exit(0)
        else:
            print("Opcion no valida. Intenta de nuevo.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario. Saliendo...")
        sys.exit(0)