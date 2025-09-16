#!/usr/bin/env python3
"""
Script per inizializzare gli Order States nel database
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.models.order_state import OrderState

def init_order_states():
    """Inizializza gli order states nel database"""
    
    # Stati degli ordini da inserire
    order_states_data = [
        (1, 'In Preparazione'),
        (2, 'Pronti Per La Spedizione'),
        (3, 'Spediti'),
        (4, 'Spedizione Confermata'),
        (5, 'Annullati'),
        (6, 'In Attesa')
    ]
    
    db = next(get_db())
    
    try:
        # Controlla se esistono già order_states
        existing_count = db.query(OrderState).count()
        print(f"📊 Order states esistenti: {existing_count}")
        
        if existing_count > 0:
            print("ℹ️  Order states già presenti nel database!")
            print("Order states esistenti:")
            for state in db.query(OrderState).order_by(OrderState.id_order_state).all():
                print(f"  ID: {state.id_order_state}, Nome: {state.name}")
            return
        
        # Inserisce i nuovi order_states
        print("📦 Inserendo order states...")
        for id_state, name in order_states_data:
            order_state = OrderState(
                id_order_state=id_state,
                name=name
            )
            db.add(order_state)
            print(f"  ✅ Aggiunto: ID {id_state} - {name}")
        
        # Commit delle modifiche
        db.commit()
        print(f"\n🎉 Inseriti {len(order_states_data)} order states con successo!")
        
        # Verifica finale
        print("\n📋 Order states nel database:")
        for state in db.query(OrderState).order_by(OrderState.id_order_state).all():
            print(f"  ID: {state.id_order_state}, Nome: {state.name}")
            
    except Exception as e:
        print(f"❌ Errore durante l'inizializzazione: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Inizializzazione Order States")
    print("=" * 40)
    init_order_states()
