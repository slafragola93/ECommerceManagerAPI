# Prompt FE — Lista fatture/NC: sdi_status + pagamento ordine (BE 2026-09-11)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale (Elettronew)**.

---

## Contesto

Il backend **ECommerceManagerAPI** ha esteso `GET /api/v1/fiscal_documents/` (stesso endpoint, niente N GET).  
Scopo: un solo badge Stato (workflow XML + esito AdE) e la colonna Pagamento = metodo **dell’ordine**.

**Non** chiamare `GET .../sdi-status` per ogni riga.  
**Non** chiamare `GET /api/v1/orders/{id}` per ogni riga.  
**Non** inventare overlay FE su `status` grezzo.

Doc BE: `docs/FATTURAPA.md` §5, `docs/BE_PROMPT_STATUS_RAPIDO_DOCUMENTI.md`.

---

## Contratto lista (ogni item in `documents[]`)

Campi nuovi / da bindare:

```ts
interface FiscalDocumentListItem {
  id_fiscal_document: number;
  id_order: number;
  status: 'pending' | 'generated' | 'uploaded' | 'sent' | 'error' | string;
  is_electronic: boolean;

  // Esito AdE (asincrono — può essere null subito dopo l’invio)
  sdi_status:
    | 'consegnata'
    | 'scartata'
    | 'mancata_consegna'
    | 'accettata'
    | 'rifiutata'
    | 'decorrenza_termini'
    | null;
  identificativo_sdi: string | null;

  // Esito intermediario / overlay (NON allargare con consegnata/scartata)
  fatturapa_status: 'uploaded' | 'sent' | 'error' | null;
  fatturapa_error_message: string | null;

  // Pagamento ordine (non snapshot fiscale)
  order_payment_name: string | null; // "Bonifico", "PayPal", …
  id_order_payment: number | null;   // id catalogo payments.id_payment

  // P1 già esposti
  id_customer: number | null;
  customer_name: string | null;      // ragione sociale o "Cognome Nome"
  is_payed: boolean;
  order_shipped: boolean;            // true se orders.id_shipping valorizzato
  mail_status: 'sent' | 'pending' | 'error' | null; // writer cortesia assente → di solito null
}
```

`id_order_payment` **non** è la PK `order_payments`: è `orders.id_payment` (catalogo).

---

## Badge Stato (obbligatorio)

Un solo badge. Priorità:

| Condizione | Label FE |
|------------|----------|
| `status === 'pending'` (no XML) | In attesa XML |
| `status === 'generated'` e `sdi_status == null` | XML generato |
| `status` in `uploaded\|sent` e `sdi_status == null` | **In attesa esito** |
| `sdi_status === 'consegnata'` | Consegnata |
| `sdi_status === 'scartata'` | Scartata |
| `sdi_status === 'mancata_consegna'` | Mancata consegna |
| `sdi_status === 'accettata'` | Accettata |
| `sdi_status === 'rifiutata'` | Rifiutata |
| `sdi_status === 'decorrenza_termini'` | Decorrenza termini |
| `status === 'error'` e `sdi_status == null` | Errore invio |

`sdi_status: null` **subito dopo** `send-to-sdi` è corretto: RC/NS arrivano dal polling BE. Non “correggere” in FE.

`fatturapa_status` resta per l’icona rapida: `sent` se RC/MC/NE/DT; `error` se NS (“Scartata da SDI”). Non sostituire `sdi_status` con un enum inventato.

Timeline completa (dettaglio, un solo doc): `GET /api/v1/fiscal_documents/{id}/sdi-status`.

---

## Colonna Pagamento (obbligatorio)

Mostrare **`order_payment_name`**. Se `null` → `—`.

Non usare un pagamento di default del documento fiscale. Non fetchare l’ordine.

Verifica: un ordine Bonifico e uno PayPal/Carta devono mostrare etichette diverse, uguali al dettaglio ordine.

---

## Flusso invio (BE attuale — API accesa)

L’invio **non** è più manuale sul portale.

1. `POST .../generate-xml` → 422: correggi (PATCH), resti `pending`
2. `POST .../send-to-sdi` body **ufficiale**: `{ "send_to_sdi": true }`
3. Attendi `sdi_status` (lista o `GET .../sdi-status`)
4. NS: PATCH (stesso numero/data) + `POST .../retry-send`
5. RC/MC: emessa, non reinviare

Mostrare **Invia a SDI** e **Reinvia dopo scarto**.  
Senza `{ "send_to_sdi": true }` il BE fa solo deposito (`UploadStop1`), non SdI.

`POST .../reset-xml`: elimina XML, torna `pending`. 400 se SdI già evaso.

`PATCH` 409 se `sdi_status` in consegnata|accettata|rifiutata|decorrenza_termini|mancata_consegna.

---

## Cosa non fare

- N GET `sdi-status` o `orders/{id}` in lista
- Allargare `fatturapa_status` con `consegnata` / `scartata`
- Polling SDI dal FE dopo `send-to-sdi`
- Cambiare il body di `send-to-sdi`
- Implementare mail cortesia (`mail_status` è display-only)

---

## Esempio payload lista

```json
{
  "documents": [
    {
      "id_fiscal_document": 10,
      "id_order": 456,
      "status": "sent",
      "fatturapa_status": "sent",
      "sdi_status": null,
      "identificativo_sdi": null,
      "order_payment_name": "Bonifico",
      "id_order_payment": 3,
      "id_customer": 89,
      "customer_name": "Rossi Mario",
      "is_payed": true,
      "order_shipped": false,
      "mail_status": null
    },
    {
      "id_fiscal_document": 11,
      "id_order": 457,
      "status": "sent",
      "fatturapa_status": "error",
      "fatturapa_error_message": "Scartata da SDI",
      "sdi_status": "scartata",
      "identificativo_sdi": "1234567890",
      "order_payment_name": "PayPal",
      "id_order_payment": 5,
      "id_customer": 90,
      "customer_name": "Bianchi Srl",
      "is_payed": true,
      "order_shipped": true,
      "mail_status": null
    }
  ],
  "total": 2,
  "page": 1,
  "limit": 25
}
```

Riga 10: badge **In attesa esito**, pagamento Bonifico.  
Riga 11: badge **Scartata**, pagamento PayPal — senza aprire il dettaglio.

---

## Done criteria

- [ ] Modelli TS lista aggiornati (`sdi_status`, `order_payment_name`, campi P1)
- [ ] Badge Stato usa `status` + `sdi_status` (tabella sopra)
- [ ] Colonna Pagamento = `order_payment_name` o `—`
- [ ] Nessun loop `sdi-status` / `orders/{id}` in lista
- [ ] Invia a SDI con `{ "send_to_sdi": true }`; dopo NS `retry-send`
- [ ] Smoke: riga inviata senza notifica = In attesa esito; riga NS = Scartata
