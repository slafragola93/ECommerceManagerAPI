#!/usr/bin/env python3
"""
Script di Setup Iniziale per ECommerceManagerAPI
Esegue automaticamente il setup necessario al primo accesso
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.models.app_configuration import AppConfiguration
from src.models.order_state import OrderState
from src.models.platform import Platform

def check_first_access():
    """Controlla se è il primo accesso al sistema"""
    db = next(get_db())
    
    try:
        # Verifica app_configurations
        app_configs_count = db.query(AppConfiguration).count()
        
        # Verifica order_states
        order_states_count = db.query(OrderState).count()
        
        # Verifica piattaforme
        platforms_count = db.query(Platform).count()
        
        print(f"📊 Stato attuale del sistema:")
        print(f"  - App Configurations: {app_configs_count}")
        print(f"  - Order States: {order_states_count}")
        print(f"  - Platforms: {platforms_count}")
        
        # È primo accesso se mancano configurazioni essenziali
        is_first_access = (
            app_configs_count == 0 or 
            order_states_count == 0 or 
            platforms_count == 0
        )
        
        return is_first_access
        
    except Exception as e:
        print(f"❌ Errore durante il controllo: {str(e)}")
        return True  # In caso di errore, considera primo accesso
    finally:
        db.close()

def setup_app_configurations():
    """Inizializza le configurazioni dell'applicazione"""
    print("\n🔧 Configurando App Configurations...")
    
    try:
        # Eseguire lo script di inizializzazione
        import subprocess
        result = subprocess.run([
            sys.executable, 
            "scripts/init_app_configurations.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ App Configurations configurate con successo")
        else:
            print(f"⚠️  App Configurations: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Errore configurazione App Configurations: {str(e)}")

def setup_order_states():
    """Inizializza gli order states"""
    print("\n📦 Configurando Order States...")
    
    db = next(get_db())
    
    try:
        # Controlla se esistono già
        existing_count = db.query(OrderState).count()
        
        if existing_count > 0:
            print(f"ℹ️  Order States già presenti: {existing_count}")
            return
        
        # Stati degli ordini da inserire
        order_states_data = [
            (1, 'In Preparazione'),
            (2, 'Pronti Per La Spedizione'),
            (3, 'Spediti'),
            (4, 'Spedizione Confermata'),
            (5, 'Annullati'),
            (6, 'In Attesa')
        ]
        
        # Inserisce i nuovi order_states
        for id_state, name in order_states_data:
            order_state = OrderState(
                id_order_state=id_state,
                name=name
            )
            db.add(order_state)
            print(f"  ✅ Aggiunto: ID {id_state} - {name}")
        
        db.commit()
        print(f"✅ Inseriti {len(order_states_data)} order states")
        
    except Exception as e:
        print(f"❌ Errore configurazione Order States: {str(e)}")
        db.rollback()
    finally:
        db.close()

def setup_ecommerce_platform():
    """Inizializza la piattaforma e-commerce"""
    print("\n🛒 Configurando Piattaforma E-commerce...")
    
    try:
        # Eseguire lo script di inizializzazione PrestaShop
        import subprocess
        result = subprocess.run([
            sys.executable, 
            "scripts/init_prestashop_platform.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Piattaforma E-commerce configurata con successo")
        else:
            print(f"⚠️  Piattaforma E-commerce: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Errore configurazione Piattaforma E-commerce: {str(e)}")

def verify_setup():
    """Verifica che il setup sia completato correttamente"""
    print("\n🔍 Verificando setup...")
    
    db = next(get_db())
    
    try:
        # Verifica finale
        app_configs_count = db.query(AppConfiguration).count()
        order_states_count = db.query(OrderState).count()
        platforms_count = db.query(Platform).count()
        
        print(f"📊 Setup completato:")
        print(f"  - App Configurations: {app_configs_count}")
        print(f"  - Order States: {order_states_count}")
        print(f"  - Platforms: {platforms_count}")
        
        if app_configs_count > 0 and order_states_count > 0 and platforms_count > 0:
            print("🎉 Setup iniziale completato con successo!")
            return True
        else:
            print("⚠️  Setup incompleto. Verificare le configurazioni.")
            return False
            
    except Exception as e:
        print(f"❌ Errore durante la verifica: {str(e)}")
        return False
    finally:
        db.close()

def main():
    """Funzione principale di setup"""
    print("🚀 ECommerceManagerAPI - Setup Iniziale")
    print("=" * 50)
    
    # Controlla se è il primo accesso
    if not check_first_access():
        print("\nℹ️  Sistema già configurato. Setup non necessario.")
        return
    
    print("\n🎉 Primo accesso rilevato! Eseguendo setup iniziale...")
    
    # Esegue il setup
    setup_app_configurations()
    setup_order_states()
    setup_ecommerce_platform()
    
    # Verifica il setup
    if verify_setup():
        print("\n✅ Setup iniziale completato con successo!")
        print("🚀 Ora puoi avviare l'API con: uvicorn src.main:app --reload")
    else:
        print("\n❌ Setup incompleto. Verificare manualmente le configurazioni.")
        print("📖 Consultare SETUP_INIZIALE.md per istruzioni dettagliate.")

if __name__ == "__main__":
    main()
