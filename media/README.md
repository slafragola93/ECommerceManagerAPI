# Directory Media

Questa directory contiene i file multimediali caricati dall'applicazione.

## Struttura

- `logos/` - Loghi aziendali (es. logo per fatture/documenti)
- `uploads/` - Altri file caricati dagli utenti

## Configurazione Logo Aziendale

Per configurare il logo aziendale per le fatture:

1. Carica il file logo (PNG, JPG) in `media/logos/`
2. Aggiungi/aggiorna in `app_configurations`:
   - **category**: `company_info`
   - **name**: `company_logo`
   - **value**: `media/logos/nome_file.png` (path relativo dalla root del progetto)

### Esempio SQL:

```sql
INSERT INTO app_configurations (category, name, value, description) 
VALUES ('company_info', 'company_logo', 'media/logos/logo_elettronew.png', 'Logo aziendale per documenti fiscali');
```

## Note

- I file in questa directory NON dovrebbero essere committati in git (aggiunti a .gitignore)
- Assicurati che la directory abbia i permessi di scrittura corretti
- Formati supportati per loghi: PNG, JPG, JPEG
- Dimensione consigliata logo: max 200x80 px


