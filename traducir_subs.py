#!/usr/bin/env python3
"""Traductor de subtítulos (.srt / .vtt / .ass / .ssa) con LibreTranslate. Funciona en Linux y Windows.

Requisito (una sola vez):   pipx install libretranslate
Uso:                        python traducir_subs.py      (abre un menú)

Menú: traducir una carpeta, ver / descargar / actualizar modelos de idioma,
y exportar / importar los modelos (.argosmodel) para guardarlos como respaldo
y no volver a descargarlos si reinstalas el sistema.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# Si ya tienes un servidor corriendo en otro lado, cambia esta URL (y pon API_KEY si la pide).
URL = "http://127.0.0.1:5000"
API_KEY = ""
CHUNK = 20  # textos por petición (más chico = progreso más fino)
CONFIG = Path.home() / ".traducir_subs.json"


# ----------------------------------------------------------------------------
# Arranque: usar el entorno de pipx donde está instalado libretranslate
# ----------------------------------------------------------------------------
def _usar_entorno_pipx():
    try:
        import argostranslate  # noqa: F401
        return
    except ImportError:
        pass
    home = Path.home()
    bases = [home / ".local/share/pipx/venvs", home / ".local/pipx/venvs", home / "pipx/venvs"]
    try:
        out = subprocess.run(["pipx", "environment", "--value", "PIPX_LOCAL_VENVS"],
                             capture_output=True, text=True).stdout.strip()
        if out:
            bases.insert(0, Path(out))
    except OSError:
        pass
    for base in bases:
        for rel in ("libretranslate/bin/python", "libretranslate/Scripts/python.exe"):
            py = base / rel
            if py.exists():
                sys.exit(subprocess.run([str(py), os.path.abspath(__file__)]).returncode)
    sys.exit("No encontré libretranslate. Instálalo con:  pipx install libretranslate")


_usar_entorno_pipx()

import argostranslate.package as apkg  # noqa: E402

TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]*\}")
TIME_RE = re.compile(r"-->")
NUM_RE = re.compile(r"^\d+$")
ASS_INICIO_RE = re.compile(r"^(?:\{[^}]*\})+")        # etiquetas {\an8}{\pos(..)} al inicio de la línea
ASS_TAG_RE = re.compile(r"\{[^}]*\}")
ASS_DIBUJO_RE = re.compile(r"\\p[1-9]")               # dibujos vectoriales: no se traducen
ASS_SALTO_RE = re.compile(r"\\[Nnh]")
EXTENSIONES = (".srt", ".vtt", ".ass", ".ssa")


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def preguntar(msg):
    return input(msg).strip().strip('"').strip("'")


def cfg_cargar():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cfg_guardar(clave, valor):
    datos = cfg_cargar()
    datos[clave] = valor
    try:
        CONFIG.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def preguntar_carpeta(msg, clave, debe_existir=True):
    """Pregunta una ruta; Enter reutiliza la última que usaste para esa opción."""
    ultima = cfg_cargar().get(clave, "")
    while True:
        extra = f" [Enter = {ultima}]" if ultima else ""
        r = preguntar(f"{msg}{extra}: ") or ultima
        if not r:
            continue
        ruta = Path(r).expanduser()
        if debe_existir and not ruta.is_dir():
            print("Esa carpeta no existe, intenta de nuevo.")
            continue
        cfg_guardar(clave, str(ruta))
        return ruta


def version_tupla(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v)))


# ----------------------------------------------------------------------------
# Gestión de modelos de idioma
# ----------------------------------------------------------------------------
def modelos_instalados():
    return sorted(apkg.get_installed_packages(), key=lambda p: (p.from_code, p.to_code))


def ver_modelos():
    while True:
        mods = modelos_instalados()
        if not mods:
            print("No hay modelos instalados todavía.")
            return
        print("Modelos instalados:")
        for p in mods:
            print(f"  {p.from_code} -> {p.to_code}   (versión {p.package_version})")
        print("\n 1) Eliminar modelos\n 0) Volver")
        op = preguntar("Elige una opción: ")
        if op in ("", "0"):
            return
        if op == "1":
            eliminar_modelos(mods)
        else:
            print("Opción no válida.")


def parsear_seleccion(texto, total):
    """'1,3' / '1 3' / 'todos' -> lista de índices (base 0), o None si es inválido."""
    if texto.lower() in ("t", "todos"):
        return list(range(total))
    idx = set()
    for parte in re.split(r"[,\s]+", texto):
        if not parte:
            continue
        if not parte.isdigit() or not 1 <= int(parte) <= total:
            return None
        idx.add(int(parte) - 1)
    return sorted(idx) or None


def eliminar_modelos(mods):
    print("\nEliminar modelos:")
    for i, p in enumerate(mods, 1):
        print(f"  {i}) {p.from_code} -> {p.to_code}   (versión {p.package_version})")
    print("(Si quieres conservar un respaldo, usa antes la opción 5 del menú principal.)")
    sel = preguntar("Números a eliminar (ej. 1,3), 'todos', o Enter para cancelar: ")
    if not sel:
        return
    indices = parsear_seleccion(sel, len(mods))
    if indices is None:
        print("Selección no válida.")
        return
    elegidos = [mods[i] for i in indices]
    print("Se eliminarán: " + ", ".join(f"{p.from_code}->{p.to_code}" for p in elegidos))
    if preguntar("¿Confirmas? (s/N): ").lower() not in ("s", "si", "sí", "y"):
        print("Cancelado.")
        return
    for p in elegidos:
        try:
            apkg.uninstall(p)
            print(f"Eliminado {p.from_code}->{p.to_code}")
        except Exception as e:
            print(f"No se pudo eliminar {p.from_code}->{p.to_code}: {e}")


def descargar_par(src, dst):
    print("Consultando el índice de modelos...")
    apkg.update_package_index()
    disp = apkg.get_available_packages()
    inst = {(p.from_code, p.to_code) for p in modelos_instalados()}

    def buscar(a, b):
        return next((p for p in disp if p.from_code == a and p.to_code == b), None)

    directo = buscar(src, dst)
    pasos = [(src, dst)] if directo else [(src, "en"), ("en", dst)]
    for a, b in pasos:
        if a == b or (a, b) in inst:
            continue
        p = buscar(a, b)
        if p is None:
            print(f"No existe un modelo {a}->{b}.")
            return False
        print(f"Descargando {a}->{b} ...")
        apkg.install_from_path(p.download())
    print("Listo.")
    return True


def asegurar_par(src, dst):
    inst = {(p.from_code, p.to_code) for p in modelos_instalados()}
    if (src, dst) in inst or ((src, "en") in inst and ("en", dst) in inst):
        return True
    return descargar_par(src, dst)


def descargar_modelo():
    src = preguntar("Idioma de origen (ej. en): ").lower()
    dst = preguntar("Idioma de destino (ej. es): ").lower()
    descargar_par(src, dst)


def actualizar_modelos():
    mods = modelos_instalados()
    if not mods:
        print("No hay modelos instalados.")
        return
    print("Consultando el índice de modelos...")
    apkg.update_package_index()
    disp = apkg.get_available_packages()
    hubo = False
    for p in mods:
        nuevo = next((d for d in disp if d.from_code == p.from_code and d.to_code == p.to_code), None)
        if nuevo and version_tupla(nuevo.package_version) > version_tupla(p.package_version):
            print(f"Actualizando {p.from_code}->{p.to_code}: {p.package_version} -> {nuevo.package_version}")
            apkg.install_from_path(nuevo.download())
            try:
                apkg.uninstall(p)  # quita la versión vieja
            except Exception:
                pass
            hubo = True
        else:
            print(f"{p.from_code}->{p.to_code}: ya está al día ({p.package_version})")
    if not hubo:
        print("Todo está al día.")


def exportar_modelos():
    mods = modelos_instalados()
    if not mods:
        print("No hay modelos instalados para exportar.")
        return
    destino = preguntar_carpeta("Carpeta donde guardar los modelos", "carpeta_modelos", debe_existir=False)
    destino.mkdir(parents=True, exist_ok=True)
    for p in mods:
        carpeta = Path(p.package_path)
        out = destino / f"{carpeta.name}.argosmodel"
        print(f"Exportando {p.from_code}->{p.to_code} ...")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in carpeta.rglob("*"):
                if f.is_file():
                    z.write(f, Path(carpeta.name) / f.relative_to(carpeta))
    print(f"Listo: {len(mods)} modelo(s) guardados en {destino}")


def importar_modelos():
    origen = preguntar_carpeta("Carpeta con los archivos .argosmodel", "carpeta_modelos")
    archivos = sorted(origen.glob("*.argosmodel"))
    if not archivos:
        print("No encontré archivos .argosmodel en esa carpeta.")
        return
    for f in archivos:
        print(f"Importando {f.name} ...")
        try:
            apkg.install_from_path(f)
        except Exception as e:
            print(f"  No se pudo importar: {e}")
    print("Listo.")


# ----------------------------------------------------------------------------
# Servidor LibreTranslate y traducción
# ----------------------------------------------------------------------------
def servidor_activo():
    try:
        urllib.request.urlopen(URL + "/languages", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def arrancar_servidor(src, dst):
    candidatos = [Path(sys.executable).parent / "libretranslate",
                  Path(sys.executable).parent / "libretranslate.exe"]
    exe = next((str(c) for c in candidatos if c.exists()), None) or shutil.which("libretranslate")
    if not exe:
        sys.exit("No encontré el comando libretranslate. Instálalo con:  pipx install libretranslate")
    langs = ",".join(dict.fromkeys([src, dst, "en"]))
    print(f"Arrancando LibreTranslate ({langs}) ...")
    proc = subprocess.Popen([exe, "--host", "127.0.0.1", "--port", "5000", "--load-only", langs],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    inicio = time.time()
    while time.time() - inicio < 1800:
        if proc.poll() is not None:
            sys.exit("LibreTranslate se cerró al arrancar. Pruébalo a mano: libretranslate --load-only " + langs)
        if servidor_activo():
            print("Servidor listo.")
            return proc
        time.sleep(3)
    proc.terminate()
    sys.exit("El servidor tardó demasiado en arrancar.")


def traducir(textos, src, dst):
    datos = {"q": textos, "source": src, "target": dst, "format": "text"}
    if API_KEY:
        datos["api_key"] = API_KEY
    req = urllib.request.Request(URL + "/translate", data=json.dumps(datos).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Error del servidor: {e.read().decode(errors='replace')}")
    t = res["translatedText"]
    return t if isinstance(t, list) else [t]


def leer(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def traducir_lista(pendientes, src, dst):
    """Traduce una lista de textos por lotes mostrando progreso y tiempo restante."""
    traducidos = []
    total = len(pendientes)
    if not total:
        return traducidos
    inicio = time.time()
    print(f"    0/{total} (0%)", end="", flush=True)
    for i in range(0, total, CHUNK):
        traducidos += traducir(pendientes[i:i + CHUNK], src, dst)
        hechos = len(traducidos)
        resta = (time.time() - inicio) / hechos * (total - hechos)
        print(f"\r    {hechos}/{total} ({hechos * 100 // total}%) - quedan ~{int(resta // 60)}m {int(resta % 60)}s   ",
              end="", flush=True)
    print()
    return traducidos


def traducir_ass(path, out, src, dst):
    """Traduce .ass/.ssa: solo el texto de las líneas Dialogue, conservando estilos, timing y
    las etiquetas del inicio de cada línea ({\\an8}, {\\pos(..)}, ...)."""
    lineas = leer(path).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    n_campos, idx_texto = 10, 9          # valores por defecto del formato estándar
    en_eventos = False
    items = []                            # (índice de línea, partes, etiquetas iniciales)
    pendientes = []
    for i, ln in enumerate(lineas):
        s = ln.strip()
        if s.startswith("["):
            en_eventos = s.lower() == "[events]"
            continue
        if not en_eventos:
            continue
        if s.lower().startswith("format:"):
            campos = [c.strip().lower() for c in s.split(":", 1)[1].split(",")]
            if "text" in campos:
                n_campos, idx_texto = len(campos), campos.index("text")
            continue
        if not s.startswith("Dialogue:"):
            continue
        partes = ln.split(":", 1)[1].split(",", n_campos - 1)
        if len(partes) < n_campos:
            continue
        texto = partes[idx_texto]
        if ASS_DIBUJO_RE.search(texto):
            continue
        m = ASS_INICIO_RE.match(texto)
        inicio = m.group(0) if m else ""
        limpio = ASS_TAG_RE.sub("", texto[len(inicio):])
        limpio = " ".join(ASS_SALTO_RE.sub(" ", limpio).split())
        if not limpio:
            continue
        items.append((i, partes, inicio))
        pendientes.append(limpio)

    traducidos = traducir_lista(pendientes, src, dst)
    for (i, partes, inicio), t in zip(items, traducidos):
        partes[idx_texto] = inicio + t
        lineas[i] = "Dialogue:" + ",".join(partes)
    out.write_text("\n".join(lineas), encoding="utf-8")


def traducir_archivo(path, out, src, dst):
    if path.suffix.lower() in (".ass", ".ssa"):
        return traducir_ass(path, out, src, dst)
    texto = leer(path).replace("\r\n", "\n").replace("\r", "\n")
    bloques = []  # (encabezado, texto_a_traducir | None, bloque_original)
    for bloque in texto.split("\n\n"):
        head, body = [], []
        for ln in bloque.split("\n"):
            if not body and (not ln.strip() or NUM_RE.match(ln.strip()) or TIME_RE.search(ln)
                             or ln.startswith(("WEBVTT", "NOTE", "STYLE"))):
                head.append(ln)
            else:
                body.append(ln)
        if not body or (head and head[0].startswith(("WEBVTT", "NOTE", "STYLE"))):
            bloques.append((None, None, bloque))
            continue
        joined = " ".join(TAG_RE.sub("", l).strip() for l in body).strip()
        bloques.append((head, joined, bloque))

    pendientes = [b[1] for b in bloques if b[1]]
    traducidos = traducir_lista(pendientes, src, dst)

    it = iter(traducidos)
    salida = []
    for head, joined, original in bloques:
        if head is None:
            salida.append(original)
        else:
            salida.append("\n".join(head + [next(it) if joined else ""]))
    out.write_text("\n\n".join(salida), encoding="utf-8")


def traducir_carpeta():
    print("Códigos comunes: en, es, fr, de, it, pt, ru, ja, zh, ar, ko")
    root = preguntar_carpeta("Ruta de la carpeta con los subtítulos", "carpeta_subs")
    src = preguntar("Idioma de origen (ej. en): ").lower()
    dst = preguntar("Idioma de destino (ej. es): ").lower()
    recursivo = preguntar("¿Incluir subcarpetas? (s/N): ").lower() in ("s", "si", "sí", "y")

    patron = "**/*" if recursivo else "*"
    archivos = [p for p in root.glob(patron)
                if p.suffix.lower() in EXTENSIONES and not p.stem.endswith(f".{dst}")]
    if not archivos:
        print("No encontré subtítulos .srt/.vtt/.ass/.ssa.")
        return

    if not asegurar_par(src, dst):
        return
    proc = None
    if not servidor_activo():
        proc = arrancar_servidor(src, dst)
    try:
        for i, f in enumerate(sorted(archivos), 1):
            out = f.with_name(f"{f.stem}.{dst}{f.suffix}")
            if out.exists():
                print(f"[{i}/{len(archivos)}] ya existe: {out.name}")
                continue
            print(f"[{i}/{len(archivos)}] {f.name}")
            traducir_archivo(f, out, src, dst)
        print("Listo.")
    finally:
        if proc:
            proc.terminate()


# ----------------------------------------------------------------------------
# Menú
# ----------------------------------------------------------------------------
MENU = """
=== Traductor de subtítulos ===
 1) Traducir subtítulos de una carpeta
 2) Ver / eliminar modelos de idioma instalados
 3) Descargar un modelo de idioma nuevo
 4) Actualizar los modelos instalados
 5) Exportar modelos a una carpeta (respaldo)
 6) Importar modelos desde una carpeta
 0) Salir
"""
ACCIONES = {"1": traducir_carpeta, "2": ver_modelos, "3": descargar_modelo,
            "4": actualizar_modelos, "5": exportar_modelos, "6": importar_modelos}


def main():
    while True:
        print(MENU)
        op = preguntar("Elige una opción: ")
        if op == "0":
            break
        accion = ACCIONES.get(op)
        if not accion:
            print("Opción no válida.")
            continue
        try:
            accion()
        except KeyboardInterrupt:
            print("\nCancelado.")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
