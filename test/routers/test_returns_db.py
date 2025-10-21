"""
Test per i resi usando direttamente il database (senza autenticazione HTTP)
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.repository.fiscal_document_repository import FiscalDocumentRepository
from src.models.order import Order
from src.models.order_detail import OrderDetail
from src.models.customer import Customer
from src.models.address import Address
from src.models.tax import Tax

def create_test_data():
    """Crea dati di test nel database"""
    db = SessionLocal()
    try:
        # Crea customer di test
        customer = Customer(
            firstname="Test",
            lastname="Customer",
            email="test@test.com"
        )
        db.add(customer)
        db.flush()
        
        # Crea address di test
        address = Address(
            id_customer=customer.id_customer,
            firstname="Test",
            lastname="Customer",
            address1="Via Test 123",
            city="Test City",
            postcode="12345",
            id_country=1  # Assumendo che esista un paese con ID 1
        )
        db.add(address)
        db.flush()
        
        # Crea tax di test
        tax = Tax(
            name="IVA 22%",
            percentage=22.0
        )
        db.add(tax)
        db.flush()
        
        # Crea ordine di test
        order = Order(
            id_customer=customer.id_customer,
            id_address_delivery=address.id_address,
            id_address_invoice=address.id_address,
            reference="TEST001",
            total_price_tax_excl=100.0,
            total_paid=0.0
        )
        db.add(order)
        db.flush()
        
        # Crea order details di test
        order_detail1 = OrderDetail(
            id_order=order.id_order,
            id_product=1,
            product_name="Prodotto Test 1",
            product_reference="TEST001",
            product_price=50.0,
            product_qty=2,
            product_weight=1.0,
            id_tax=tax.id_tax,
            reduction_percent=0.0,
            reduction_amount=0.0
        )
        db.add(order_detail1)
        
        order_detail2 = OrderDetail(
            id_order=order.id_order,
            id_product=2,
            product_name="Prodotto Test 2",
            product_reference="TEST002",
            product_price=30.0,
            product_qty=1,
            product_weight=2.0,
            id_tax=tax.id_tax,
            reduction_percent=0.0,
            reduction_amount=0.0
        )
        db.add(order_detail2)
        
        db.commit()
        
        return {
            "order_id": order.id_order,
            "customer_id": customer.id_customer,
            "address_id": address.id_address,
            "tax_id": tax.id_tax,
            "order_detail_ids": [order_detail1.id_order_detail, order_detail2.id_order_detail]
        }
        
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

def test_partial_return_no_shipping():
    """Test 1: Creazione reso parziale no spedizione"""
    print("\n=== Test 1: Reso parziale no spedizione ===")
    
    # Crea dati di test
    test_data = create_test_data()
    order_id = test_data["order_id"]
    order_detail_ids = test_data["order_detail_ids"]
    
    print(f"Ordine creato con ID: {order_id}")
    print(f"Order detail IDs: {order_detail_ids}")
    
    # Crea reso parziale (solo primo articolo)
    db = SessionLocal()
    try:
        fiscal_repo = FiscalDocumentRepository(db)
        
        return_items = [
            {
                "id_order_detail": order_detail_ids[0],
                "quantity": 2,  # Quantità completa del primo articolo
                "unit_price": 50.0,
                "id_tax": test_data["tax_id"]
            }
        ]
        
        return_doc = fiscal_repo.create_return(order_id, return_items, includes_shipping=False, note="Reso parziale test")
        return_id = return_doc.id_fiscal_document
        
        print(f"Reso creato con ID: {return_id}")
        
        # Verifica flag is_partial = True
        if return_doc.is_partial != True:
            print(f"ERRORE: Expected is_partial=True, got {return_doc.is_partial}")
            return False
        print("Flag is_partial = True verificato")
        
        # Verifica total_amount documento fiscale (con IVA)
        # Atteso: (2 × 50.0) × 1.22 = 100.0 × 1.22 = 122.0
        expected_document_total = (2 * 50.0) * 1.22  # 122.0
        actual_document_total = return_doc.total_amount
        
        if abs(actual_document_total - expected_document_total) > 0.01:
            print(f"ERRORE: Expected document total {expected_document_total}, got {actual_document_total}")
            return False
        print(f"Total_amount documento (con IVA): {actual_document_total}")
        
        # Verifica total_amount dettagli (senza IVA)
        from src.models.fiscal_document_detail import FiscalDocumentDetail
        details = db.query(FiscalDocumentDetail).filter(
            FiscalDocumentDetail.id_fiscal_document == return_id
        ).all()
        
        for detail in details:
            expected_detail_total = detail.quantity * detail.unit_price
            if abs(detail.total_amount - expected_detail_total) > 0.01:
                print(f"ERRORE: Expected detail total {expected_detail_total}, got {detail.total_amount}")
                return False
            print(f"Total_amount dettaglio (senza IVA): {detail.total_amount}")
        
        return True
        
    except Exception as e:
        print(f"ERRORE: {e}")
        return False
    finally:
        db.close()

def test_full_return_no_shipping():
    """Test 2: Creazione reso intero no spedizione"""
    print("\n=== Test 2: Reso intero no spedizione ===")
    
    # Crea dati di test
    test_data = create_test_data()
    order_id = test_data["order_id"]
    order_detail_ids = test_data["order_detail_ids"]
    
    print(f"Ordine creato con ID: {order_id}")
    
    # Crea reso completo (tutti gli articoli)
    db = SessionLocal()
    try:
        fiscal_repo = FiscalDocumentRepository(db)
        
        return_items = [
            {
                "id_order_detail": order_detail_ids[0],
                "quantity": 2,  # Quantità completa
                "unit_price": 50.0,
                "id_tax": test_data["tax_id"]
            },
            {
                "id_order_detail": order_detail_ids[1],
                "quantity": 1,  # Quantità completa
                "unit_price": 30.0,
                "id_tax": test_data["tax_id"]
            }
        ]
        
        return_doc = fiscal_repo.create_return(order_id, return_items, includes_shipping=False, note="Reso completo test")
        return_id = return_doc.id_fiscal_document
        
        print(f"Reso creato con ID: {return_id}")
        
        # Verifica flag is_partial = False
        if return_doc.is_partial != False:
            print(f"ERRORE: Expected is_partial=False, got {return_doc.is_partial}")
            return False
        print("Flag is_partial = False verificato")
        
        # Verifica total_amount documento fiscale (con IVA)
        # Articolo 1: 2 × 50.0 = 100.0
        # Articolo 2: 1 × 30.0 = 30.0
        # Totale senza IVA: 130.0
        # Totale con IVA: 130.0 × 1.22 = 158.6
        expected_document_total = (100.0 + 30.0) * 1.22  # 158.6
        actual_document_total = return_doc.total_amount
        
        if abs(actual_document_total - expected_document_total) > 0.01:
            print(f"ERRORE: Expected document total {expected_document_total}, got {actual_document_total}")
            return False
        print(f"Total_amount documento (con IVA): {actual_document_total}")
        
        return True
        
    except Exception as e:
        print(f"ERRORE: {e}")
        return False
    finally:
        db.close()

def run_all_tests():
    """Esegue tutti i test"""
    print("=== INIZIO TEST RESI CON DATABASE ===")
    
    tests = [
        ("Reso parziale no spedizione", test_partial_return_no_shipping),
        ("Reso intero no spedizione", test_full_return_no_shipping)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- Esecuzione: {test_name} ---")
        try:
            if test_func():
                print(f"SUCCESS: {test_name}: PASSED")
                passed += 1
            else:
                print(f"FAILED: {test_name}: FAILED")
        except Exception as e:
            print(f"ERROR: {test_name}: ERROR - {e}")
    
    print(f"\n=== RISULTATI FINALI ===")
    print(f"Test passati: {passed}/{total}")
    
    if passed == total:
        print("TUTTI I TEST SONO PASSATI!")
        return True
    else:
        print("ALCUNI TEST SONO FALLITI!")
        return False

if __name__ == "__main__":
    run_all_tests()
