import streamlit as st
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from copy import copy
from io import BytesIO

st.title("Полное копирование сметы с сохранением формата и объединений")

uploaded_file = st.file_uploader("Загрузите исходную смету (Excel)", type=["xlsx"])

if uploaded_file:
    file_name = st.text_input("Введите название нового файла (без расширения):")

    if file_name:
        try:
            # Загружаем исходную книгу
            wb_input = load_workbook(uploaded_file)
            ws_input = wb_input.active

            # Жестко ограничиваем 15 колонками (как в шапке)
            max_col = 16
            st.info("Используется строго 15 колонок")

            # Создаем новую книгу и лист
            wb_output = Workbook()
            ws_output = wb_output.active

            # Добавляем вашу шапку (ровно 15 колонок)
            header = [
                "№ п/п", "Обоснование", "Наименование работ и затрат", "", "",
                "Единица измерения", "на единицу измерения", "коэффициенты",
                "всего с учетом коэффициентов", "на единицу измерения в базисном уровне цен",
                "индекс", "на единицу измерения в текущем уровне цен", "коэффициенты",
                "всего в текущем уровне цен"
            ]
            
            ws_output.append(header)

            # Копируем данные из исходного файла начиная с 46-й строки (только первые 14 колонок)
            output_row = 2
            
            for row_num in range(46, ws_input.max_row + 1):
                for col_num in range(1, max_col + 1):  # Только 14 колонок
                    source_cell = ws_input.cell(row=row_num, column=col_num)
                    target_cell = ws_output.cell(row=output_row, column=col_num)
                    
                    # Копируем значение
                    target_cell.value = source_cell.value
                    
                    # Копируем все стили
                    if source_cell.has_style:
                        target_cell.font = copy(source_cell.font)
                        target_cell.fill = copy(source_cell.fill)
                        target_cell.border = copy(source_cell.border)
                        target_cell.alignment = copy(source_cell.alignment)
                        target_cell.number_format = copy(source_cell.number_format)
                
                output_row += 1

            # Копируем объединенные ячейки (только в пределах 14 колонок)
            for merged_range in ws_input.merged_cells.ranges:
                min_row, min_col, max_row, max_col_val = merged_range.min_row, merged_range.min_col, merged_range.max_row, merged_range.max_col
                
                # Копируем только объединения в пределах 14 колонок и начиная с 46 строки
                if min_row >= 46 and max_col_val <= max_col:
                    new_min_row = min_row - 46 + 2
                    new_max_row = max_row - 46 + 2
                    
                    try:
                        ws_output.merge_cells(
                            start_row=new_min_row,
                            start_column=min_col,
                            end_row=new_max_row,
                            end_column=max_col_val
                        )
                    except:
                        pass  # Игнорируем ошибки объединения

            # Копируем ширину колонок (только первые 14)
            for col_num in range(1, max_col + 1):
                col_letter = get_column_letter(col_num)
                if col_letter in ws_input.column_dimensions:
                    ws_output.column_dimensions[col_letter].width = ws_input.column_dimensions[col_letter].width
                else:
                    # Стандартная ширина для колонок
                    ws_output.column_dimensions[col_letter].width = 12

            # Сохраняем в поток
            output = BytesIO()
            wb_output.save(output)
            output.seek(0)

            st.success("Файл успешно обработан! Использовано 15 колонок.")
            st.download_button(
                label="Скачать смету",
                data=output,
                file_name=f"{file_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Произошла ошибка: {str(e)}")