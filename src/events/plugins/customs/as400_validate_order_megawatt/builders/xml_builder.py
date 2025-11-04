"""Builder XML per formato XML ordine AS400."""

import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from src.models.order import Order
from ..services.order_service import OrderDataService


class OrderXMLBuilder:
    """Builder per creare XML ordine AS400."""

    def __init__(self, order_service: OrderDataService):
        """Inizializza builder con servizio ordini."""
        self.order_service = order_service

    def build_order_xml(self, order: Order) -> str:
        """
        Costruisce XML ordine completo secondo specifiche AS400.
        
        Args:
            order: Oggetto Order con tutte le relazioni caricate
            
        Returns:
            Stringa XML pronta per envelope SOAP
        """
        root = ET.Element("ordine")
        
        # Costruisci sezione spedizione
        self._build_spedizione(root, order)
        
        # Costruisci header ordine
        self._build_order_header(root, order)
        
        # Costruisci sezione prodotti
        self._build_prodotti(root, order)
        
        # Costruisci totali ordine
        self._build_totals(root, order)
        
        # Converti in stringa con encoding corretto
        xml_str = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
        
        # Aggiungi dichiarazione XML
        return f'<?xml version="1.0" encoding="utf-8"?>\n{xml_str}'

    def _build_spedizione(self, parent: ET.Element, order: Order) -> None:
        """Costruisce sezione spedizione (indirizzo di spedizione)."""
        spedizione = ET.SubElement(parent, "spedizione")
        
        address = order.address_delivery
        if address:
            self._safe_set_text(spedizione, "ragioneSociale", address.company)
            self._safe_set_text(spedizione, "ragioneSociale2", None)
            self._safe_set_text(spedizione, "indirizzo", address.address1)
            self._safe_set_text(spedizione, "indirizzo2", address.address2)
            self._safe_set_text(spedizione, "CAP", address.postcode)
            self._safe_set_text(spedizione, "localita", address.city)
            self._safe_set_text(spedizione, "provincia", address.state)
            
            # Codice ISO paese
            country_code = ""
            if address.country:
                country_code = address.country.iso_code or ""
            self._safe_set_text(spedizione, "nazione", country_code)
            
            self._safe_set_text(spedizione, "CAPEstero", None)
            
            # CognomeNome: firstname + lastname
            cognome_nome = ""
            if address.firstname or address.lastname:
                cognome_nome = f"{address.firstname or ''} {address.lastname or ''}".strip()
            self._safe_set_text(spedizione, "cognomeNome", cognome_nome)
            
            self._safe_set_text(spedizione, "telefono", address.phone)
            
            # Email dal customer
            email = ""
            if order.customer:
                email = order.customer.email or ""
            self._safe_set_text(spedizione, "email", email)
            
            # Note: nome corriere spedizione
            shipping_note = ""
            print(order.shipments)
            if order.shipments and hasattr(order.shipments, 'carrier_api') and order.shipments.carrier_api:
                shipping_note = order.shipments.carrier_api.name or ""
            self._safe_set_text(spedizione, "note", shipping_note)
        else:
            # Elementi indirizzo vuoti
            for tag in ["ragioneSociale", "ragioneSociale2", "indirizzo", "indirizzo2", 
                       "CAP", "localita", "provincia", "nazione", "CAPEstero", 
                       "cognomeNome", "telefono", "email", "note"]:
                self._safe_set_text(spedizione, tag, "")

    def _build_order_header(self, parent: ET.Element, order: Order) -> None:
        """Costruisce sezione header ordine."""
        # Partita IVA WebMarket
        vat_number = self.order_service.get_vat_number()
        self._safe_set_text(parent, "partitaIvaWebMarket", vat_number)
        
        # Numero ordine (internal_reference)
        self._safe_set_text(parent, "numeroOrdine", order.internal_reference)
        
        # Data ordine (formato: dd/MM/yyyy)
        data_ordine = ""
        if order.date_add:
            if isinstance(order.date_add, datetime):
                data_ordine = order.date_add.strftime("%d/%m/%Y")
            else:
                data_ordine = order.date_add
        self._safe_set_text(parent, "dataOrdine", data_ordine)
        
        # Tipo ordine: sempre "P"
        self._safe_set_text(parent, "tipoOrdine", "P")
        
        # Stato ordine: "P" se pagamento completo, altrimenti "N"
        stato_ordine = "N"
        if order.payment and order.payment.is_complete_payment:
            stato_ordine = "P"
        self._safe_set_text(parent, "statoOrdine", stato_ordine)
        
        # Note: vuoto
        self._safe_set_text(parent, "note", None)
        
        # Riferimento ordine cliente
        self._safe_set_text(parent, "riferimentoOrdineCliente", order.reference)

    def _build_prodotti(self, parent: ET.Element, order: Order) -> None:
        """Costruisce sezione prodotti."""
        prodotti = ET.SubElement(parent, "prodotti")
        
        if not order.order_details:
            return
        
        for idx, detail in enumerate(order.order_details, start=1):
            prodotto = ET.SubElement(prodotti, "prodotto")
            
            # Progressivo riga (1, 2, 3...)
            self._safe_set_text(prodotto, "progressivoRiga", str(idx))
            
            # ID articolo web (Product.id_origin)
            id_articolo = "0"
            if detail.product and detail.product.id_origin:
                id_articolo = str(detail.product.id_origin)
            self._safe_set_text(prodotto, "idArticoloWeb", id_articolo)
            
            # Unità di misura: sempre "PCE"
            self._safe_set_text(prodotto, "unitaDiMisura", "PCE")
            
            # Prezzo unitario
            prezzo_unitario = detail.product_price or 0.0
            self._safe_set_text(prodotto, "prezzoUnitario", str(prezzo_unitario))
            
            # Moltiplicatore: sempre 1
            self._safe_set_text(prodotto, "moltiplicatore", "1")
            
            # Quantità
            quantita = detail.product_qty or 1
            self._safe_set_text(prodotto, "quantita", str(quantita))
            
            # Totale imponibile riga
            totale_imponibile_riga = prezzo_unitario * quantita
            self._safe_set_text(prodotto, "totaleImponibileRiga", f"{totale_imponibile_riga:.6f}")
            
            # Percentuale IVA (recuperata direttamente dalla query con join)
            percentuale_iva = getattr(detail, 'tax_percentage', 0.0)
            self._safe_set_text(prodotto, "percentualeIVA", f"{percentuale_iva:.2f}")
            
            # Note: vuoto
            self._safe_set_text(prodotto, "note", None)
            
            # Totale IVA riga
            totale_iva_riga = totale_imponibile_riga * (percentuale_iva / 100.0)
            self._safe_set_text(prodotto, "totaleIVA", f"{totale_iva_riga:.2f}")
            
            # Totale riga (imponibile + IVA)
            totale_riga = totale_imponibile_riga * (1 + percentuale_iva / 100.0)
            self._safe_set_text(prodotto, "totaleRiga", f"{totale_riga:.2f}")
            
            # Prezzo vendita web
            self._safe_set_text(prodotto, "prezzoVenditaWeb", str(prezzo_unitario))

    def _build_totals(self, parent: ET.Element, order: Order) -> None:
        """Costruisce sezione totali ordine."""
        # Valuta: sempre "EUR"
        self._safe_set_text(parent, "valuta", "EUR")
        
        # Totale aggiustamento: sempre 0
        self._safe_set_text(parent, "totaleAggiustamento", "0")
        
        # Totale imponibile e IVA: calcolati in un unico loop
        totale_imponibile = 0.0
        totale_iva = 0.0
        if order.order_details:
            for detail in order.order_details:
                prezzo = detail.product_price or 0.0
                qty = detail.product_qty or 1
                totale_riga = prezzo * qty
                totale_imponibile += totale_riga
                percentuale = getattr(detail, 'tax_percentage', 0.0)
                totale_iva += totale_riga * (percentuale / 100.0)
        self._safe_set_text(parent, "totaleImponibile", f"{totale_imponibile:.2f}")
        self._safe_set_text(parent, "totaleIVA", f"{totale_iva:.2f}")
        
        # Totale ordine
        totale_ordine = order.total_paid or 0.0
        self._safe_set_text(parent, "totaleOrdine", f"{totale_ordine:.2f}")

    def _safe_set_text(self, parent: ET.Element, tag: str, value: Optional[str]) -> None:
        """Imposta in sicurezza il contenuto testo di un elemento, gestendo None e valori vuoti."""
        element = ET.SubElement(parent, tag)
        if value is None:
            element.text = ""
        else:
            element.text = str(value)

