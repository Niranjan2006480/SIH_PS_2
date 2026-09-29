INSERT INTO scheme_rules (
    scheme_code, scheme_name, category, min_project_cost, max_project_cost, 
    loan_percentage, max_loan_amount, annual_interest_rate, tenure_months, moratorium_months
) VALUES 
-- Micro Finance Scheme (Project cost <= 1.40 Lakh, 90% loan, max 1.25 Lakh, 6.5% interest, 3 years including 3-month moratorium)
(
    'NBCFDC_MICRO_FINANCE', 'NBCFDC Micro Finance Scheme', 'Micro Finance', 0.00, 140000.00,
    90.00, 125000.00, 6.5000, 36, 3
),
-- Term Loan Scheme (Project cost > 1.40 Lakh up to 50 Lakh, 90% loan, max 45 Lakh, 8.0% interest, 7 years including 6-month moratorium)
(
    'NBCFDC_TERM_LOAN', 'NBCFDC Term Loan Scheme', 'Term Loan', 140000.01, 5000000.00,
    90.00, 4500000.00, 8.0000, 84, 6
)
ON CONFLICT (scheme_code) DO UPDATE SET
    scheme_name = EXCLUDED.scheme_name,
    category = EXCLUDED.category,
    min_project_cost = EXCLUDED.min_project_cost,
    max_project_cost = EXCLUDED.max_project_cost,
    loan_percentage = EXCLUDED.loan_percentage,
    max_loan_amount = EXCLUDED.max_loan_amount,
    annual_interest_rate = EXCLUDED.annual_interest_rate,
    tenure_months = EXCLUDED.tenure_months,
    moratorium_months = EXCLUDED.moratorium_months;

