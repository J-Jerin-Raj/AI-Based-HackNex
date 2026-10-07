from helpers.cleaning import parse_currency_amount, clean_status
import pandas as pd

# Load the required tables
customers = pd.read_csv('data/customers.csv', keep_default_na=False)
fx_rates = pd.read_csv('data/fx_rates.csv', keep_default_na=False)
monthly_summary = pd.read_csv('data/monthly_summary.csv', keep_default_na=False)
orders = pd.read_csv('data/orders.csv', keep_default_na=False)
refunds = pd.read_csv('data/refunds.csv', keep_default_na=False)

# Parse amounts in orders.csv
orders['amount'] = orders['amount'].apply(parse_currency_amount)

# Clean status in orders.csv
orders['status'] = orders['status'].apply(clean_status)

# Deduplicate orders by order_id
orders = orders.drop_duplicates(subset=['order_id'])

# Filter completed USD orders
completed_usd_orders = orders[(orders['status'] == 'COMPLETED') & (orders['currency'] == 'USD')]

# Calculate total revenue from completed USD orders
total_revenue = completed_usd_orders['amount'].sum()

# Print the final calculated answer
print(round(total_revenue, 2))