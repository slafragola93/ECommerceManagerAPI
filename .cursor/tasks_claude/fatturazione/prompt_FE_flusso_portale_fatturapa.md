# Prompt FE — Flusso FatturaPA portale (allineamento BE 2026-09-10)

Incolla questo intero messaggio in chat sul **repo Angular del gestionale**.

---

## Contesto

L’invio allo SdI **non** passa più dai pulsanti API del gestionale. Flusso ufficiale / ufficio:

1. Crea fattura (`pending`)
2. Genera XML (`POST /api/v1/fiscal_documents/{id}/generate-xml`)
3. Operatore: scarica XML e completa controlli + invio sul **portale FatturaPA.com**
4. Esiti SdI (RC/NS/MC/NE/DT) via polling → `GET /api/v1/fiscal_documents/{id}/sdi-status`
5. Se NS: stesso numero/data, nuovo file (`generate-xml` ruota `progressivo_invio`), ritrasmetti dal portale (circolare 13/E)

`FATTURAPA_SDI_API_SEND_ENABLED=false`. `POST .../send-to-sdi` con `true` e `POST .../retry-send` rispondono **400**.

Doc BE: `docs/FATTURAPA.md`, `docs/BE_PROMPT_STATUS_RAPIDO_DOCUMENTI.md`.

---

## Task UI (obbligatori)

1. **Nascondere** i pulsanti «Carica su FatturaPA» e «Invia a SDI» (e qualsiasi CTA `send-to-sdi` / `retry-send`) su fattura e nota di credito.
2. **Tenere** genera XML, download XML/PDF, dettaglio esito SdI.
3. Badge/timeline dettaglio: `GET /api/v1/fiscal_documents/{id}/sdi-status` (`sdi_status` + `notifications[]`).
4. Lista: usare `fatturapa_status` (`uploaded|sent|error|null`). Overlay BE:
   - `sdi_status` RC/MC/NE/DT → `sent`
   - `sdi_status=scartata` (NS) → `error` + `fatturapa_error_message` «Scartata da SDI»
   - XML pronto, nessuna notifica → spesso `null` (normale)
5. Dopo NS: CTA **«Correggi e rigenera XML»** (non «Reinvia a SDI»):
   - `PATCH /api/v1/fiscal_documents/{id}` (stesso numero/data; se c’è XML il BE lo azzera e torna `pending`)
   - poi `POST .../generate-xml` (nuovo progressivo)
6. Opzionale: `POST /api/v1/fiscal_documents/{id}/reset-xml` — elimina solo l’XML, `status=pending`, conserva `progressivo_invio`. **400** se lo SdI ha già evaso (RC/MC/NE/DT).
7. `PATCH` fattura **consentito** se `sdi_status` è null o `scartata`. **409** se `consegnata|accettata|rifiutata|decorrenza_termini|mancata_consegna`.

---

## Fuori scope

- Riattivare invio API
- Mail di cortesia
- Ciclo passivo POOL / purchase-invoices
