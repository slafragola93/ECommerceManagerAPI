# Prompt FE — Email gestionale (Spediti + fatture / ricevute / NC)

Copia **tutto da qui alla fine del file** in una chat sul **repo Angular del gestionale**. Il BE può essere ancora in sviluppo: valuta UX e schermate; gli endpoint sotto sono il **contratto target** (allineare i path quando lo Swagger sarà live).

**Stato BE:** implementato. Endpoint in Swagger (`Email Templates`, `send-email` su fiscal_documents e ricevute). SMTP e testi non sono in Angular: il FE è editor + pulsanti di invio. Guida: `docs/EMAIL_DOCUMENTI_E_SPEDITI.md`.

---

## Task (cosa valutare e poi implementare)

Il gestionale deve poter:

1. **Configurare SMTP** con le chiavi già previste in Impostazioni (`app_configurations` categoria `email_settings`).
2. **Creare e modificare template email** (editor, più lingue) salvati sul BE.
3. **Inviare** dal gestionale solo:
   - in automatico quando un ordine passa a **Spediti** (`id_order_state = 3`) — nessun pulsante obbligatorio; l’operatore cambia lo stato come oggi;
   - in modo esplicito **fattura**, **ricevuta**, **nota di credito** (pulsante “Invia al cliente” + icona `mail_status` già in stato rapido).

**PrestaShop** continua a mandare tutte le altre mail (conferma ordine, altri stati, tracking, ecc.). **Non** aggiungere UI per mail su altri stati ordine o su stati spedizione.

Tu (FE) decidi layout, editor (TipTap/Quill/textarea), tab lingue, dove mettere Impostazioni vs azioni in lista/dettaglio documento. Il BE non impone il componente, solo i campi e i purpose.

---

## Fuori scope FE

- Hook o schermate “invia mail” su stati ordine ≠ Spediti.
- Mail su cambio stato spedizione.
- Comunicazioni libere / newsletter.
- Fatture di acquisto.
- Invio automatico alla **creazione** del documento (solo pulsante).
- Testi hardcoded in `i18n` Angular per il corpo della mail cliente (i testi vivono nel BE).

---

## Autenticazione

`Authorization: Bearer <JWT>`

| Area | Permesso atteso |
|------|-----------------|
| CRUD template, preview, send-test, SMTP via `app_configurations` | `settings` read/create/update |
| Invia fattura / NC | stesso modulo fatture (`fiscal_documents` update o analogo già usato per azioni documento) |
| Invia ricevuta | stesso modulo ricevute |

Se i nomi permesso BE differiscono, allineare a Swagger.

---

## 1) SMTP — già quasi pronto

`GET/PUT` su `/api/v1/app_configurations/` e `GET /api/v1/app_configurations/by-category/email_settings`.

Chiavi (value stringa):

| name | Uso UI |
|------|--------|
| sender_name | Nome mittente |
| sender_email | From |
| password | Password (campo secret) |
| ccn | BCC |
| smtp_server | Host |
| smtp_port | Porta |
| security | TLS / SSL / none (come verrà documentato BE) |
| enabled | Kill switch globale (`true`/`false`) — **nuova**, seed BE |
| default_locale | Fallback lingua (`en` consigliato) — **nuova** |

Se `enabled` non è true o mancano host/from, gli invii BE falliscono: in UI disabilitare “Invia” e mostrare hint “configura SMTP”.

---

## 2) Editor template — schermata Impostazioni

Contratto live (Swagger `Email Templates`):

- Lista: `GET /api/v1/email-templates/` → `{ "templates": [...], "total": n }` (non è un array nudo)
- Create: `POST /api/v1/email-templates/` → 201 oggetto template. `code` è **unico**: se esiste già → 400, usare PUT
- Dettaglio / update / delete: `GET|PUT|DELETE /api/v1/email-templates/{id}`
- `PUT /api/v1/email-templates/{id}/translations/{locale}` — `locale` solo nel path (`it` \| `en` \| `fr` \| `de` \| `es`). Body: `{ subject, body_html, body_text? }` — **non** serve `locale` nel JSON
- `GET /api/v1/email-templates/variables?purpose=`
- `POST /api/v1/email-templates/{id}/preview` — body: `locale` + `context` opzionale. Traduzioni **non** obbligatorie al save: senza testi → 200 con subject/body vuoti. Opzionale: `subject`/`body_html` della bozza editor
- `POST /api/v1/email-templates/{id}/send-test` — body: `to`, `locale`, stessi campi bozza opzionali
- Testi lingua: `PUT /{id}` accetta anche `locale` + `subject` + `body_html` nello stesso body del template (così il save della schermata unica li persiste). In GET tornano sia in `translations[]` sia in cima (`subject`, `body_html`, `locale`). Alternative: `translations[]` / mappa `{ it: {...} }` oppure `PUT /{id}/translations/{locale}`

