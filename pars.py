import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from bs4 import BeautifulSoup
import urllib.parse
import time
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import re

# ======== ФУНКЦИИ ДЛЯ КИРИЛЛИЦЫ ========
def register_cyrillic_font(font_name='Arial', font_path='arial.ttf'):
    """
    Регистрирует шрифт с поддержкой кириллицы для ReportLab
    font_name: имя шрифта для использования в canvas.setFont()
    font_path: путь к .ttf файлу шрифта
    """
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        print(f"Шрифт '{font_name}' успешно зарегистрирован.")
        return font_name
    except Exception as e:
        print(f"Ошибка регистрации шрифта '{font_name}': {e}")
        return None

def set_cyrillic_font(canvas_obj, font_name='Arial', size=10):
    """
    Устанавливает шрифт с поддержкой кириллицы в canvas
    """
    try:
        canvas_obj.setFont(font_name, size)
    except Exception as e:
        print(f"Не удалось установить шрифт '{font_name}': {e}")
        canvas_obj.setFont("Helvetica", size)  # fallback

# ======== НОВЫЕ ФУНКЦИИ ========
def clean_price(price_text):
    """Очищает цену от лишних символов и форматирует"""
    if not price_text:
        return None
    # Удаляем все нецифровые символы, кроме точки и запятой
    cleaned = re.sub(r'[^\d,.]', '', str(price_text))
    # Заменяем запятую на точку для float преобразования
    cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None

def format_price(price):
    """Форматирует цену в читаемый вид"""
    if price is None:
        return "Не найдено"
    return f"{price:,.2f} руб.".replace(',', ' ')

