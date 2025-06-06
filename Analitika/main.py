import pandas as pd
import numpy as np
import re

# --- 1. Загрузка данных ---
fin = pd.read_excel('financial_data_new.xlsx')
prol = pd.read_excel('prolongations_new.xlsx')


# --- 2. Очистка value ---
def clean_value(val):
    """
    Очищает и преобразует значение из столбца 'value' к float.

    Параметры
    ----------
    val : any
        Исходное значение, возможно некорректное (строка, None, float, etc)

    Возвращает
    -------
    float
        Чистое числовое значение (или 0 при ошибке/пустых/словах ноль).
    """
    if pd.isna(val): return 0
    val = str(val).replace(' ', '').replace(' ', '')
    if val.lower() in ('ноль', 'none', '-', 'nan', '0ноль', 'null', ''):
        return 0
    val = re.sub('[^0-9,.-]', '', val).replace(',', '.')
    try: return float(val)
    except: return 0

fin['value'] = fin['value'].apply(clean_value)

# --- 3. Преобразования и номера месяцев ---
fin['id'] = fin['id'].astype(str).str.strip()
prol['id'] = prol['id'].astype(str).str.strip()
fin['month'] = fin['month'].str.capitalize().str.strip()
prol['month'] = prol['month'].str.capitalize().str.strip()
fin['year'] = fin['year'].astype(int)
prol['year'] = prol['year'].astype(int)

month_dict = {'Январь': 1, 'Февраль': 2, 'Март': 3, 'Апрель': 4, 'Май': 5, 'Июнь': 6,
              'Июль': 7, 'Август': 8, 'Сентябрь': 9, 'Октябрь': 10, 'Ноябрь': 11, 'Декабрь': 12}

def month_int(row):
    """
    Преобразует строковое название месяца и год в числовой период вида YYYYMM.

    Параметры
    ----------
    row : pandas.Series
        Строка DataFrame c полями 'year' и 'month'

    Возвращает
    ----------
    int
        Период в формате YYYYMM (например, 202307)
    """
    return row['year'] * 100 + month_dict.get(row['month'], 0)

fin['period'] = fin.apply(month_int, axis=1)
prol['period'] = prol.apply(month_int, axis=1)

periods = fin[['year','month','period']].drop_duplicates().copy()
periods['month_num'] = periods['month'].map(month_dict)
periods = periods.dropna(subset=['month_num']).astype({'year':int, 'month':str, 'period':int, 'month_num':int})
periods = periods.sort_values(['year', 'month_num']).reset_index(drop=True)

# --- 4. Основной расчёт по месяцам ---
# В этом блоке будет рассчитан столбец с основными метриками пролонгаций по месяцам и менеджерам.
# Для каждого месяца (начиная со второго доступного) и для каждого менеджера будут рассчитаны:
#   - База пролонгации K1 (проекты закончились в прошлом месяце, сумма за прошлый месяц)
#   - Сумма пролонгаций K1 (эти же проекты имеют отгрузку на текущий месяц)
#   - K1 = (Сумма пролонгаций K1) / (База K1)
#   - База пролонгации K2 (проекты закончились 2 месяца назад и не пролонгировались в предыдущем месяце)
#   - Сумма пролонгаций K2 (эти проекты получили пролонгацию только сейчас)
#   - K2 = (Сумма пролонгаций K2) / (База K2)
# Для проектов, которые закончились только что или месяц назад, естественно, не получится посчитать K2 (будет np.nan)

results = []
AMs = prol['AM'].unique()  # Получаем список уникальных аккаунт-менеджеров

