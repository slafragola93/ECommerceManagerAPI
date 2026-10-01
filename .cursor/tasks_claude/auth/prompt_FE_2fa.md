# Prompt FE — Autenticazione a due fattori (2FA / MFA)

Copia **tutto da qui alla fine del file** in una chat sul **repo Angular del gestionale**.

**Stato BE:** implementato. Contratto in Swagger sotto tag `Authentication` e reset admin sotto `User`. Riferimento BE: `docs/AUTH_CHANGES.md` (sezione 2FA).

---

## Task (cosa implementare)

Il gestionale deve supportare un **2FA opzionale** per utente, già gestito dal BE:

1. **Login a due step** quando l’utente ha il 2FA attivo (TOTP app authenticator **oppure** OTP via email).
2. **Attivazione / disattivazione** del 2FA dall’area profilo (o Impostazioni account) dell’utente loggato.
3. **Reset 2FA da admin** su un utente (recupero se perde l’authenticator) — niente backup code lato BE.

Il BE non genera immagini QR: per TOTP restituisce `otpauth_uri` (+ segreto in chiaro una sola volta). Il FE disegna il QR (es. libreria QR) e/o mostra il segreto per inserimento manuale.

Tu (FE) decidi layout, dove mettere le schermate (login step 2, profilo “Sicurezza”, azione admin in lista utenti). Il BE impone solo i campi e i flussi sotto.

---

## Fuori scope FE

- Backup / recovery codes (non esistono sul BE).
- 2FA obbligatorio per ruolo (oggi è opzionale per utente).
- Cambiare durata token, form login username/password, refresh/logout (già esistenti).
- Soft delete utenti o altre feature auth non legate al MFA.

---

## Autenticazione

| Area | Auth |
|------|------|
| Login, MFA verify, MFA resend | **Nessun** Bearer |
| Status / setup / confirm / disable 2FA | `Authorization: Bearer <access_token>` |
| Reset 2FA admin | Bearer + permesso `users` **update** |

Login e verify usano ancora `application/x-www-form-urlencoded` solo per `POST /login` (come oggi). Tutti gli altri endpoint MFA/2FA sono JSON.

---

## 1) Login — contratto aggiornato

`POST /api/v1/auth/login`  
Content-Type: `application/x-www-form-urlencoded`  
Body: `username`, `password` (come oggi).

### Caso A — senza 2FA (`mfa_method = none`)

Risposta **200** (campi come oggi + flag):

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer",
  "current_user": "username",
  "expires_at": "2026-10-01T12:30:00",
  "mfa_required": false
}
```

**FE:** se `mfa_required === false` (o assente), salva i token e procedi come oggi. Ignorare campi extra non rompe i client vecchi, ma conviene tipizzare `mfa_required`.

### Caso B — con 2FA attivo

Risposta **200** **senza** access/refresh:

```json
{
  "mfa_required": true,
  "mfa_token": "<opaco>",
  "mfa_method": "totp",
  "expires_at": "2026-10-01T12:05:00"
}
```

`mfa_method` è `"totp"` oppure `"email"`.  
`expires_at`: sessione MFA valida **5 minuti**.

**FE:**
1. Non navigare nella home.
2. Mostra schermata “Inserisci codice di verifica”.
3. Tieni in memoria (o sessionStorage) `mfa_token` + `mfa_method` + scadenza.
4. Se `mfa_method === "email"`: messaggio “codice inviato all’email dell’account” + pulsante **Reinvia codice**.
5. Se `totp`: messaggio “apri Google Authenticator / app TOTP”.

### Verify

`POST /api/v1/auth/mfa/verify`

```json
{ "mfa_token": "...", "code": "123456" }
```

`code`: 6–8 caratteri.

**200:** stesso payload del login completo (`access_token`, `refresh_token`, …, `mfa_required: false`).  
**401:** messaggio generico `"Codice non valido o sessione scaduta"` (anche dopo 5 tentativi falliti la sessione è bruciata: ripartire dal login).

### Resend (solo email)

`POST /api/v1/auth/mfa/resend`

```json
{ "mfa_token": "..." }
```

**200:** nuovo `mfa_token` + `expires_at` (sostituisci quello in memoria).  
**429:** cooldown **60 secondi** — mostra countdown.  
**401:** token scaduto/non valido → torna al login.

---

## 2) Flusso UI login (suggerito)

```
[Username + Password] 
    → mfa_required false → salva token → app
    → mfa_required true  → [Codice OTP]
                              → verify ok → salva token → app
                              → verify fail → errore, ritenta (max 5, poi riloggarsi)
                              → (email) resend con cooldown 60s
                              → scaduto → messaggio + torna a password
