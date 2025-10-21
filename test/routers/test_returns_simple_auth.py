"""
Test semplificati per i resi con autenticazione (senza emoji)
"""
import requests
import json

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

def get_auth_token():
    """Ottiene il token di autenticazione per i test"""
    # Prova diverse credenziali comuni
    credentials = [
        ("admin", "admin"),
        ("test", "test"),
        ("user", "user"),
        ("elettronewtest", "elettronew")
    ]
    
    for username, password in credentials:
        login_data = {
            "username": username,
            "password": password
        }
        
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
        if response.status_code == 200:
            print(f"Login successful with {username}")
            return response.json()["access_token"]
        else:
            print(f"Login failed with {username}: {response.status_code}")
    
    print("All login attempts failed")
    return None

def get_auth_headers():
    """Ottiene gli header di autenticazione"""
    token = get_auth_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}

def test_simple_return():
    """Test semplice per verificare l'autenticazione"""
    print("\n=== Test semplice reso ===")
    
    # Ottieni token di autenticazione
    headers = get_auth_headers()
    if not headers:
        print("ERRORE: Impossibile ottenere token di autenticazione")
        return False
    
    print("Token di autenticazione ottenuto con successo")
    
    # Prova a creare un ordine semplice
    order_data = {
        "id_customer": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 1,
        "payment_method": "cash",
        "order_details": [
            {
                "id_product": 1,
                "product_name": "Prodotto Test",
                "product_reference": "TEST001",
                "product_price": 10.0,
                "product_qty": 1,
                "product_weight": 1.0,
                "id_tax": 1,
                "reduction_percent": 0.0,
                "reduction_amount": 0.0
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/orders/", json=order_data, headers=headers)
    print(f"Response status: {response.status_code}")
    print(f"Response text: {response.text}")
    
    if response.status_code == 201:
        print("SUCCESS: Ordine creato con successo")
        order_response = response.json()
        order_id = order_response["order"]["id_order"]
        
        # Prova a creare un reso
        return_data = {
            "order_details": [
                {
                    "id_order_detail": 1,  # Dovrebbe essere ottenuto dinamicamente
                    "quantity": 1,
                    "unit_price": 10.0
                }
            ],
            "includes_shipping": False,
            "note": "Test reso"
        }
        
        response = requests.post(f"{API_BASE}/orders/{order_id}/returns", json=return_data, headers=headers)
        print(f"Return response status: {response.status_code}")
        print(f"Return response text: {response.text}")
        
        if response.status_code == 201:
            print("SUCCESS: Reso creato con successo")
            return True
        else:
            print("FAILED: Errore nella creazione del reso")
            return False
    else:
        print("FAILED: Errore nella creazione dell'ordine")
        return False

if __name__ == "__main__":
    print("=== TEST SEMPLICE RESI CON AUTENTICAZIONE ===")
    
    try:
        if test_simple_return():
            print("\nTUTTI I TEST SONO PASSATI!")
        else:
            print("\nALCUNI TEST SONO FALLITI!")
    except Exception as e:
        print(f"\nERRORE NEI TEST: {e}")
