-- Script per eliminare le configurazioni ecommerce/commerce non utilizzate da app_configurations
-- Queste configurazioni non sono utilizzate perché il sistema usa store.base_url e store.api_key

-- Query di verifica: mostra cosa verrà eliminato
SELECT 
    id_app_configuration,
    category,
    name,
    value,
    description,
    date_add
FROM app_configurations 
WHERE category IN ('ecommerce', 'commerce')
ORDER BY category, name;

-- Elimina configurazioni ecommerce/commerce
DELETE FROM app_configurations 
WHERE category IN ('ecommerce', 'commerce');

-- Verifica eliminazione
SELECT COUNT(*) as remaining_count
FROM app_configurations 
WHERE category IN ('ecommerce', 'commerce');