```

Non chiamare `refresh` / API protette finché non hai l’`access_token` post-verify.

---

## 3) Setup 2FA (utente già loggato)

Schermata **Sicurezza / 2FA** (profilo o impostazioni account).

### Stato

`GET /api/v1/auth/2fa/status` → Bearer

```json
{ "mfa_method": "none", "totp_enabled": false }
```

Valori `mfa_method`: `"none"` | `"totp"` | `"email"`.  
Se `none`: mostra scelta metodo + CTA “Attiva”.  
Se attivo: mostra metodo corrente + CTA “Disattiva”.

### Avvio setup

`POST /api/v1/auth/2fa/setup` → Bearer

```json
{ "method": "totp" }
```
oppure `{ "method": "email" }`

**409** se 2FA già attivo (prima disattivare).

**TOTP — 200:**

```json
{
  "method": "totp",
  "otpauth_uri": "otpauth://totp/...",
  "totp_secret": "BASE32...",
  "message": "..."
}
```

**FE TOTP:**
1. Genera QR da `otpauth_uri` (libreria FE).
2. Mostra anche `totp_secret` per copia/inserimento manuale (una sola volta: non ripresentarlo dopo).
3. Input codice a 6 cifre → confirm.

**Email — 200:**

```json
{
  "method": "email",
  "message": "Codice inviato all'email dell'utente. Conferma con POST /2fa/confirm"
}
```

**FE email:** messaggio “controlla la tua email” + input codice. Se SMTP non configurato → **400** chiaro dal BE.

### Confirm (attiva davvero il 2FA)

`POST /api/v1/auth/2fa/confirm` → Bearer

```json
{ "code": "123456" }
```

**200:** `{ "message": "...", "mfa_method": "totp"|"email" }`  
Dal login successivo servirà lo step MFA.

**Importante:** dopo `setup` ma **prima** di `confirm`, il login **non** chiede ancora il 2FA (`mfa_method` resta `none`). Setup abbandonato non blocca l’accesso.

### Disable

`POST /api/v1/auth/2fa/disable` → Bearer

```json
{ "password": "passwordAttuale", "code": "123456" }
```

- **TOTP:** password + codice authenticator.
- **Email:** se non c’è un OTP fresco, il BE può rispondere **400** inviando il codice via email; ripeti la stessa richiesta con password + codice ricevuto.

---

## 4) Reset 2FA da admin

In gestione utenti (dettaglio / menu azioni), solo se l’admin ha permesso `users.update`:

`POST /api/v1/users/{id_user}/2fa/reset` → Bearer  

Body: nessuno.

**200:** `{ "message": "2FA resettato", "id_user": ..., "mfa_method": "none" }`

**FE:** conferma dialog (“L’utente dovrà riattivare il 2FA al prossimo accesso / dalle impostazioni”). Nessun codice richiesto.

---

## 5) Tipizzazione / store (suggerito)

- Estendere il modello login: union  
  `LoginSuccess | MfaChallenge` discriminata da `mfa_required`.
- Non salvare `mfa_token` nel localStorage a lungo termine: solo finché dura lo step 2 (max 5 min).
- Dopo verify: stesso flusso di persistenza token già usato oggi (`access_token`, `refresh_token`, `expires_at`).
- Opzionale: in NgRx/auth store, flag `mfaPending` + `mfaMethod`.

---

## 6) Checklist accettazione FE

- [ ] Login senza 2FA invariato (utente `mfa_method=none`).
- [ ] Login con TOTP → schermata codice → verify → entra in app.
- [ ] Login con email → messaggio invio + verify; resend con cooldown 60s.
- [ ] Codice errato: messaggio errore; dopo 5 errori si deve rifare il login.
- [ ] Sessione MFA scaduta (5 min): messaggio + ritorno a username/password.
- [ ] Setup TOTP: QR da `otpauth_uri` + segreto manuale + confirm.
- [ ] Setup email: OTP + confirm.
- [ ] Disable con password + codice.
- [ ] Admin: reset 2FA su utente (permesso `users` update).
- [ ] Nessuna chiamata API autenticata tra challenge MFA e verify riuscito.

---

## Riferimenti BE rapidi

| Metodo | Path |
|--------|------|
| POST | `/api/v1/auth/login` |
| POST | `/api/v1/auth/mfa/verify` |
| POST | `/api/v1/auth/mfa/resend` |
| GET | `/api/v1/auth/2fa/status` |
| POST | `/api/v1/auth/2fa/setup` |
| POST | `/api/v1/auth/2fa/confirm` |
| POST | `/api/v1/auth/2fa/disable` |
| POST | `/api/v1/users/{id}/2fa/reset` |

Issuer TOTP mostrato in app authenticator: **Elettronew**.