def create_price_table_pdf(product_data, font_name):
    """Создает PDF с таблицей цен для одного товара"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    
    # Заголовок товара
    title_text = f"{product_data['name']} ({product_data['type']})"
    elements.append(Paragraph(title_text, styles['Heading2']))
    elements.append(Spacer(1, 12))
    
    # Информация о товаре
    info_text = f"Ед. измерения: {product_data['unit']} | Кол-во: {product_data['quantity']} | Сметная цена: {product_data['estimate_price']} | Текущие цены: {product_data['current_price']}"
    elements.append(Paragraph(info_text, styles['Normal']))
    elements.append(Paragraph(f"Обоснование: {product_data['justification']}", styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Таблица с ценами по магазинам
    table_data = [['Магазин', 'Цена', 'Статус']]
    
    for shop_name, price_info in product_data['prices'].items():
        price_value = price_info.get('price')
        if price_value:
            table_data.append([shop_name, format_price(clean_price(price_value)), '✓ Найдено'])
        else:
            table_data.append([shop_name, 'Не найдено', '✗ Отсутствует'])
    
    # Создаем таблицу
    table = Table(table_data, colWidths=[200, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 20))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def collect_product_data(df, shop_columns):
    """Собирает данные по всем товарам"""
    product_data_list = []
    
    for idx, row in df.iterrows():
        prices = {}
        
        for shop_name in shop_columns:
            if shop_name in SHOP_INFO:
                shop_tuple = (shop_name, SHOP_INFO[shop_name][0])
                price, _ = search_product_in_shop(shop_tuple, row['Наименование'])
                prices[shop_name] = {
                    'price': price
                }
                time.sleep(0.1)  # Пауза между запросами
        
        product_data = {
            'name': row['Наименование'],
            'type': row.get('Тип', ''),
            'unit': row.get('Ед. измерения', ''),
            'quantity': row.get('Количество', ''),
            'estimate_price': row.get('Сметная цена', ''),
            'current_price': row.get('Текущие цены', ''),
            'justification': row.get('Обоснование', ''),
            'prices': prices
        }
        product_data_list.append(product_data)
    
    return product_data_list

st.title("Сбор цен по магазинам и генерация PDF (Материалы)")

# Словарь магазинов: название -> (URL поиска, CSS-селектор цены)
SHOP_INFO = {
    # Строительные материалы
    "Спектр Томск": ("https://spektr-tomsk.ru/search/?query={query}", ".price"),
    "Стройса": ("https://www.stroyssa.tomsk.ru/search/?q={query}", ".price"),
    "СтройПарк": ("https://stroyparkdiy.ru/search?search={query}", ".price"),
    "Сатурн": ("https://tomsk.saturn.net/catalog/search/?q={query}", ".price"),
    "СтройДвор70": ("https://stroydvor70.ru/search/?query={query}", ".price"),
    "СтройДвор Томск": ("https://stroydvor.tomsk.ru/search/?q{query}", ".price"),
    "СД70": ("https://sd70.ru/search/?query={query}", ".price"),
    "АвтоСтройЛавка": ("https://avtostroylavka70.ru/search/?query={query}", ".price"),
    "М-Плюс": ("https://mplus.tomsk.ru/search/?q={query}", ".price"),
    "СтройМастер": ("https://stroimaster.tomsk.ru/search/?q={query}", ".price"),
    "SMT Group": ("https://smt-group.ru/search/?q={query}", ".price"),
    "ВсеИнструменты": ("https://www.vseinstrumenti.ru/search/?q={query}", ".price"),
    "НСК-Строй": ("https://nsk-stroy.com/search/?q={query}", ".price"),
    "Опт-Стройка": ("https://opt-stroyka.ru/search/?q={query}", ".price"),
    "Строй-Мат54": ("https://stroy-mat54.ru/search/?q={query}", ".price"),
    "LemanaPro": ("https://novosibirsk.lemanapro.ru/search/?q={query}", ".price"),
    "Ладья": ("https://www.ladya.pro/search/?q={query}", ".price"),
    "ТомскЛес": ("https://tomskles.su/search/?q={query}", ".price"),
    "Амбар-С": ("https://tomsk.ambar-s.ru/search/?q={query}", ".price"),

    # Вода (сантехника)
    "Waterman": ("https://waterman-t.ru/search/?q={query}", ".price"),
    "Водолей": ("https://томск.водолей.рф/search?q={query}", ".price"),
    "Сантехника": ("https://tomsk.santehnica.ru/search/?q={query}", ".price"),
    "Смесители Томск": ("https://smesiteli-tomsk.ru/search/?q={query}", ".price"),

    # Крепеж
    "Крепеж70": ("https://krepeg70.ru/search/?q={query}", ".price"),
    "ПромКрепеж": ("https://tomsk.promkrepezh.ru/search/?q={query}", ".price"),

    # Утеплитель
    "ТСТН": ("https://tomsk.tstn.ru/search/?q={query}", ".price"),

    # Металл
    "Ferrum-N": ("https://tomsk.ferrum-n.ru/search/?q={query}", ".price"),
    "ANEP Metall": ("https://kemerovo.anepmetall.ru/search/?q={query}", ".price"),
    "SMT Group (металл)": ("https://smt-group.ru/search/?q={query}", ".price"),
    "СПК": ("https://tomsk.spk.ru/search/?q={query}", ".price"),
    "ЕвроМет": ("https://ewromet.ru/search/?q={query}", ".price"),
    "МеталлоБаза": ("https://metallobazan.ru/search/?q={query}", ".price"),
    "МеталлКомфорт": ("https://metallkomfort.ru/search/?q={query}", ".price"),

    # Кровля/фасады
    "МеталлПрофиль": ("https://tomsk.metallprofil.ru/search/?q={query}", ".price"),
    "ArealMetall": ("https://arealmetall.com/search/?q={query}", ".price"),
    "DTM": ("https://tomsk.dtm.ru/search/?q={query}", ".price"),
    "КровельныйЦентр": ("https://кровельныйцентр.рф/search?query={query}", ".price"),

    # Электрика
    "Сиб-А": ("https://www.sib-a.ru/search/?q={query}", ".price"),
    "RS24": ("https://rs24.ru/search.html?q={query}", ".price"),
    "ЭТМ": ("https://www.etm.ru/catalog?searchValue={query}", ".price"),

    # Пиломатериал
    "EcoLes": ("https://ecoles-tomsk.ru/search/?q={query}", ".price"),
    "ТД Лесной": ("https://www.tdlesnoy.com/search/?q={query}", ".price"),

    # Двери
    "World of Doors": ("https://worldofdoors.ru/search?query={query}", ".price"),
    "Gallery of Doors": ("https://galleryofdoors.ru/search?search={query}", ".price"),
    "Фабрика Дверей": ("https://фабрикадверей.рф/tomsk/search?query={query}", ".price"),

    # Вентиляция
    "НеваТом": ("https://www.nevatom.ru/search/?q={query}", ".price"),
    "TomVent": ("https://tomvent.ru/search/?q={query}", ".price"),
    "VentGrad70": ("https://ventgrad70.ru/search/?q={query}", ".price"),

    # Базовые магазины
    "ChipDip": ("https://www.chipdip.ru/search?searchtext={query}", ".price"),
    "МиниМакс": ("https://www.minimaks.ru/catalog/?q={query}", ".price"),
    "ЯндексМаркет": ("https://market.yandex.ru/search?text={query}", ".price"),
}

uploaded_file = st.file_uploader("Выберите Excel файл", type=["xlsx"])
pdf_name = st.text_input("Имя PDF файла (без расширения)", value="report")

def search_product_in_shop(shop, product_name):
    """
    shop: tuple ("Название магазина", "URL с {query}")
    product_name: строка с названием товара
    возвращает: (цена, None) или (None, None), если не найдено
    """
    # Гарантируем, что product_name — это строка
    if not product_name or str(product_name).strip().lower() == 'nan':
        return None, None

    product_name = str(product_name).strip()
    shop_name, url_template = shop

    # Кодируем название товара в URL
    try:
        url = url_template.format(query=urllib.parse.quote(product_name))
    except Exception as e:
        print(f"Ошибка кодирования URL для '{product_name}' в {shop_name}: {e}")
        return None, None

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Ищем цену по CSS селекторам
        price = None
        price_tag = soup.select_one('.price, .product-price')  # пример
        if price_tag:
            price = price_tag.get_text(strip=True)

        return price, None  # Только цену, без изображения

    except requests.RequestException as e:
        print(f"Ошибка запроса для '{product_name}' в {shop_name}: {e}")
        return None, None

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    if "Материалы" not in xls.sheet_names:
        st.error("В Excel нет листа 'Материалы'")
    else:
        df = pd.read_excel(xls, sheet_name="Материалы")
        st.success(f"Лист 'Материалы' загружен. Найдено {len(df)} товаров.")

        if "Текущие цены" not in df.columns:
            st.error("В файле нет колонки 'Текущие цены'")
        else:
            price_index = df.columns.get_loc("Текущие цены")
            shop_columns = df.columns[price_index + 1:].tolist()
            st.write(f"Магазины для поиска: {shop_columns}")
            font_name = register_cyrillic_font('Arial', 'arial.ttf')

            # Добавляем новую кнопку для расширенного отчета
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Сгенерировать PDF (оригинальный)"):
                    pdf_buffer = BytesIO()
                    c = canvas.Canvas(pdf_buffer, pagesize=A4)
                    width, height = A4
                    margin = 50
                    y_position = height - margin
                    line_height = 14

                    for idx, row in df.iterrows():
                        y_position -= 20
                        set_cyrillic_font(c, font_name, 12) 
                        c.drawString(margin, y_position, f"{row['Наименование']} ({row['Тип']})")

                        y_position -= line_height
                        set_cyrillic_font(c, font_name, 10)
                        c.drawString(margin, y_position, f"Обоснование: {row.get('Обоснование','')}")
                        y_position -= line_height
                        c.drawString(margin, y_position, f"Ед. измерения: {row.get('Ед. измерения','')} | Кол-во: {row.get('Количество','')} | Сметная цена: {row.get('Сметная цена','')} | Текущие цены: {row.get('Текущие цены','')}")

                        for shop_name in shop_columns:
                         if shop_name in SHOP_INFO:
                          shop_tuple = (shop_name, SHOP_INFO[shop_name][0])
                          price, _ = search_product_in_shop(shop_tuple, row['Наименование'])
                         if price:
                          y_position -= line_height
                          c.drawString(margin + 20, y_position, f"{shop_name}: {price}")

                        y_position -= 30
                        if y_position < margin + 150:
                            c.showPage()
                            y_position = height - margin
                        time.sleep(0.2)  # небольшой таймаут, чтобы не перегружать сайты

                    c.save()
                    pdf_buffer.seek(0)
                    st.download_button(
                        label="Скачать PDF (оригинальный)",
                        data=pdf_buffer,
                        file_name=f"{pdf_name}_original.pdf",
                        mime="application/pdf"
                    )
                    st.success("PDF готов!")

            with col2:
                if st.button("Сгенерировать PDF с таблицей"):
                    with st.spinner("Собираем данные по магазинам..."):
                        product_data_list = collect_product_data(df, shop_columns)
                        
                        # Создаем объединенный PDF со всеми товарами
                        all_buffers = []
                        for product_data in product_data_list:
                            product_pdf = create_price_table_pdf(product_data, font_name)
                            all_buffers.append(product_pdf)
                        
                        # Объединяем все PDF в один
                        merged_pdf = BytesIO()
                        # Здесь можно добавить логику объединения PDF, если нужно
                        # Пока просто берем первый товар для демонстрации
                        if all_buffers:
                            st.download_button(
                                label="Скачать PDF с таблицей",
                                data=all_buffers[0],
                                file_name=f"{pdf_name}_table.pdf",
                                mime="application/pdf"
                            )
                            st.success("PDF с таблицей готов!")