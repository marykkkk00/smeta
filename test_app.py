import streamlit as st
import pandas as pd
import random
from io import BytesIO

# === НАСТРОЙКИ API ===
API_BASE_URL = "https://cs.smetnoedelo.ru/api/"  # пока не используем (демо-цены)
API_TOKEN = "f8jnhskPMwzovgXG5dxtC7VI"

# === Вспомогательные функции ===
def detect_base_by_code(code):
    """Определяем базу и «чистый» код."""
    code = str(code).strip().upper()
    if not code or code == 'NAN' or (code.isdigit() and len(code) < 3):
        return None, "Пропускаем (пустой или номер раздела)"

    clean_code = code
    for prefix in ['ГЭСН', 'ТЕР', 'ФЕР', 'РЕСУРС']:
        if code.startswith(prefix):
            clean_code = code[len(prefix):].strip('- ')
            break

    if code.startswith('ГЭСН'):
        return 'gesn', clean_code
    elif code.startswith('ТЕР'):
        return 'ter', clean_code
    elif code.startswith('ФЕР') or code.startswith('РЕСУРС') or '91.' in clean_code:
        return 'resource', clean_code
    else:
        if '-' in clean_code:
            first_part = clean_code.split('-')[0]
            if first_part.isdigit():
                if int(first_part) <= 11:
                    return 'gesn', clean_code
                else:
                    return 'ter', clean_code
            else:
                return 'gesn', clean_code
        elif '.' in clean_code:
            return 'resource', clean_code

    return None, f"Не удалось определить базу для кода: {code}"


def build_item_link(base_name: str, clean_code: str) -> str:
    """Формируем ссылку в формате:
    https://cs.smetnoedelo.ru/fsscm/fsscm{code}.html
    """
    if not clean_code:
        return ""
    code_for_url = str(clean_code).replace(" ", "").replace("—", "-")
    return f"https://cs.smetnoedelo.ru/fsscm/fsscm{code_for_url}.html"


# === Демо-функция для получения цен ===
def get_price_demo(obosnovanie):
    base_name, clean_code = detect_base_by_code(obosnovanie)
    if not base_name:
        return None, "Не определено"

    if base_name == 'gesn':
        price = round(random.uniform(500, 5000), 2)
    elif base_name == 'ter':
        price = round(random.uniform(1000, 10000), 2)
    elif base_name == 'resource':
        price = round(random.uniform(50, 500), 2)
    else:
        price = round(random.uniform(100, 1000), 2)

    return price, base_name


# === Streamlit интерфейс ===
st.set_page_config(page_title="ИИ для расчёта смет", layout="wide")
st.title("ИИ для расчёта строительных смет")

uploaded_file = st.file_uploader("Загрузите смету (Excel)", type=["xlsx"]) 

if uploaded_file is not None:
    try:
        smeta = pd.read_excel(uploaded_file)

        # --- Поиск колонки с кодами ---
        obosn_col = None
        keywords_code = ['обоснование', 'код', 'code', 'шифр', 'артикул']
        for col in smeta.columns:
            col_clean = str(col).strip().lower()
            if any(k in col_clean for k in keywords_code):
                obosn_col = col
                break

        if obosn_col is None:
            st.error("Не найдена колонка с кодами расценок")
        else:
            st.subheader("Исходная смета")
            st.dataframe(smeta)

            # --- Поиск колонки с количеством ---
            qty_col = None
            keywords_qty = ['кол', 'qty', 'amount']
            for col in smeta.columns:
                col_clean = str(col).strip().lower()
                if any(k in col_clean for k in keywords_qty):
                    qty_col = col
                    break
            if qty_col is None:
                for i, col in enumerate(smeta.columns):
                    if 'единица' in str(col).lower():
                        if i + 1 < len(smeta.columns):
                            qty_col = smeta.columns[i + 1]
                        break
            if qty_col is None:
                for col in smeta.columns:
                    if pd.api.types.is_numeric_dtype(smeta[col]):
                        qty_col = col
                        break

            if qty_col is None:
                st.error("Не найдена колонка с количеством")
            else:
                st.info(f"Колонка с количеством: {qty_col}")

                # --- Получаем демо-цены и ссылки ---
                prices, base_names, links = [], [], []
                for raw_code in smeta[obosn_col]:
                    price, base_name = get_price_demo(raw_code)
                    prices.append(price)
                    base_names.append(base_name)

                    base_for_link, clean_code = detect_base_by_code(raw_code)
                    if clean_code:
                        links.append(build_item_link(base_for_link, clean_code))
                    else:
                        links.append("")

                # --- Нормализуем количество и цену ---
                smeta['Количество'] = pd.to_numeric(smeta[qty_col], errors='coerce').fillna(0)
                smeta['Цена (API)'] = pd.to_numeric(pd.Series(prices), errors='coerce').fillna(0)

                # --- Рассчитываем "Всего в текущем уровне цен" ---
                smeta['Всего в текущем уровне цен'] = smeta['Количество'] * smeta['Цена (API)']

                # --- Добавляем вспомогательные колонки ---
                smeta['База'] = base_names
                smeta['Ссылка на товар'] = links

                # --- Подсветка строк без базы ---
                def highlight_base(row):
                    if row['База'] == "Не определено" or row['База'] is None:
                        return ['background-color: #ffcccc'] * len(row)
                    return [''] * len(row)

                # --- Формируем финальный DataFrame ---
                col_name = next((c for c in smeta.columns if 'наименование' in str(c).lower()), 'Наименование работ и затрат')
                col_unit = next((c for c in smeta.columns if 'единица' in str(c).lower()), 'Единица измерения')

                final_cols = [
                    obosn_col,
                    col_name,
                    col_unit,
                    'Количество',
                    'Цена (API)',
                    'Всего в текущем уровне цен',
                    'Ссылка на товар',
                    'База',
                ]
                final_df = smeta[final_cols].copy()

                st.subheader("Результат расчёта (демо)")
                st.dataframe(final_df.style.apply(highlight_base, axis=1))

                # --- Итог строго по числовой колонке ---
                total_new_cost = pd.to_numeric(final_df['Всего в текущем уровне цен'], errors='coerce').fillna(0).sum()
                st.metric("Общая стоимость по актуальным ценам", f"{total_new_cost:,.2f} руб.")

                # --- Подготовка Excel ---
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='Расчёт')
                    ws = writer.sheets['Расчёт']

                    link_col_idx = final_df.columns.get_loc('Ссылка на товар') + 1
                    for r in range(2, len(final_df) + 2):
                        url = ws.cell(row=r, column=link_col_idx).value
                        if url:
                            cell = ws.cell(row=r, column=link_col_idx)
                            cell.hyperlink = url
                            cell.style = "Hyperlink"

                    total_row = len(final_df) + 2
                    ws.cell(row=total_row, column=1, value='ИТОГО')
                    total_col_idx = final_df.columns.get_loc('Всего в текущем уровне цен') + 1
                    ws.cell(row=total_row, column=total_col_idx, value=total_new_cost)

                processed_data = output.getvalue()

                st.download_button(
                    label="📥 Скачать расчёт в Excel",
                    data=processed_data,
                    file_name="смета_с_актуальными_ценами.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    except Exception as e:
        st.error(f"Ошибка при обработке файла: {e}")
