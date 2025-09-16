import pandas as pd
import streamlit as st
from io import BytesIO
import os

st.title("Обработка смет Excel")

# Ввод пути для сохранения файлов (если пусто — используется кнопка скачивания)
save_path = st.text_input("Введите путь для сохранения обработанных файлов (например, C:/Users/.../processed):")

# Загрузка файлов
uploaded_files = st.file_uploader(
    "Выберите Excel-файлы",
    type=["xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"Обрабатывается: {uploaded_file.name}")
        
        # Чтение файла без заголовков для поиска нужной строки
        raw_df = pd.read_excel(uploaded_file, header=None)
        required_cols = ['Обоснование', 'Наименование работ и затрат', 'Единица измерения', 'Количество']
        header_row = None
        
        for i, row in raw_df.iterrows():
            if all(col in row.values for col in required_cols):
                header_row = i
                break

        if header_row is None:
            st.error(f"Не найдены колонки {required_cols} в файле {uploaded_file.name}")
            continue

        # Чтение с правильной строкой заголовка
        df = pd.read_excel(uploaded_file, header=header_row)
        df = df[required_cols]
        df = df.dropna(subset=required_cols, how='all')
        df['Количество'] = pd.to_numeric(df['Количество'], errors='coerce').fillna(0)

        # Сохранение файла на диск, если указан путь
        if save_path:
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            file_name = os.path.join(save_path, f"processed_{uploaded_file.name}")
            df.to_excel(file_name, index=False)
            st.success(f"Файл сохранен: {file_name}")
        else:
            # Иначе — предлагаем скачать
            output = BytesIO()
            df.to_excel(output, index=False)
            output.seek(0)
            st.download_button(
                label=f"Скачать обработанный {uploaded_file.name}",
                data=output,
                file_name=f"processed_{uploaded_file.name}",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )





