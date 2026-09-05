INSERT INTO scheme_rules (
    scheme_code, scheme_name, category, min_project_cost, max_project_cost, 
    loan_percentage, max_loan_amount, annual_interest_rate, tenure_months, moratorium_months
) VALUES 
-- Term Loans
(
    'TERM_SWARNIMA', 'New Swarnima for Women', 'Term Loan', 0.01, 105263.15, -- 95% of 105263 = 100000 loan
    95.00, 100000.00, 5.0000, 84, 6
),
(
    'TERM_SAKSHAM_L1', 'Saksham (Up to 5 Lakh)', 'Term Loan', 0.01, 588235.29, -- 85% of 588235 = 500000
    85.00, 500000.00, 6.0000, 84, 6
),
(
    'TERM_SAKSHAM_L2', 'Saksham (Above 5 to 10 Lakh)', 'Term Loan', 588235.30, 1176470.58, -- 85% of 1176470 = 1000000
    85.00, 1000000.00, 8.0000, 84, 6
),
(
    'TERM_SHILP_L1', 'Shilp Sampada (Up to 5 Lakh)', 'Term Loan', 0.01, 588235.29,
    85.00, 500000.00, 6.0000, 84, 6
),
(
    'TERM_SHILP_L2', 'Shilp Sampada (Above 5 to 10 Lakh)', 'Term Loan', 588235.30, 1176470.58,
    85.00, 1000000.00, 8.0000, 84, 6
),
-- Micro Finance
(
    'MICRO_GENERAL', 'Micro Finance Scheme', 'Micro Finance', 0.01, 55555.55, -- 90% of 55555 = 50000
    90.00, 50000.00, 5.0000, 36, 3
),
(
    'MICRO_MAHILA', 'Mahila Samriddhi Yojana', 'Micro Finance', 0.01, 52631.57, -- 95% of 52631 = 50000
    95.00, 50000.00, 4.0000, 36, 3
),
(
    'MICRO_KRISHI', 'Krishi Sampada', 'Micro Finance', 0.01, 52631.57,
    95.00, 50000.00, 4.0000, 36, 3
)
ON CONFLICT (scheme_code) DO NOTHING;
