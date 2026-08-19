CREATE TABLE customers (
    customer_id VARCHAR PRIMARY KEY,
    signup_date DATE NOT NULL,
    country VARCHAR NOT NULL,
    city VARCHAR NOT NULL,
    age_group VARCHAR NOT NULL,
    device_type VARCHAR NOT NULL,
    acquisition_channel VARCHAR NOT NULL,
    customer_segment VARCHAR NOT NULL
);

CREATE TABLE campaigns (
    campaign_id VARCHAR PRIMARY KEY,
    campaign_name VARCHAR NOT NULL,
    platform VARCHAR NOT NULL,
    channel VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    budget DOUBLE NOT NULL,
    spend DOUBLE NOT NULL,
    impressions BIGINT NOT NULL,
    clicks BIGINT NOT NULL,
    conversions BIGINT NOT NULL,
    revenue DOUBLE NOT NULL
);

CREATE TABLE sessions (
    session_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL REFERENCES customers(customer_id),
    timestamp TIMESTAMP NOT NULL,
    device VARCHAR NOT NULL,
    country VARCHAR NOT NULL,
    traffic_source VARCHAR NOT NULL,
    campaign_id VARCHAR,
    landing_page VARCHAR NOT NULL,
    session_duration_seconds INTEGER NOT NULL,
    pages_viewed INTEGER NOT NULL
);

CREATE TABLE conversions (
    conversion_id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES sessions(session_id),
    customer_id VARCHAR NOT NULL REFERENCES customers(customer_id),
    timestamp TIMESTAMP NOT NULL,
    product_id VARCHAR NOT NULL,
    revenue DOUBLE NOT NULL,
    discount DOUBLE NOT NULL,
    conversion_type VARCHAR NOT NULL
);

CREATE TABLE funnel_events (
    customer_id VARCHAR NOT NULL REFERENCES customers(customer_id),
    session_id VARCHAR NOT NULL REFERENCES sessions(session_id),
    timestamp TIMESTAMP NOT NULL,
    event_name VARCHAR NOT NULL
);

CREATE TABLE daily_campaign_metrics (
    date DATE NOT NULL,
    campaign_id VARCHAR NOT NULL REFERENCES campaigns(campaign_id),
    impressions BIGINT NOT NULL,
    clicks BIGINT NOT NULL,
    spend DOUBLE NOT NULL,
    conversions BIGINT NOT NULL,
    revenue DOUBLE NOT NULL,
    PRIMARY KEY (date, campaign_id)
);

CREATE TABLE app_reviews (
    review_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    rating INTEGER NOT NULL,
    review_text VARCHAR NOT NULL,
    app_version VARCHAR NOT NULL,
    device VARCHAR NOT NULL,
    country VARCHAR NOT NULL
);

CREATE TABLE experiments (
    experiment_id VARCHAR NOT NULL,
    experiment_name VARCHAR NOT NULL,
    variant VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL REFERENCES customers(customer_id),
    exposure_date DATE NOT NULL,
    conversion INTEGER NOT NULL,
    revenue DOUBLE NOT NULL
);

CREATE TABLE marketing_incidents (
    incident_id VARCHAR PRIMARY KEY,
    incident_date DATE NOT NULL,
    title VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    affected_metric VARCHAR NOT NULL,
    affected_channel VARCHAR NOT NULL,
    root_cause VARCHAR NOT NULL,
    resolution VARCHAR NOT NULL,
    impact VARCHAR NOT NULL
);

CREATE TABLE metric_definitions (
    metric_name VARCHAR PRIMARY KEY,
    definition VARCHAR NOT NULL,
    formula VARCHAR NOT NULL,
    required_columns VARCHAR NOT NULL,
    allowed_dimensions VARCHAR NOT NULL,
    business_context VARCHAR NOT NULL,
    owner VARCHAR NOT NULL
);

CREATE TABLE anomaly_ground_truth (
    scenario_id VARCHAR PRIMARY KEY,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    affected_metric VARCHAR NOT NULL,
    affected_dimension VARCHAR NOT NULL,
    expected_direction VARCHAR NOT NULL,
    root_cause VARCHAR NOT NULL,
    severity VARCHAR NOT NULL
);

CREATE VIEW session_facts AS
SELECT
    s.*,
    c.conversion_id,
    c.product_id,
    COALESCE(c.revenue, 0) AS revenue,
    COALESCE(c.discount, 0) AS discount,
    CASE WHEN c.conversion_id IS NULL THEN 0 ELSE 1 END AS converted
FROM sessions s
LEFT JOIN conversions c USING (session_id);
