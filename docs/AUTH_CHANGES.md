# Modifiche Autenticazione — Elettronew
> Migration applicata il 23/04/2026
> Revision ID: `0a615ed0ec5f`

---

## Obiettivo

Implementare un sistema di autenticazione completo con:
- JWT a breve scadenza + Refresh Token per sessione
- 2FA opzionale (TOTP via Google Authenticator o OTP via Email)
- Permessi granulari per modulo — ogni utente ha una matrice personalizzata
- Ruoli come etichetta organizzativa con permessi di default ereditabili
- Override personali per ogni utente sopra i permessi del ruolo

---

## Tabelle modificate

### `users`
| Colonna | Tipo | Note |
|---------|------|------|
| `totp_secret` | VARCHAR(255) NULL | Chiave segreta TOTP cifrata a riposo |
| `totp_enabled` | BOOLEAN NOT NULL DEFAULT FALSE | Il 2FA è attivo per questo utente |
| `mfa_method` | ENUM('totp','email','none') DEFAULT 'none' | Metodo 2FA scelto dall'utente |
| `deleted_at` | DATETIME NULL | Soft delete — NULL = utente attivo |

### `roles`
| Colonna | Modifica | Note |
|---------|----------|------|
| `name` | VARCHAR(15) → VARCHAR(50) | Nomi ruolo più lunghi |
| `permissions` | **RIMOSSA** | Sostituita da permission_type |
| `description` | AGGIUNTA VARCHAR(255) NULL | Descrizione del ruolo |
| `permission_type` | AGGIUNTA ENUM('full_crud','custom') | full_crud = accesso totale, custom = matrice |
| `is_system` | AGGIUNTA BOOLEAN DEFAULT FALSE | TRUE = ruolo non eliminabile (es. ADMIN) |

---

## Tabelle create

### `app_modules`
Catalogo dei moduli del gestionale su cui applicare i permessi.

| Colonna | Tipo | Note |
|---------|------|------|
| `id_module` | INT PK | |
| `name` | VARCHAR(100) UNIQUE | Identificatore tecnico es: 'orders' |
| `label` | VARCHAR(100) | Nome UI es: 'Ordini' |
| `sort_order` | INT DEFAULT 0 | Ordine nella matrice UI |
| `is_active` | BOOLEAN DEFAULT TRUE | Modulo visibile/nascosto |

**Da popolare con seed data** (vedi sezione sotto)

---

### `user_module_permissions`
La matrice permessi. Una riga = utente o ruolo su un modulo.

| Colonna | Tipo | Note |
|---------|------|------|
| `id` | INT PK | |
| `id_user` | INT FK → users NULL | NULL se è permesso di ruolo |
| `id_role` | INT FK → roles NULL | NULL se è permesso personale |
| `id_module` | INT FK → app_modules NOT NULL | |
| `can_read` | BOOLEAN DEFAULT FALSE | |
| `can_create` | BOOLEAN DEFAULT FALSE | |
| `can_update` | BOOLEAN DEFAULT FALSE | |
| `can_delete` | BOOLEAN DEFAULT FALSE | |
| `created_by` | INT FK → users NULL | Admin che ha configurato il permesso |
| `updated_at` | DATETIME | |

**Vincoli unicità:**
- `uq_role_module` → (id_role, id_module) unici
- `uq_user_module` → (id_user, id_module) unici

**Logica di lettura:**
```
id_user valorizzato + id_role NULL  → permesso personale dell'utente
id_role valorizzato + id_user NULL  → permesso di default del ruolo
```

---

### `refresh_tokens`
Sessioni per device. Sostituisce il JWT a 30 giorni.

| Colonna | Tipo | Note |
|---------|------|------|
| `id` | INT PK | |
| `id_user` | INT FK → users NOT NULL | |
| `token_hash` | VARCHAR(255) UNIQUE | SHA-256 del token reale |
| `device_info` | VARCHAR(255) NULL | es: "Chrome 124 / Windows 11" |
| `ip_address` | VARCHAR(45) NULL | Copre IPv4 e IPv6 |
| `expires_at` | DATETIME NOT NULL | Scadenza token (7 giorni) |
| `revoked_at` | DATETIME NULL | NULL = valido, data = revocato |
| `created_at` | DATETIME NOT NULL | |

NOTA TIMESTAMP:
Il sistema usa datetime.now() (ora locale italiana) per coerenza con
tutto il resto del progetto (es. tabella orders).
File coinvolti:
- src/services/routers/auth_service.py
- src/routers/auth.py
---

### `mfa_pending_sessions`
Step intermedio del login con 2FA attivo.

| Colonna | Tipo | Note |
|---------|------|------|
| `id` | INT PK | |
| `id_user` | INT FK → users NOT NULL | |
| `token_hash` | VARCHAR(255) UNIQUE | Token temporaneo inviato al client |
| `expires_at` | DATETIME NOT NULL | Scade in 5 minuti |
| `used_at` | DATETIME NULL | NULL = non ancora usato |
| `ip_address` | VARCHAR(45) NULL | |
| `created_at` | DATETIME NOT NULL | |
| `mfa_method` | ENUM('totp','email') NOT NULL | Metodo usato in questa sessione |
| `otp_code_hash` | VARCHAR(255) NULL | SHA-256 del codice email (solo se method=email) |

