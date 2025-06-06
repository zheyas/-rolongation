
import pandas as pd
import re

# ---------- PROLONGATIONS ----------
prol = pd.read_csv('prolongations.csv')

def split_month_year(cell):
    m = re.match(r'([А-Яа-я]+)\s+(\d{4})', str(cell).strip())
    return pd.Series([m.group(1), int(m.group(2))]) if m else pd.Series([None, None])

prol[['month', 'year']] = prol['month'].apply(split_month_year)
prol = prol.dropna(subset=['month', 'year'])

prol.to_excel('prolongations_new.xlsx', index=False)
print('Сохранен файл prolongations_new.xlsx')

# ---------- FINANCIAL DATA ----------
fin = pd.read_csv('financial_data.csv')

id_cols = [c for c in fin.columns if not re.match(r'[А-Яа-я]+\s+\d{4}', c)]
month_cols = [c for c in fin.columns if re.match(r'[А-Яа-я]+\s+\d{4}', c)]

fin_long = fin.melt(id_vars=id_cols, value_vars=month_cols, 
                    var_name="month_year", value_name="value") 

fin_long[['month','year']] = fin_long['month_year'].apply(split_month_year)
fin_long = fin_long.drop(['month_year'], axis=1)
fin_long = fin_long.dropna(subset=['month', 'year'])

if len(id_cols) > 1:
    fin_long = fin_long[['id']+id_cols[1:] + ['month','year','value']]
else:
    fin_long = fin_long[['id','month','year','value']]

fin_long.to_excel('financial_data_new.xlsx', index=False)
print('Сохранен файл financial_data_new.xlsx')
