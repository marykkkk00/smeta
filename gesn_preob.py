import streamlit as st
import pandas as pd
import json

st.title("Преобразование Excel в JSON по ГЭСН")

# Загрузка Excel файла
uploaded_file = st.file_uploader("Загрузите Excel файл", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Чистка текстовых колонок
    text_columns = ["Сборник", "Наименование", "Шифр", "ЕдИзм"]
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace("\xa0", " ").str.strip()

    # Выбор сборника
    collections = df['Сборник'].unique().tolist()
    selected_collection = st.selectbox("Выберите сборник (опционально):", ["Все"] + collections)

    # Фильтрация по сборнику
    if selected_collection != "Все":
        df_filtered = df[df['Сборник'] == selected_collection]
    else:
        df_filtered = df.copy()

    # Фильтрация по наименованию работ (поиск подстроки)
    search_name = st.text_input("Поиск по наименованию работы (опционально):")
    if search_name:
        df_filtered = df_filtered[df_filtered['Наименование'].str.contains(search_name, case=False, na=False)]

    st.write(f"Найдено записей: {len(df_filtered)}")

    # Создаём пустой список для JSON
    json_list = []

    for _, row in df_filtered.iterrows():
        # Очистка стоимости и преобразование в int
        cost_str = str(row["Стоимость"]).replace("\xa0", "").replace(" ", "")
        try:
            cost_int = int(cost_str)
        except ValueError:
            cost_int = 0  # Если не удалось преобразовать, ставим 0

        json_item = {
            "№": int(row["№"]),
            "Шифр": str(row["Шифр"]),
            "Наименование": str(row["Наименование"]),
            "ЕдИзм": str(row["ЕдИзм"]),
            "Стоимость": cost_int
        }
        json_list.append(json_item)

    # Преобразуем в JSON строку
    json_str = json.dumps(json_list, ensure_ascii=False, indent=4)
    st.code(json_str, language="json")

    # Кнопка для скачивания JSON
    st.download_button(
        label="Скачать JSON",
        data=json_str,
        file_name="output.json",
        mime="application/json"
    )
