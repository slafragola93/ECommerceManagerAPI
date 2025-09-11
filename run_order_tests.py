#!/usr/bin/env python3
"""
Script per eseguire i test degli endpoint Order
"""

import subprocess
import sys
import os

def run_tests():
    """Esegue i test per gli endpoint Order"""
    
    print("🧪 Avvio test per gli endpoint Order...")
    print("=" * 50)
    
    # Comando per eseguire i test
    test_commands = [
        # Test base
        ["python", "-m", "pytest", "test/routers/test_order.py", "-v", "--tb=short"],
        
        # Test avanzati
        ["python", "-m", "pytest", "test/routers/test_order_advanced.py", "-v", "--tb=short"],
        
        # Test con coverage (se pytest-cov è installato)
        ["python", "-m", "pytest", "test/routers/test_order*.py", "--cov=src/routers/order", "--cov-report=term-missing", "-v"]
    ]
    
    results = []
    
    for i, cmd in enumerate(test_commands, 1):
        print(f"\n📋 Esecuzione test {i}/{len(test_commands)}")
        print(f"Comando: {' '.join(cmd)}")
        print("-" * 30)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode == 0:
                print("✅ Test completati con successo!")
                results.append(True)
            else:
                print("❌ Test falliti!")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                results.append(False)
                
        except FileNotFoundError:
            print("❌ pytest non trovato. Installa pytest: pip install pytest")
            results.append(False)
        except Exception as e:
            print(f"❌ Errore durante l'esecuzione: {e}")
            results.append(False)
    
    # Riepilogo
    print("\n" + "=" * 50)
    print("📊 RIEPILOGO TEST")
    print("=" * 50)
    
    successful = sum(results)
    total = len(results)
    
    print(f"Test eseguiti: {total}")
    print(f"Test riusciti: {successful}")
    print(f"Test falliti: {total - successful}")
    
    if successful == total:
        print("🎉 Tutti i test sono passati!")
        return 0
    else:
        print("⚠️  Alcuni test sono falliti. Controlla i log sopra.")
        return 1

def run_specific_test(test_file):
    """Esegue un test specifico"""
    print(f"🧪 Esecuzione test specifico: {test_file}")
    print("=" * 50)
    
    cmd = ["python", "-m", "pytest", test_file, "-v", "--tb=short"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        return result.returncode
        
    except FileNotFoundError:
        print("❌ pytest non trovato. Installa pytest: pip install pytest")
        return 1
    except Exception as e:
        print(f"❌ Errore durante l'esecuzione: {e}")
        return 1

def main():
    """Funzione principale"""
    if len(sys.argv) > 1:
        # Esegui test specifico
        test_file = sys.argv[1]
        return run_specific_test(test_file)
    else:
        # Esegui tutti i test
        return run_tests()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
