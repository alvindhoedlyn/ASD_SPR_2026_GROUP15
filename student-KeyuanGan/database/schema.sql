CREATE TABLE IF NOT EXISTS expenses (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    expense_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS budget_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_budget REAL NOT NULL CHECK (total_budget >= 0),
    min_price REAL NOT NULL CHECK (min_price >= 0),
    max_price REAL NOT NULL CHECK (max_price >= min_price)
);
-- =========================================================
-- Seed data: minimum 10 records per table
-- =========================================================

INSERT OR IGNORE INTO expenses
    (expense_id, category, description, amount, expense_date)
VALUES
    (1, 'Accommodation', 'Hotel booking', 420.00, '2026-09-01'),
    (2, 'Transport', 'Flight ticket', 180.00, '2026-09-01'),
    (3, 'Food', 'Lunch', 35.50, '2026-09-02'),
    (4, 'Transport', 'Train ticket', 22.00, '2026-09-02'),
    (5, 'Entertainment', 'Museum ticket', 28.00, '2026-09-03'),
    (6, 'Food', 'Dinner', 48.00, '2026-09-03'),
    (7, 'Shopping', 'Travel accessories', 65.00, '2026-09-04'),
    (8, 'Transport', 'Airport transfer', 55.00, '2026-09-04'),
    (9, 'Food', 'Breakfast', 21.50, '2026-09-05'),
    (10, 'Entertainment', 'City tour', 84.00, '2026-09-05');


INSERT OR IGNORE INTO budget_settings
    (id, total_budget, min_price, max_price)
VALUES
    (1, 3000.00, 500.00, 1500.00),
    (2, 3200.00, 500.00, 1600.00),
    (3, 3400.00, 600.00, 1700.00),
    (4, 3600.00, 600.00, 1800.00),
    (5, 3800.00, 700.00, 1900.00),
    (6, 4000.00, 700.00, 2000.00),
    (7, 4200.00, 800.00, 2100.00),
    (8, 4500.00, 800.00, 2200.00),
    (9, 4800.00, 900.00, 2400.00),
    (10, 5000.00, 1000.00, 2500.00);