for i in range(1, len(periods)):
    # Получаем параметры текущего периода (месяца) и двух предыдущих
    year_cur, month_cur, period_cur, month_num_cur = periods.iloc[i]
    year_prev,  _, period_prev,  _ = periods.iloc[i-1]
    if i > 1:
        year_prev2,  _, period_prev2,  _ = periods.iloc[i-2]
    else:
        period_prev2 = None  # Для второго месяца в ряду позапрошлого месяца просто нет (nan)

    for am in AMs:
        # --------K1: коэффициент пролонгации в первый месяц после окончания проекта----------
        # 1. Находим id проектов менеджера am, которые завершились в прошлом месяце
        ids_prev = prol.query("AM == @am and period == @period_prev")['id'].unique()
        # 2. База K1: сумма по этим проектам, реально отгруженным в прошлом месяце
        prev_sum = fin[(fin['id'].isin(ids_prev)) & (fin['period']==period_prev)]['value'].sum()

        # 3. Проверяем, кто из этих проектов имеет пролонгацию в текущем месяце (наличие отгрузки)
        curr_ids = set(fin[(fin['id'].isin(ids_prev)) & (fin['period']==period_cur) & (fin['value'] > 0)]['id'])
        # 4. Сумма пролонгаций K1: общий объем, отгруженный этим проектам в текущем месяце (то есть пролонгировали)
        curr_sum = fin[(fin['id'].isin(curr_ids)) & (fin['period']==period_cur)]['value'].sum()

        # 5. Вычисляем коэффициент K1: отношением суммы пролонгированных к общей базе
        K1 = curr_sum/prev_sum if prev_sum > 0 else np.nan

        # --------K2: коэффициент пролонгации во второй месяц после окончания проекта----------
        # K2 считаем только если есть позапрошлый месяц (начиная с третьего месяца года)
        if period_prev2 is not None:
            # 1. Находим id проектов менеджера am, которые завершились в позапрошлом месяце
            ids_prev2 = prol.query("AM == @am and period == @period_prev2")['id'].unique()
            # 2. Оставляем только те, которые НЕ были пролонгированы в прошлом месяце (нет отгрузки в прошлом месяце)
            not_renewed = set(fin[(fin['id'].isin(ids_prev2)) & (fin['period']==period_prev) & (fin['value']==0)]['id'])

            # 3. База K2: сумма по этим "отложенным" проектам за позапрошлый месяц
            prev2_sum = fin[(fin['id'].isin(not_renewed)) & (fin['period']==period_prev2)]['value'].sum()

            # 4. Сумма пролонгаций K2: какое количество этих проектов всё-таки пролонгировали сейчас
            sum2 = fin[(fin['id'].isin(not_renewed)) & (fin['period']==period_cur) & (fin['value'] > 0)]['value'].sum()

            # 5. Вычисляем коэффициент K2: отношением суммы пролонгированных проектов к базе
            K2 = sum2/prev2_sum if prev2_sum > 0 else np.nan
        else:
            # Если позапрошлого месяца нет (январь, февраль) — K2 посчитать нельзя
            K2 = np.nan
            sum2 = prev2_sum = np.nan

        # Добавляем результаты по данному менеджеру за этот месяц в общий список
        results.append({
            'Менеджер': am,
            'Год': year_cur,
            'Месяц': month_cur,
            'K1, сумма пролонгаций': curr_sum,
            'K1, база': prev_sum,
            'Коэф. пролонгации K1': K1,
            'K2, сумма пролонгаций': sum2,
            'K2, база': prev2_sum,
            'Коэф. пролонгации K2': K2
        })

# Из полученного списка делаем "помесячный" датафрейм с результатами (по каждому менеджеру)
df = pd.DataFrame(results)

# --- 5. Годовые итоги по каждому менеджеру ---
# Здесь считаются такие же суммы и коэффициенты, только уже агрегировано по всему году:
# группируем по Менеджеру и Году, складываем суммы и заново считаем итоговые K1, K2 как отношение сумм.
df_year = df.groupby(['Менеджер', 'Год']).agg({
    'K1, сумма пролонгаций': 'sum',
    'K1, база': 'sum',
    'K2, сумма пролонгаций': 'sum',
    'K2, база': 'sum'
}).reset_index()
df_year['Коэф. пролонгации K1'] = df_year['K1, сумма пролонгаций'] / df_year['K1, база']
df_year['Коэф. пролонгации K2'] = df_year['K2, сумма пролонгаций'] / df_year['K2, база']

def get_top_antitop(sub, value_col, top_n=3):
    """
    Возвращает топ-N и анти-топ-N строки DataFrame по выбранному столбцу.

    Параметры
    ----------
    sub : pandas.DataFrame
        Таблица по какому-либо периоду/группе.
    value_col : str
        Название столбца, по которому сортировать (например 'Коэф. пролонгации K1')
    top_n : int
        Сколько записей считать топом/анти-топом (по умолчанию 3)

    Возвращает
    ----------
    top : pandas.DataFrame
        Топ N с начала (max -> min)
    anti : pandas.DataFrame
        Анти-топ N с конца (min -> max)
    """
    sub = sub.dropna(subset=[value_col])
    top = sub.sort_values(value_col, ascending=False).head(top_n)
    anti = sub.sort_values(value_col, ascending=True).head(top_n)
    return top, anti

