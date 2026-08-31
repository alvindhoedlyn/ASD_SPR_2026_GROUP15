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