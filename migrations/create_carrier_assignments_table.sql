-- Migration: Create carrier_assignments table
-- Description: Creates the carrier_assignments table for automatic carrier assignment rules

CREATE TABLE IF NOT EXISTS carrier_assignments (
    id_carrier_assignment INT AUTO_INCREMENT PRIMARY KEY,
    id_carrier_api INT NOT NULL,
    postal_codes VARCHAR(1000) NULL COMMENT 'Comma-separated list of postal codes',
    countries VARCHAR(1000) NULL COMMENT 'Comma-separated list of country IDs',
    origin_carriers VARCHAR(1000) NULL COMMENT 'Comma-separated list of origin carrier IDs',
    min_weight FLOAT NULL COMMENT 'Minimum weight for assignment',
    max_weight FLOAT NULL COMMENT 'Maximum weight for assignment',
    
    -- Foreign key constraint
    FOREIGN KEY (id_carrier_api) REFERENCES carriers_api(id_carrier_api) ON DELETE CASCADE,
    
    -- Indexes for performance
    INDEX idx_carrier_assignments_carrier_api (id_carrier_api),
    INDEX idx_carrier_assignments_weight (min_weight, max_weight),
    INDEX idx_carrier_assignments_postal_codes (postal_codes(100)),
    INDEX idx_carrier_assignments_countries (countries(100)),
    INDEX idx_carrier_assignments_origin_carriers (origin_carriers(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add some example data
INSERT INTO carrier_assignments (id_carrier_api, postal_codes, countries, min_weight, max_weight) VALUES
(1, '20100,20121,20122,20123,20124,20125,20126,20127,20128,20129,20131,20132,20133,20134,20135,20136,20137,20138,20139,20141,20142,20143,20144,20145,20146,20147,20148,20149,20151,20152,20153,20154,20155,20156,20157,20158,20159,20161,20162,20163,20164,20165,20166,20167,20168,20169,20171,20172,20173,20174,20175,20176,20177,20178,20179,20181,20182,20183,20184,20185,20186,20187,20188,20189,20191,20192,20193,20194,20195,20196,20197,20198,20199', '1', 0.0, 5.0),
(2, '00100,00118,00119,00120,00121,00122,00123,00124,00125,00126,00127,00128,00129,00131,00132,00133,00134,00135,00136,00137,00138,00139,00141,00142,00143,00144,00145,00146,00147,00148,00149,00151,00152,00153,00154,00155,00156,00157,00158,00159,00161,00162,00163,00164,00165,00166,00167,00168,00169,00171,00172,00173,00174,00175,00176,00177,00178,00179,00181,00182,00183,00184,00185,00186,00187,00188,00189,00191,00192,00193,00194,00195,00196,00197,00198,00199', '1', 5.1, 30.0),
(1, NULL, '1', 30.1, 999.0);

-- Add comments to the table
ALTER TABLE carrier_assignments COMMENT = 'Automatic carrier assignment rules based on postal codes, countries, origin carriers, and weight ranges';