---

### `auth_logs`
Audit trail completo di tutti gli eventi di autenticazione.

| Colonna | Tipo | Note |
|---------|------|------|
| `id` | INT PK | |
| `id_user` | INT FK → users NULL | NULL per tentativi su utenti inesistenti |
| `event` | VARCHAR(100) NOT NULL | Tipo evento (vedi lista sotto) |
| `ip_address` | VARCHAR(45) NULL | |
| `user_agent` | VARCHAR(255) NULL | Browser e OS |
| `extra_data` | JSON NULL | Dati extra specifici per evento |
| `created_at` | DATETIME NOT NULL | |

**Eventi previsti:**
```
login_success       → login riuscito
login_failed        → password errata o utente inesistente
mfa_success         → codice 2FA verificato
mfa_failed          → codice 2FA sbagliato
logout              → sessione chiusa
token_refreshed     → access token rinnovato
password_changed    → password modificata
mfa_enabled         → 2FA attivato
mfa_disabled        → 2FA disattivato
permission_changed  → permessi modificati da admin
```

---

## Logica permessi — come funziona

```
1. L'utente è ADMIN? (is_system=TRUE sul ruolo)
   → Sì → accesso totale, nessun controllo

2. Esiste un permesso personale?
   WHERE id_user = X AND id_module = Y AND id_role IS NULL
   → Sì → usa i flag can_* di questa riga

3. Esiste un permesso del ruolo?
   WHERE id_role = R AND id_module = Y AND id_user IS NULL
   → Sì → usa i flag can_* di questa riga

4. Nessuna riga trovata → ACCESSO NEGATO
```

---

## Flusso login — come cambia

```
PRIMA:
POST /login → JWT valido 30 giorni con permessi dentro ❌

DOPO (senza 2FA):
POST /login → access_token (30 min) + refresh_token (7 giorni)

DOPO (con 2FA):
POST /login → mfa_token temporaneo (5 min)
POST /auth/mfa/verify → access_token + refresh_token

TOKEN SCADUTO:
POST /auth/refresh → nuovo access_token

LOGOUT:
POST /auth/logout → refresh_token revocato nel DB
```

---

## Seed data da inserire (prossimo step)

Dopo la migration vanno inseriti i dati iniziali:

### Ruoli di sistema
```sql
INSERT INTO roles (name, description, permission_type, is_system)
VALUES
  ('ADMIN', 'Accesso completo a tutti i moduli', 'full_crud', TRUE);
```

### Moduli del gestionale
```sql
INSERT INTO app_modules (name, label, sort_order) VALUES
  ('orders',           'Ordini',           1),
  ('quotes',           'Preventivi',        2),
  ('fiscal_documents', 'Fatture',           3),
  ('products',         'Prodotti',          4),
  ('customers',        'Clienti',           5),
  ('shipments',        'Spedizioni',        6),
  ('carriers',         'Corrieri',          7),
  ('ddt',              'DDT',               8),
  ('returns',          'Resi',              9),
  ('payments',         'Pagamenti',        10),
  ('stores',           'Negozi',           11),
  ('platforms',        'Piattaforme',      12),
  ('settings',         'Impostazioni',     13),
  ('users',            'Utenti',           14),
  ('admin',            'Amministrazione',  15);
```

---

## File modelli creati/modificati

```
src/models/user.py                    → aggiornato (totp, mfa, deleted_at, nuove relazioni)
src/models/role.py                    → aggiornato (permission_type, is_system, description)
src/models/app_modules.py             → NUOVO
src/models/user_module_permission.py  → NUOVO
src/models/refresh_token.py           → NUOVO
src/models/mfa_pending_session.py     → NUOVO
src/models/auth_log.py                → NUOVO
src/models/__init__.py                → aggiornato (importa i nuovi modelli)
```

---

## Prossimi step da implementare

```
FASE 2 — Backend logica
  □ PermissionService.check_permission()
  □ Riscrivi create_access_token() → JWT snello 30 min
  □ Riscrivi get_current_user()
  □ require_permission() come FastAPI Depends
  □ POST /auth/refresh → rinnova access token
  □ POST /auth/logout  → revoca refresh token
  □ POST /auth/mfa/verify → verifica codice 2FA
  □ POST /2fa/setup    → genera QR code TOTP
  □ POST /2fa/confirm  → attiva 2FA
  □ Aggiorna /api/v1/init → restituisce module_permissions
  □ GET/PUT /api/v1/users/{id}/permissions
  □ GET/POST/DELETE /api/v1/roles
  □ GET /api/v1/modules
  □ Applica require_permission() su ogni router

FASE 3 — Frontend Angular
  □ Aggiorna store NgRx Permissions
  □ Sidebar dinamica per can_read
  □ Nascondi bottoni per permesso
  □ PermissionGuard aggiornato
```