ID da usare nei path: `template.id` **oppure** `template.id_email_template` (stesso valore). Non interpolare `undefined`.

### Modello mentale

Un **template** = un tipo di mail (`purpose` + `code` stabile + nome visibile + `is_default` + `is_active`).

Il **testo** non sta sul template: sta sulle **traduzioni** (una per lingua): `subject`, `body_html`, `body_text` opzionale.

`purpose` ammessi (solo questi in v1):

| purpose | Quando il BE lo usa |
|---------|---------------------|
| `order_shipped` | Automatico su passaggio a Spediti |
| `invoice` | Pulsante invia fattura |
| `receipt` | Pulsante invia ricevuta |
| `credit_note` | Pulsante invia nota di credito |

Serve **almeno un template default** per `order_shipped` se volete che lo stato 3 mandi mail (altrimenti il plugin non ha nulla da spedire). Per i documenti: default per purpose oppure select in modale invio.

### UX suggerita (valutate voi)

- Lista template: nome, purpose, default, lingue compilate, attivo.
- Nuovo / modifica: purpose, code (immutabile dopo create se il BE lo vincola), nome, default.
- Tab lingue: oggetto + **editor rich-text** che salva HTML in `body_html`; chip placeholder da `GET .../variables` (inserire `{{ firstname }}` ecc. nel cursore).
- Anteprima (chiama BE, non render solo FE).
- Invio di prova a un indirizzo.

Lingua di invio reale: `customers.id_lang` → ISO BE; se manca la traduzione, `default_locale`. In editor mostrare quali locale mancano.

---

## 3) Ordine → Spediti (nessuna nuova azione)

Il cambio stato ordine **già esiste**. Non serve un bottone “Invia mail spedizione”.

Valutare solo:

- Se SMTP/template `order_shipped` non sono pronti, il BE non manda (log). Eventuale toast non è richiesto in v1 (l’evento è async/plugin).
- Non mostrare “mail ordine” su altri stati.

`id_order_state` **Spediti = 3** (seed BE). Non hardcodare il nome se avete già l’id dallo store stati.

---

## 4) Fattura / NC / ricevuta — Invia al cliente

Icona **mail** dello stato rapido (contratto già noto):

`mail_status`: `null` \| `pending` \| `sent` \| `error`  
`mail_error_message`: tooltip se `error`

Oggi è quasi sempre `null`. Dopo il BE: dopo `POST send-email` aggiornare lista/dettaglio.

Contratto target:

- `POST /api/v1/fiscal_documents/{id}/send-email` — body opzionale `{ "id_email_template": number }`. Solo `document_type` `invoice` o `credit_note` (non `return`).
- `POST /api/v1/ricevute/{id}/send-email` — analogo.

PDF allegato lato BE. FE: conferma (destinatario = email cliente), eventuale select template, loading, errore da `mail_error_message`.

---

## 5) Placeholder (chip)

`GET /api/v1/email-templates/variables?purpose=invoice` (ecc.)

Attesi (orientativi):

- `order_shipped`: `firstname`, `lastname`, `reference`, `tracking`, `carrier_name`
- `invoice` / `credit_note` / `receipt`: `firstname`, `lastname`, `document_number`, `document_date`, `order_reference`, `total`

Solo chiavi in whitelist: il BE lascia vuoto il resto. Non inventare `{{ tracking }}` sui template fattura.

---

## 6) Criteri di accettazione FE

- [ ] Impostazioni: form SMTP + `enabled` + `default_locale`
- [ ] CRUD template e traduzioni per i 4 purpose
- [ ] Anteprima e send-test
- [ ] Dettaglio/lista fattura e NC: Invia + icona mail aggiornata
- [ ] Ricevute: stesso
- [ ] Nessuna UI mail per altri stati ordine o per shipping
- [ ] Nessun testo corpo mail in i18n Angular (solo label UI)

---

## 7) Domande aperte per la vostra stima

- Editor: un solo HTML o anche “solo testo” visibile?
- Un template default obbligatorio in UI prima di abilitare SMTP?
- Dopo send-email: refresh GET o optimistic `mail_status=pending`?
