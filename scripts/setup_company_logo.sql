-- Script per configurare il logo aziendale in app_configurations

-- Inserisci/Aggiorna il logo aziendale
INSERT INTO app_configurations (category, name, value, description, date_add, date_upd) 
VALUES (
    'company_info', 
    'company_logo', 
    'media/logos/logo_elettronew.png', 
    'Path al logo aziendale per documenti fiscali (fatture, DDT, ecc.)',
    NOW(),
    NOW()
)
ON DUPLICATE KEY UPDATE 
    value = 'media/logos/logo_elettronew.png',
    description = 'Path al logo aziendale per documenti fiscali (fatture, DDT, ecc.)',
    date_upd = NOW();

-- Verifica configurazione
SELECT * FROM app_configurations WHERE category = 'company_info' AND name = 'company_logo';

-- NOTA: 
-- 1. Carica il tuo logo in: media/logos/logo_elettronew.png
-- 2. Formati supportati: PNG, JPG, JPEG
-- 3. Dimensioni consigliate: max 200x80 px per una buona resa nel PDF
-- 4. Il path è relativo alla root del progetto


