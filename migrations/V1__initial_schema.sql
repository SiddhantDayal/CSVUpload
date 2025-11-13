-- V1__initial_schema.sql
-- SQL commands for initial database schema setup

-- Create Product Table
CREATE TABLE IF NOT EXISTS product (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(200),
    description TEXT,
    active BOOLEAN DEFAULT TRUE
);

-- Create a functional index for case-insensitive SKU lookup (for performance with func.upper(Product.sku))
-- Note: PostgreSQL's 'upper' function is used here. For other databases, syntax might vary.
CREATE INDEX IF NOT EXISTS idx_product_sku_upper ON product (upper(sku));

-- Create Webhook Table
CREATE TABLE IF NOT EXISTS webhook (
    id SERIAL PRIMARY KEY,
    url VARCHAR(500) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMP WITHOUT TIME ZONE,
    last_status_code INTEGER,
    last_response_time REAL
);

-- Create an index for event_type and enabled for quick webhook lookup
CREATE INDEX IF NOT EXISTS idx_webhook_event_type_enabled ON webhook (event_type, enabled);
