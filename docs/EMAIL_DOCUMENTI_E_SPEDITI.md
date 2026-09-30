# Email gestionale: Spediti + fatture / ricevute / NC

Il gestionale invia mail al cliente **solo** in questi casi:

1. L’ordine passa a **Spediti** (`id_order_state = 3`) — plugin `email_notification`.
2. L’operatore preme **Invia al cliente** su fattura, nota di credito o ricevuta.

Tutte le altre mail (conferma ordine, tracking, altri stati) restano a PrestaShop.

## Configurazione SMTP

Categoria `app_configurations.email_settings`:

- `sender_name`, `sender_email`, `password`, `ccn`, `smtp_server`, `smtp_port`, `security`
- `enabled` — `true` per abilitare gli invii
- `default_locale` — fallback lingua (`en`)

`GET /api/v1/app_configurations/by-category/email_settings`

## Template

Tabelle `email_templates` e `email_template_translations`. Purpose: `order_shipped`, `invoice`, `receipt`, `credit_note`.

API: `/api/v1/email-templates/` (CRUD, traduzioni, `variables`, `preview`, `send-test`). Permesso `settings`.

Risposta template: `id_email_template` e `id` (alias). Lista: `{ templates, total }`. `code` unico (POST duplicato → 400).

Le traduzioni **non** sono obbligatorie in create/update del template. Preview senza testi salvati risponde 200 con subject/body vuoti (oppure renderizza `subject`/`body_html` se il FE li manda in bozza). L’invio reale (Spediti / send-email) resta senza mail se manca una traduzione.

`PUT /email-templates/{id}` persiste oggetto/corpo se il FE li manda in cima (`locale`, `subject`, `body_html`) o in `translations`. GET li rimostra in cima e in `translations[]`.

`PUT /email-templates/{id}/translations/{locale}`: `locale` è nel path; body solo `subject`, `body_html`, `body_text` opzionale.

Serve un template **default** attivo per `order_shipped` se la mail su Spediti deve partire. Stesso per i documenti se il FE non passa `id_email_template`.

## Invio documenti

- `POST /api/v1/fiscal_documents/{id}/send-email` — solo `invoice` e `credit_note`; PDF in allegato; aggiorna `mail_status`
- `POST /api/v1/ricevute/{id}/send-email` — analogo

Body opzionale: `{ "id_email_template": 1 }`

## Plugin

`config/event_handlers.yaml`: `email_notification.enabled: true`. Il plugin ignora ogni stato diverso da 3. Kill switch operativo: `email_settings.enabled`.

## Migration

```bash
alembic upgrade head
```

Poi `python scripts/setup_initial.py` (o init configurazioni) per creare le chiavi `enabled` e `default_locale` se mancano.

Prompt FE: `.cursor/tasks_claude/email/prompt_FE_email_spediti_e_documenti.md`
