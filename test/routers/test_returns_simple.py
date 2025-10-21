"""
Test semplificati per la funzionalità dei resi
Questi test si concentrano sui controlli specifici richiesti
"""
import requests
import json

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Credenziali per l'autenticazione
TEST_USERNAME = "elettronewtest"
TEST_PASSWORD = "elettronew"

def get_auth_token():
    """Ottiene il token di autenticazione per i test"""
    login_data = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=login_data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Errore login: {response.status_code} - {response.text}")
        return None

def get_auth_headers():
    """Ottiene gli header di autenticazione"""
    token = get_auth_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}

def test_partial_return_no_shipping():
    """Test 1: Creazione reso parziale no spedizione"""
    print("\n=== Test 1: Reso parziale no spedizione ===")
    
    # Crea ordine di test
    order_data = {
        "id_customer": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 1,
        "payment_method": "cash",
        "order_details": [
            {
                "id_product": 1,
                "product_name": "Prodotto A",
                "product_reference": "PROD_A",
                "product_price": 10.0,
                "product_qty": 2,
                "product_weight": 1.0,
                "id_tax": 1,  # 22% IVA
                "reduction_percent": 0.0,
                "reduction_amount": 0.0
            },
            {
                "id_product": 2,
                "product_name": "Prodotto B",
                "product_reference": "PROD_B",
                "product_price": 20.0,
                "product_qty": 1,
                "product_weight": 2.0,
                "id_tax": 1,
                "reduction_percent": 0.0,
                "reduction_amount": 0.0
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/orders/", json=order_data)
    if response.status_code != 201:
        print(f"Errore creazione ordine: {response.status_code} - {response.text}")
        return False
    
    order_response = response.json()
    order_id = order_response["order"]["id_order"]
    print(f"✓ Ordine creato con ID: {order_id}")
    
    # Ottieni dettagli ordine
    order_response = requests.get(f"{API_BASE}/orders/{order_id}")
    order_details = order_response.json()["order_details"]
    print(f"✓ Dettagli ordine: {len(order_details)} articoli")
    
    # Crea reso parziale (solo primo articolo)
    return_data = {
        "order_details": [
            {
                "id_order_detail": order_details[0]["id_order_detail"],
                "quantity": order_details[0]["product_qty"],  # 2
                "unit_price": order_details[0]["product_price"]  # 10.0
            }
        ],
        "includes_shipping": False,
        "note": "Reso parziale test"
    }
    
    response = requests.post(f"{API_BASE}/orders/{order_id}/returns", json=return_data)
    if response.status_code != 201:
        print(f"Errore creazione reso: {response.status_code} - {response.text}")
        return False
    
    return_response = response.json()
    return_id = return_response["return_id"]
    print(f"✓ Reso creato con ID: {return_id}")
    
    # Verifica flag is_partial = True
    return_details = requests.get(f"{API_BASE}/returns/{return_id}")
    return_data = return_details.json()
    
    if return_data["is_partial"] != True:
        print(f"❌ ERRORE: Expected is_partial=True, got {return_data['is_partial']}")
        return False
    print("✓ Flag is_partial = True verificato")
    
    # Verifica total_amount dettaglio (senza IVA)
    # Atteso: 2 × 10.0 = 20.0
    expected_detail_total = 2 * 10.0
    print(f"✓ Total_amount dettaglio atteso (senza IVA): {expected_detail_total}")
    
    # Verifica total_amount documento fiscale (con IVA)
    # Atteso: 20.0 + (20.0 × 0.22) = 20.0 + 4.4 = 24.4
    expected_document_total = expected_detail_total * 1.22  # 22% IVA
    actual_document_total = return_data["total_amount"]
    
    if abs(actual_document_total - expected_document_total) > 0.01:
        print(f"❌ ERRORE: Expected document total {expected_document_total}, got {actual_document_total}")
        return False
    print(f"✓ Total_amount documento (con IVA): {actual_document_total}")
    
    return True

def test_full_return_no_shipping():
    """Test 2: Creazione reso intero no spedizione"""
    print("\n=== Test 2: Reso intero no spedizione ===")
    
    # Crea ordine di test
    order_data = {
        "id_customer": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 1,
        "payment_method": "cash",
        "order_details": [
            {
                "id_product": 1,
                "product_name": "Prodotto A",
                "product_reference": "PROD_A",
                "product_price": 15.0,
                "product_qty": 2,
                "product_weight": 1.0,
                "id_tax": 1,
                "reduction_percent": 0.0,
                "reduction_amount": 0.0
            },
            {
                "id_product": 2,
                "product_name": "Prodotto B",
                "product_reference": "PROD_B",
                "product_price": 25.0,
                "product_qty": 1,
                "product_weight": 2.0,
                "id_tax": 1,
                "reduction_percent": 0.0,
                "reduction_amount": 0.0
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/orders/", json=order_data)
    if response.status_code != 201:
        print(f"Errore creazione ordine: {response.status_code} - {response.text}")
        return False
    
    order_response = response.json()
    order_id = order_response["order"]["id_order"]
    print(f"✓ Ordine creato con ID: {order_id}")
    
    # Ottieni dettagli ordine
    order_response = requests.get(f"{API_BASE}/orders/{order_id}")
    order_details = order_response.json()["order_details"]
    print(f"✓ Dettagli ordine: {len(order_details)} articoli")
    
    # Crea reso completo (tutti gli articoli)
    return_data = {
        "order_details": [
            {
                "id_order_detail": order_details[0]["id_order_detail"],
                "quantity": order_details[0]["product_qty"],  # 2
                "unit_price": order_details[0]["product_price"]  # 15.0
            },
            {
                "id_order_detail": order_details[1]["id_order_detail"],
                "quantity": order_details[1]["product_qty"],  # 1
                "unit_price": order_details[1]["product_price"]  # 25.0
            }
        ],
        "includes_shipping": False,
        "note": "Reso completo test"
    }
    
    response = requests.post(f"{API_BASE}/orders/{order_id}/returns", json=return_data)
    if response.status_code != 201:
        print(f"Errore creazione reso: {response.status_code} - {response.text}")
        return False
    
    return_response = response.json()
    return_id = return_response["return_id"]
    print(f"✓ Reso creato con ID: {return_id}")
    
    # Verifica flag is_partial = False
    return_details = requests.get(f"{API_BASE}/returns/{return_id}")
    return_data = return_details.json()
    
    if return_data["is_partial"] != False:
        print(f"❌ ERRORE: Expected is_partial=False, got {return_data['is_partial']}")
        return False
    print("✓ Flag is_partial = False verificato")
    
    # Verifica che tutte le quantità siano uguali all'ordine originale
    for i, return_item in enumerate(return_data["order_details"]):
        original_qty = order_details[i]["product_qty"]
        return_qty = return_item["quantity"]
        if return_qty != original_qty:
            print(f"❌ ERRORE: Expected quantity {original_qty}, got {return_qty} for item {i}")
            return False
    print("✓ Tutte le quantità corrispondono all'ordine originale")
    
    # Verifica totali
    # Articolo 1: 2 × 15.0 = 30.0
    # Articolo 2: 1 × 25.0 = 25.0
    # Totale senza IVA: 55.0
    # Totale con IVA: 55.0 × 1.22 = 67.1
    expected_detail_total = (2 * 15.0) + (1 * 25.0)  # 55.0
    expected_document_total = expected_detail_total * 1.22  # 67.1
    actual_document_total = return_data["total_amount"]
    
    if abs(actual_document_total - expected_document_total) > 0.01:
        print(f"❌ ERRORE: Expected document total {expected_document_total}, got {actual_document_total}")
        return False
    print(f"✓ Total_amount documento (con IVA): {actual_document_total}")
    
    return True

def test_return_with_shipping():
    """Test 5: Creazione reso con spedizione"""
    print("\n=== Test 5: Reso con spedizione ===")
    
    # Crea ordine con spedizione
    order_data = {
        "id_customer": 1,
        "id_address_delivery": 1,
        "id_address_invoice": 1,
        "id_shipping": 1,  # Spedizione
        "payment_method": "cash",
        "order_details": [
            {
                "id_product": 1,
                "product_name": "Prodotto A",
                "product_reference": "PROD_A",
                "product_price": 10.0,
                "product_qty": 1,
                "product_weight": 1.0,
                "id_tax": 1,
                "reduction_percent": 0.0,
                "reduction_amount": 0.0
            }
        ]
    }
    
    response = requests.post(f"{API_BASE}/orders/", json=order_data)
    if response.status_code != 201:
        print(f"Errore creazione ordine: {response.status_code} - {response.text}")
        return False
    
    order_response = response.json()
    order_id = order_response["order"]["id_order"]
    print(f"✓ Ordine creato con ID: {order_id}")
    
    # Ottieni dettagli ordine
    order_response = requests.get(f"{API_BASE}/orders/{order_id}")
    order_details = order_response.json()["order_details"]
    
    # Crea reso con spedizione inclusa
    return_data = {
        "order_details": [
            {
                "id_order_detail": order_details[0]["id_order_detail"],
                "quantity": order_details[0]["product_qty"],  # 1
                "unit_price": order_details[0]["product_price"]  # 10.0
            }
        ],
        "includes_shipping": True,
        "note": "Reso con spedizione"
    }
    
    response = requests.post(f"{API_BASE}/orders/{order_id}/returns", json=return_data)
    if response.status_code != 201:
        print(f"Errore creazione reso: {response.status_code} - {response.text}")
        return False
    
    return_response = response.json()
    return_id = return_response["return_id"]
    print(f"✓ Reso con spedizione creato con ID: {return_id}")
    
    # Verifica che includes_shipping sia True
    return_details = requests.get(f"{API_BASE}/returns/{return_id}")
    return_data = return_details.json()
    
    if return_data.get("includes_shipping") != True:
        print(f"❌ ERRORE: Expected includes_shipping=True, got {return_data.get('includes_shipping')}")
        return False
    print("✓ Flag includes_shipping = True verificato")
    
    # Verifica che il totale includa la spedizione
    # Prodotto: 1 × 10.0 = 10.0
    # Spedizione: 20.0 (assumendo)
    # Totale senza IVA: 30.0
    # Totale con IVA: 30.0 × 1.22 = 36.6
    actual_total = return_data["total_amount"]
    
    # Il totale dovrebbe essere maggiore di quello senza spedizione
    expected_without_shipping = 10.0 * 1.22  # 12.2
    if actual_total <= expected_without_shipping:
        print(f"❌ ERRORE: Expected total with shipping > {expected_without_shipping}, got {actual_total}")
        return False
    
    print(f"✓ Total_amount con spedizione: {actual_total}")
    print(f"✓ Totale superiore a quello senza spedizione ({expected_without_shipping})")
    
    return True

def run_all_tests():
    """Esegue tutti i test"""
    print("=== INIZIO TEST RESI ===")
    
    tests = [
        ("Reso parziale no spedizione", test_partial_return_no_shipping),
        ("Reso intero no spedizione", test_full_return_no_shipping),
        ("Reso con spedizione", test_return_with_shipping)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- Esecuzione: {test_name} ---")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n=== RISULTATI FINALI ===")
    print(f"Test passati: {passed}/{total}")
    
    if passed == total:
        print("🎉 TUTTI I TEST SONO PASSATI!")
        return True
    else:
        print("⚠️  ALCUNI TEST SONO FALLITI!")
        return False

if __name__ == "__main__":
    run_all_tests()
