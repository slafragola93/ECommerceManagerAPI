-- Script per inizializzare le configurazioni ecommerce in app_configurations
-- Questo script inserisce base_url e api_key nella categoria 'ecommerce'

-- Inserisci base_url (sostituisci con il tuo URL)
INSERT INTO app_configurations (id_lang, category, name, value, description, is_encrypted, date_add, date_upd)
VALUES (
    0,
    'ecommerce',
    'base_url',
    'https://tuosito.com',  -- CAMBIA QUESTO CON IL TUO URL
    'URL base della piattaforma ecommerce (es. https://tuosito.com)',
    0,
    NOW(),
    NOW()
) ON DUPLICATE KEY UPDATE 
    value = VALUES(value),
    date_upd = NOW();

-- Inserisci api_key (sostituisci con la tua API key)
INSERT INTO app_configurations (id_lang, category, name, value, description, is_encrypted, date_add, date_upd)
VALUES (
    0,
    'ecommerce',
    'api_key',
    'TUA_API_KEY_QUI',  -- CAMBIA QUESTO CON LA TUA API KEY
    'Chiave API della piattaforma ecommerce',
    0,
    NOW(),
    NOW()
) ON DUPLICATE KEY UPDATE 
    value = VALUES(value),
    date_upd = NOW();

-- Verifica che le configurazioni siano state inserite correttamente
SELECT * FROM app_configurations WHERE category = 'ecommerce';

