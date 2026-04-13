#!/usr/bin/env python3
"""
Wrapper interactivo para generate_formatted_crs.py
Permite introducir 1 o 2 URLs de manera interactiva
"""

import subprocess
import sys
import os

def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")

def print_info(text):
    print(f"ℹ️  {text}")

def print_success(text):
    print(f"✓ {text}")

def main():
    print_header("🚀 CR GENERATION - MODO INTERACTIVO")
    
    print_info("Este script ejecutará generate_formatted_crs.py de forma interactiva")
    print_info("Puedes introducir 1 o 2 URLs para analizar")
    
    urls = []
    
    # URL 1
    print_info("\n[URL #1] Ingresa la primera URL (o presiona ENTER para omitir)")
    print_info("Ejemplo: https://prodlabrpt.rose.rdlabs.hpecorp.net/cgi-bin/testResultsCentral?...")
    url1 = input(">>> ").strip()
    
    if url1:
        urls.append(url1)
        print_success(f"URL 1 capturada ({len(url1)} caracteres)")
    else:
        print("⚠️  URL 1 omitida")
    
    # URL 2
    print_info("\n[URL #2] Ingresa la segunda URL (o presiona ENTER para omitir)")
    url2 = input(">>> ").strip()
    
    if url2:
        urls.append(url2)
        print_success(f"URL 2 capturada ({len(url2)} caracteres)")
    else:
        print("⚠️  URL 2 omitida")
    
    if not urls:
        print("❌ No se proporcionaron URLs. Abortando.")
        return 1
    
    print_header(f"🔄 EJECUTANDO {len(urls)} ANÁLISIS")
    
    script_path = os.path.join(
        os.path.dirname(__file__),
        "tools",
        "generate_formatted_crs.py"
    )
    
    for i, url in enumerate(urls, 1):
        print(f"\n\n📌 ANÁLISIS {i}/{len(urls)}")
        print(f"{'='*80}")
        print(f"URL: {url[:100]}..." if len(url) > 100 else f"URL: {url}")
        print(f"{'='*80}\n")
        
        try:
            # Ejecutar script con la URL
            result = subprocess.run(
                [sys.executable, script_path, url],
                cwd=os.path.dirname(os.path.dirname(script_path))
            )
            
            if result.returncode == 0:
                print_success(f"Análisis {i} completado")
            else:
                print(f"⚠️  Análisis {i} con código de salida {result.returncode}")
                
        except Exception as e:
            print(f"❌ Error en análisis {i}: {e}")
    
    print_header("✨ TODOS LOS ANÁLISIS COMPLETADOS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
