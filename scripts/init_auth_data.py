#!/usr/bin/env python3
"""
Script per inizializzare i dati base del sistema
di autenticazione e permessi.
Eseguire una sola volta dopo la migration.
Rieseguibile in sicurezza - salta i dati gia' presenti.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import get_db
from src.models.role import Role, PermissionType
from src.models.app_modules import AppModule


def init_roles():
    """Inizializza i ruoli di sistema"""

    roles_data = [
        {
            'name': 'ADMIN',
            'description': 'Accesso completo a tutti i moduli',
            'permission_type': PermissionType.full_crud,
            'is_system': True
        }
    ]

    db = next(get_db())
    try:
        print("Ruoli esistenti: " + str(db.query(Role).count()))

        inserted = 0
        skipped = 0

        for role_data in roles_data:
            exists = db.query(Role).filter(
                Role.name == role_data['name']
            ).first()

            if exists:
                # Aggiorna i valori nel caso siano sbagliati
                exists.permission_type = role_data['permission_type']
                exists.is_system = role_data['is_system']
                exists.description = role_data['description']
                skipped += 1
                print("  Ruolo aggiornato: " + role_data['name'])
                continue

            role = Role(
                name=role_data['name'],
                description=role_data['description'],
                permission_type=role_data['permission_type'],
                is_system=role_data['is_system']
            )
            db.add(role)
            inserted += 1
            print("  Ruolo inserito: " + role_data['name'])

        db.commit()
        print("Ruoli inseriti: " + str(inserted))
        print("Ruoli aggiornati: " + str(skipped))

    except Exception as e:
        db.rollback()
        print("ERRORE durante inserimento ruoli: " + str(e))
        raise
    finally:
        db.close()


def init_modules():
    """Inizializza i moduli del gestionale"""

    modules_data = [
        ('orders',           'Ordini',          1),
        ('quotes',           'Preventivi',       2),
        ('fiscal_documents', 'Fatture',          3),
        ('products',         'Prodotti',         4),
        ('customers',        'Clienti',          5),
        ('shipments',        'Spedizioni',       6),
        ('carriers',         'Corrieri',         7),
        ('ddt',              'DDT',              8),
        ('returns',          'Resi',             9),
        ('payments',         'Pagamenti',       10),
        ('stores',           'Negozi',          11),
        ('platforms',        'Piattaforme',     12),
        ('settings',         'Impostazioni',    13),
        ('users',            'Utenti',          14),
        ('admin',            'Amministrazione', 15),
    ]

    db = next(get_db())
    try:
        print("Moduli esistenti: " + str(db.query(AppModule).count()))

        inserted = 0
        skipped = 0

        for name, label, sort_order in modules_data:
            exists = db.query(AppModule).filter(
                AppModule.name == name
            ).first()

            if exists:
                skipped += 1
                print("  Modulo gia' presente: " + name)
                continue

            module = AppModule(
                name=name,
                label=label,
                sort_order=sort_order,
                is_active=True
            )
            db.add(module)
            inserted += 1
            print("  Modulo inserito: " + name + " (" + label + ")")

        db.commit()
        print("Moduli inseriti: " + str(inserted))
        print("Moduli saltati: " + str(skipped))

    except Exception as e:
        db.rollback()
        print("ERRORE durante inserimento moduli: " + str(e))
        raise
    finally:
        db.close()


def main():
    print("=" * 50)
    print("Inizializzazione dati autenticazione")
    print("=" * 50)

    print("\n--- Ruoli ---")
    init_roles()

    print("\n--- Moduli ---")
    init_modules()

    print("\n" + "=" * 50)
    print("Completato")
    print("=" * 50)


if __name__ == '__main__':
    main()