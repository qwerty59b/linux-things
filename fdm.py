#!/usr/bin/env python3
import subprocess
import sys
import re
import urllib.request
import os

REPO_URL = "https://builds.garudalinux.org/repos/chaotic-aur/x86_64/"
PACKAGE_NAME = "freedownloadmanager"

def verificar_e_instalar_aria2():
    print("🔍 Verificando si aria2 está instalado...")
    result = subprocess.run(["which", "aria2c"], capture_output=True, text=True)
    if result.returncode != 0:
        print("⚠️ aria2 no está instalado. Instalando aria2 con pacman...")
        # Se usa sudo para instalar, pedirá tu contraseña si es necesario
        subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "aria2"], check=True)
        print("✅ aria2 instalado correctamente.")
    else:
        print("✅ aria2 ya está instalado.")

def obtener_info_paquete_reciente():
    print(f"🌐 Consultando el repositorio en {REPO_URL}...")
    try:
        req = urllib.request.Request(REPO_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
        
        # Buscar archivos como freedownloadmanager-6.34.4.6974-1.2-x86_64.pkg.tar.zst
        pattern = rf'href="({PACKAGE_NAME}-[^"]+\.pkg\.tar\.zst)"'
        matches = re.findall(pattern, html)
        
        # Filtrar solo los paquetes, excluyendo las firmas (.sig)
        pkg_files = [m for m in matches if not m.endswith('.sig')]
        
        if not pkg_files:
            print("❌ No se encontró el paquete freedownloadmanager en el repositorio.")
            return None, None
        
        # El último elemento suele ser el más reciente en los índices de repositorios
        latest_pkg = pkg_files[-1]
        
        # Extraer la versión (ej: 6.34.4.6974-1.2)
        version_match = re.search(rf'{PACKAGE_NAME}-(.+)-x86_64\.pkg\.tar\.zst', latest_pkg)
        version = version_match.group(1) if version_match else "desconocida"
        
        return latest_pkg, version
            
    except Exception as e:
        print(f"❌ Error al consultar el repositorio: {e}")
        return None, None

def obtener_version_instalada():
    result = subprocess.run(["pacman", "-Q", PACKAGE_NAME], capture_output=True, text=True)
    if result.returncode == 0:
        # La salida de pacman -Q es del tipo: "freedownloadmanager 6.34.4.6974-1.2"
        parts = result.stdout.strip().split()
        if len(parts) >= 2:
            return parts[1]
    return None

def instalar_paquete():
    latest_pkg, version = obtener_info_paquete_reciente()
    if not latest_pkg:
        print("No se pudo obtener la información del paquete más reciente.")
        return
    
    pkg_url = f"{REPO_URL}{latest_pkg}"
    sig_url = f"{pkg_url}.sig"
    
    print(f"📦 Paquete más reciente encontrado: {latest_pkg}")
    print(f"📥 Descargando con aria2 (16 conexiones simultáneas)...")
    
    # Descargar el paquete principal con 16 conexiones (-x 16) y 16 divisiones (-s 16)
    result = subprocess.run(["aria2c", "-x", "16", "-s", "16", pkg_url])
    if result.returncode != 0:
        print("❌ Error durante la descarga con aria2.")
        return
    
    # Descargar la firma (silenciosamente, no es crítico si falla)
    subprocess.run(["aria2c", "-x", "4", "-s", "4", sig_url], capture_output=True)
    
    print("🔧 Instalando el paquete con pacman...")
    result = subprocess.run(["sudo", "pacman", "-U", "--noconfirm", latest_pkg])
    
    if result.returncode == 0:
        print("✅ Instalación completada exitosamente.")
    else:
        print("❌ Error durante la instalación con pacman. Asegúrate de tener las dependencias resueltas (tener Chaotic AUR en tu pacman.conf ayuda).")
    
    # Limpiar archivos descargados del directorio actual
    for file_to_remove in [latest_pkg, f"{latest_pkg}.sig"]:
        if os.path.exists(file_to_remove):
            os.remove(file_to_remove)
            print(f"🧹 Archivo temporal {file_to_remove} eliminado.")

def verificar_version():
    installed_version = obtener_version_instalada()
    latest_pkg, latest_version = obtener_info_paquete_reciente()
    
    if not latest_version:
        print("No se pudo verificar la versión más reciente en el repositorio.")
        return
        
    print(f"🌐 Versión disponible en el repositorio: {latest_version}")
    
    if installed_version:
        print(f"💻 Versión instalada en el sistema: {installed_version}")
        if installed_version == latest_version:
            print("✅ El sistema ya tiene la versión más reciente instalada.")
        else:
            print("⚠️ Hay una nueva versión disponible. Puedes usar la opción 1 para descargarla e instalarla.")
    else:
        print("ℹ️ El paquete freedownloadmanager NO está instalado en el sistema.")

def main():
    print("=" * 65)
    print("  Administrador de FreeDownloadManager (Chaotic AUR)")
    print("=" * 65)
    
    while True:
        print("\n--- Menú de Opciones ---")
        print("1. Instalar FreeDownloadManager")
        print("2. Verificar nuevas versiones")
        print("3. Salir")
        
        choice = input("Selecciona una opción (1-3): ").strip()
        
        if choice == '1':
            verificar_e_instalar_aria2()
            instalar_paquete()
        elif choice == '2':
            verificar_version()
        elif choice == '3':
            print("👋 Saliendo del script. ¡Hasta luego!")
            break
        else:
            print("⚠️ Opción no válida. Por favor, selecciona 1, 2 o 3.")

if __name__ == "__main__":
    if sys.platform != "linux":
        print("⚠️ Este script está diseñado para ejecutarse en Arch Linux.")
        sys.exit(1)
    main()