# --- 6. Топ3/Антитоп3 по K1 за каждый месяц ---
table_months_K1 = []
for (year, month), sub in df.groupby(['Год', 'Месяц']):
    row = {'Год': year, 'Месяц': month}
    top_k1, low_k1 = get_top_antitop(sub, 'Коэф. пролонгации K1')
    for idx, (_, r) in enumerate(top_k1.iterrows(), 1):
        row[f'Топ{idx}_Менеджер'] = r['Менеджер']
        row[f'Топ{idx}_K1'] = r['Коэф. пролонгации K1']
    for idx, (_, r) in enumerate(low_k1.iterrows(), 1):
        row[f'АнтиТоп{idx}_Менеджер'] = r['Менеджер']
        row[f'АнтиТоп{idx}_K1'] = r['Коэф. пролонгации K1']
    table_months_K1.append(row)
df_top_months_K1 = pd.DataFrame(table_months_K1)

# --- 7. Топ3/Антитоп3 по K2 за каждый месяц ---
table_months_K2 = []
for (year, month), sub in df.groupby(['Год', 'Месяц']):
    row = {'Год': year, 'Месяц': month}
    top_k2, low_k2 = get_top_antitop(sub, 'Коэф. пролонгации K2')
    for idx, (_, r) in enumerate(top_k2.iterrows(), 1):
        row[f'Топ{idx}_Менеджер'] = r['Менеджер']
        row[f'Топ{idx}_K2'] = r['Коэф. пролонгации K2']
    for idx, (_, r) in enumerate(low_k2.iterrows(), 1):
        row[f'АнтиТоп{idx}_Менеджер'] = r['Менеджер']
        row[f'АнтиТоп{idx}_K2'] = r['Коэф. пролонгации K2']
    table_months_K2.append(row)
df_top_months_K2 = pd.DataFrame(table_months_K2)

# --- 8. Топ3/Антитоп3 по K1 за год ---
table_years_K1 = []
for year, sub in df_year.groupby('Год'):
    row = {'Год': year}
    top_k1, low_k1 = get_top_antitop(sub, 'Коэф. пролонгации K1')
    for idx, (_, r) in enumerate(top_k1.iterrows(), 1):
        row[f'Топ{idx}_Менеджер'] = r['Менеджер']
        row[f'Топ{idx}_K1'] = r['Коэф. пролонгации K1']
    for idx, (_, r) in enumerate(low_k1.iterrows(), 1):
        row[f'АнтиТоп{idx}_Менеджер'] = r['Менеджер']
        row[f'АнтиТоп{idx}_K1'] = r['Коэф. пролонгации K1']
    table_years_K1.append(row)
df_top_years_K1 = pd.DataFrame(table_years_K1)

# --- 9. Топ3/Антитоп3 по K2 за год ---
table_years_K2 = []
for year, sub in df_year.groupby('Год'):
    row = {'Год': year}
    top_k2, low_k2 = get_top_antitop(sub, 'Коэф. пролонгации K2')
    for idx, (_, r) in enumerate(top_k2.iterrows(), 1):
        row[f'Топ{idx}_Менеджер'] = r['Менеджер']
        row[f'Топ{idx}_K2'] = r['Коэф. пролонгации K2']
    for idx, (_, r) in enumerate(low_k2.iterrows(), 1):
        row[f'АнтиТоп{idx}_Менеджер'] = r['Менеджер']
        row[f'АнтиТоп{idx}_K2'] = r['Коэф. пролонгации K2']
    table_years_K2.append(row)
df_top_years_K2 = pd.DataFrame(table_years_K2)

# --- 10. Сохраняем в Excel ---
with pd.ExcelWriter('Отчет_по_пролонгациям.xlsx', engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name="По месяцам", index=False)
    df_year.to_excel(writer, sheet_name="За год", index=False)
    df_top_months_K1.to_excel(writer, sheet_name="Топы по месяцам K1", index=False)
    df_top_months_K2.to_excel(writer, sheet_name="Топы по месяцам K2", index=False)
    df_top_years_K1.to_excel(writer, sheet_name="Топы по годам K1", index=False)
    df_top_years_K2.to_excel(writer, sheet_name="Топы по годам K2", index=False)

print("Отчет сохранён как 'Отчет_по_пролонгациям.xlsx'.")