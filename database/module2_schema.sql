DROP TABLE IF EXISTS repayment_schedule CASCADE;
DROP TABLE IF EXISTS financial_calculations CASCADE;
DROP TABLE IF EXISTS scheme_rules CASCADE;

-- Table to hold NBCFDC scheme rules dynamically so they are not hardcoded in business logic
CREATE TABLE scheme_rules (
    scheme_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code VARCHAR(50) NOT NULL UNIQUE,
    scheme_name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL, -- e.g., 'Term Loan', 'Micro Finance'
    min_project_cost NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    max_project_cost NUMERIC(14,2) NOT NULL,
    loan_percentage NUMERIC(5,2) NOT NULL, -- e.g., 95.00 for 95%
    max_loan_amount NUMERIC(14,2) NOT NULL,
    annual_interest_rate NUMERIC(6,4) NOT NULL,
    tenure_months INTEGER NOT NULL,
    moratorium_months INTEGER NOT NULL DEFAULT 0,
    repayment_frequency VARCHAR(20) NOT NULL DEFAULT 'monthly',
    moratorium_interest_policy VARCHAR(50) NOT NULL DEFAULT 'paid_separately',
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table to hold calculation snapshots from Module 2
CREATE TABLE financial_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255), -- Stores Firebase UID if logged in, else null
    location_id VARCHAR(255), -- village_lgd_code
    scheme_id UUID NOT NULL REFERENCES scheme_rules(scheme_id),
    available_margin NUMERIC(14,2) NOT NULL,
    raw_project_cost NUMERIC(14,2) NOT NULL,
    project_cost NUMERIC(14,2) NOT NULL,
    theoretical_loan NUMERIC(14,2) NOT NULL,
    eligible_loan NUMERIC(14,2) NOT NULL,
    required_margin NUMERIC(14,2) NOT NULL,
    funding_gap NUMERIC(14,2) NOT NULL,
    annual_interest_rate NUMERIC(6,4) NOT NULL,
    tenure_months INTEGER NOT NULL,
    moratorium_months INTEGER NOT NULL,
    moratorium_interest_mode VARCHAR(50) NOT NULL,
    monthly_emi NUMERIC(14,2),
    quarterly_payment NUMERIC(14,2),
    rules_version INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Repayment schedule cache (quarterly/monthly)
CREATE TABLE repayment_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id UUID NOT NULL REFERENCES financial_calculations(id) ON DELETE CASCADE,
    period_number INTEGER NOT NULL,
    period_type VARCHAR(20) NOT NULL, -- 'month' or 'quarter'
    opening_balance NUMERIC(14,2) NOT NULL,
    payment NUMERIC(14,2) NOT NULL,
    principal_component NUMERIC(14,2) NOT NULL,
    interest_component NUMERIC(14,2) NOT NULL,
    closing_balance NUMERIC(14,2) NOT NULL
);
