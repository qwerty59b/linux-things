import os
import subprocess
import sys
import platform

system_info = platform.system()

if system_info == 'Windows':
    mkvmerge = "C:\\Program Files\\MKVToolNix\\mkvmerge.exe"
else:
    mkvmerge = "/usr/bin/mkvmerge"

# Extensiones soportadas
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts", ".flv", ".wmv"}
SUBTITLE_EXTS = {".ass", ".srt", ".ssa", ".vtt", ".sub", ".sup"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma", ".ac3", ".eac3", ".dts", ".mka", ".truehd"}

# Configuración de idioma
SUBTITLE_LANGUAGE = "spa"
SUBTITLE_TRACK_NAME = "Spanish"
AUDIO_LANGUAGE = "spa"
AUDIO_TRACK_NAME = "Spanish"


def create_output_directory(directory):
    output_dir = os.path.join(directory, "Output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def find_companion_files(directory, base_name, extensions):
    """Devuelve lista de archivos con la extensión dada que coincidan con el nombre base."""
    result = []
    for ext in extensions:
        path = os.path.join(directory, base_name + ext)
        if os.path.isfile(path):
            result.append((path, ext))
    # Si hay varios, priorizar .ass > .srt > .ssa para subtítulos... pero mejor incluir todos
    return result


def build_mkvmerge_command(output_file, input_file, subtitle_files, audio_files):
    cmd = [mkvmerge, "-o", output_file, input_file]
    
    for sub_path, _ in subtitle_files:
        cmd += ["--language", f"0:{SUBTITLE_LANGUAGE}", "--track-name", f"0:{SUBTITLE_TRACK_NAME}", sub_path]
    
    for aud_path, _ in audio_files:
        cmd += ["--language", f"0:{AUDIO_LANGUAGE}", "--track-name", f"0:{AUDIO_TRACK_NAME}", aud_path]
    
    return cmd


def process_files(directory, output_dir):
    files = [f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in VIDEO_EXTS]

    if not files:
        print("No se encontraron archivos de video.")
        return

    for file in files:
        input_file = os.path.join(directory, file)
        base_name = os.path.splitext(file)[0]
        output_file = os.path.join(output_dir, base_name + ".mkv")
        
        subtitle_files = find_companion_files(directory, base_name, SUBTITLE_EXTS)
        audio_files = find_companion_files(directory, base_name, AUDIO_EXTS)
        
        if not subtitle_files and not audio_files:
            print(f"[SKIP] {file} - no tiene subtítulos ni pistas de audio asociadas")
            continue
        
        print(f"\n[PROCESANDO] {file}")
        if subtitle_files:
            print(f"  Subtítulos: {', '.join(os.path.basename(p) for p,_ in subtitle_files)}")
        if audio_files:
            print(f"  Audio: {', '.join(os.path.basename(p) for p,_ in audio_files)}")
        
        cmd = build_mkvmerge_command(output_file, input_file, subtitle_files, audio_files)
        print(f"  Ejecutando: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  [OK] -> {output_file}")
            elif result.returncode == 1:
                # mkvmerge devuelve 1 cuando hay warnings pero el muxing se completó
                print(f"  [OK con warnings] -> {output_file}")
                if result.stderr.strip():
                    print(f"    {result.stderr.strip()}")
            else:
                print(f"  [ERROR] mkvmerge falló (código {result.returncode})")
                if result.stderr.strip():
                    print(f"    {result.stderr.strip()}")
        except FileNotFoundError:
            print(f"  [ERROR] No se encontró mkvmerge en: {mkvmerge}")
            return
        except Exception as e:
            print(f"  [ERROR] {e}")


if __name__ == "__main__":
    input_directory = input("Introduzca el path: ").strip().strip('"').strip("'")
    
    if not os.path.isdir(input_directory):
        print(f"Error: '{input_directory}' no es un directorio válido.")
        sys.exit(1)
    
    output_dir = create_output_directory(input_directory)
    process_files(input_directory, output_dir)

    print("\n============================ :)")
    input("Hecho. Presiona Enter para salir.")
