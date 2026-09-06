import pandas as pd
from sqlalchemy import create_engine, text
import streamlit as st
from datetime import datetime

# Заголовок приложения
st.title("Загрузка Excel в PostgreSQL")

# Загрузка файла Excel через Streamlit
uploaded_file = st.file_uploader("Выберите Excel файл", type="xlsx")

if uploaded_file:
    # Чтение Excel в DataFrame
    df = pd.read_excel(uploaded_file)

    # Переименовываем колонки в соответствии с БД
    df = df.rename(columns={
        'Обоснование': 'obosnovanie',
        'Наименование работ и затрат': 'naimenovanie',
        'Единица измерения': 'edinica_izmereniya',
        'Количество': 'kolichestvo'
    })

    # Преобразуем в список словарей
    records = df.to_dict(orient='records')

    # --- Подключение к базе ---
    db_user = ''       # Ваш пользователь PostgreSQL
    db_password = ''    # Пароль
    db_host = 'localhost'
    db_port = ''
    db_name = 'smeta_db'

    engine = create_engine(f'postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')

    try:
        # Вставка данных
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO smeta_items (obosnovanie, naimenovanie, edinica_izmereniya, kolichestvo)
                    VALUES (:obosnovanie, :naimenovanie, :edinica_izmereniya, :kolichestvo)
                """),
                records
            )
            conn.commit()

        st.success(f"Данные успешно загружены! Всего записей: {len(records)}")
    except Exception as e:
        st.error(f"Ошибка при загрузке: {e}")
 # --- Отображение таблицы ---
        query = "SELECT id, obosnovanie, naimenovanie, edinica_izmereniya, kolichestvo FROM smeta_items;"
        df_db = pd.read_sql(query, engine)
        st.subheader("Текущие данные в таблице smeta_items")
        st.dataframe(df_db)

    except Exception as e:
        st.error(f"Ошибка при загрузке: {e}")
