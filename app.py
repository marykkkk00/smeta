from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
import pandas as pd
from io import BytesIO
import requests
import random
import os
import json
from typing import List, Dict, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Токены ===
SMETA_API_TOKEN = ""
HF_TOKEN = ""

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Создаем папку для статики, если её нет
os.makedirs("static", exist_ok=True)

# Статика
app.mount("/static", StaticFiles(directory="static"), name="static")

# Шаблоны
templates = Jinja2Templates(directory=".")

# Главная страница
@app.get("/", response_class=HTMLResponse)
async def serve_html(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

# --- Работа с API smeta ---
def get_price_from_smeta(material_name: str) -> float:
    """Получение цены материала из API сметы"""
    if not material_name or pd.isna(material_name) or str(material_name).strip() == "":
        return 0.0
        
    material_name = str(material_name).strip()
    logger.info(f"Поиск цены для: {material_name}")
    
    headers = {"Authorization": f"Bearer {SMETA_API_TOKEN}"}
    API_URL = "https://cs.smetnoedelo.ru/api/v1/prices"
    
    try:
        response = requests.get(
            API_URL, 
            headers=headers, 
            params={"query": material_name},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Ответ API: {data}")
            
            if data and isinstance(data, dict) and "prices" in data and data["prices"]:
                price = data["prices"][0].get("value", 0)
                logger.info(f"Найдена цена: {price} для {material_name}")
                return float(price)
                
    except Exception as e:
        logger.error(f"Ошибка API для {material_name}: {e}")
    
    return 0.0

# --- Загрузка Excel ---
@app.post("/upload_excel/")
async def upload_excel(file: UploadFile = File(...)):
    """Загрузка и обработка Excel файла со сметой"""
    try:
        logger.info(f"Начало обработки файла: {file.filename}")
        
        # Читаем содержимое файла
        content = await file.read()
        
        # Пытаемся прочитать Excel с разными движками
        try:
            df = pd.read_excel(BytesIO(content), engine='openpyxl')
        except:
            try:
                df = pd.read_excel(BytesIO(content), engine='xlrd')
            except:
                df = pd.read_excel(BytesIO(content))
        
        logger.info(f"Файл прочитан. Колонки: {df.columns.tolist()}")
        logger.info(f"Первые строки:\n{df.head()}")

        # Ищем колонку с обоснованием (пробуем разные варианты названий)
        obosnovanie_col = None
        possible_names = ['Обоснование', 'обоснование', 'Код', 'код', 'Артикул', 'артикул']
        
        for col in df.columns:
            if any(name in str(col).lower() for name in [n.lower() for n in possible_names]):
                obosnovanie_col = col
                break
        
        if not obosnovanie_col:
            return JSONResponse({
                "error": "Не найдена колонка с обоснованием. Доступные колонки: " + ", ".join(df.columns.tolist())
            }, status_code=400)

        # Ищем колонку количества
        qty_col = None
        qty_names = ['кол', 'количество', 'qty', 'amount', 'quantity']
        
        for col in df.columns:
            col_lower = str(col).lower()
            if any(name in col_lower for name in qty_names):
                qty_col = col
                break
        
        if not qty_col:
            return JSONResponse({
                "error": "Не найдена колонка количества. Доступные колонки: " + ", ".join(df.columns.tolist())
            }, status_code=400)

        # Добавляем колонку "Цена API"
        logger.info("Начинаем поиск цен...")
        df["Цена API"] = df[obosnovanie_col].apply(get_price_from_smeta)
        
        # Преобразуем колонки в числовой формат
        df[qty_col] = pd.to_numeric(df[qty_col], errors='coerce').fillna(0)
        df["Цена API"] = pd.to_numeric(df["Цена API"], errors='coerce').fillna(0)
        
        # Новая стоимость
        df["Новая стоимость"] = df[qty_col] * df["Цена API"]
        
        # Заполняем NaN значения
        df = df.fillna("")
        
        total_cost = float(df["Новая стоимость"].sum())
        logger.info(f"Обработка завершена. Общая стоимость: {total_cost}")

        return {
            "table": df.to_dict(orient="records"),
            "total": total_cost,
            "columns": df.columns.tolist()
        }

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        return JSONResponse({
            "error": f"Ошибка при обработке файла: {str(e)}"
        }, status_code=500)

# --- Умный чат с ИИ ---
class SmartChatBot:
    """Умный чат-бот для работы со сметами"""
    
    def __init__(self):
        self.context = {}
        self.responses = {
            "привет": ["Привет! Я помогу вам с расчетом смет.", "Здравствуйте! Чем могу помочь со сметами?"],
            "помощь": [
                "Я могу:\n• Анализировать Excel файлы со сметами\n• Искать актуальные цены материалов\n• Рассчитывать общую стоимость\n• Отвечать на вопросы по сметам",
                "Мои возможности:\n- Загрузка и анализ смет\n- Поиск цен через API\n- Расчет стоимости работ\n- Консультация по сметным нормам"
            ],
            "цена": [
                "Для поиска цен загрузите Excel файл со сметой, и я найду актуальные цены через базу данных.",
                "Я могу найти текущие рыночные цены материалов. Просто загрузите файл со сметой."
            ],
            "смета": [
                "Работа со сметами - моя специализация! Загрузите файл, и я помогу с расчетами.",
                "Отлично! Для начала работы загрузите Excel файл со сметой."
            ],
            "спасибо": ["Пожалуйста! Обращайтесь еще.", "Рад был помочь! Если будут вопросы - я здесь."],
            "default": [
                "Интересный вопрос! Я специализируюсь на работе со сметами. Могу помочь с расчетами или поиском цен.",
                "Понял ваш вопрос. Как эксперт по сметам, я могу помочь с анализом ваших данных.",
                "Хороший вопрос! Загрузите вашу смету, и я смогу дать более точный ответ.",
                "Я чат-бот для работы со сметами. Могу помочь с расчетами, ценами и анализом данных."
            ]
        }
    
    def generate_response(self, message: str) -> str:
        """Генерация ответа на основе сообщения"""
        message_lower = message.lower()
        
        # Поиск ключевых слов
        for keyword, responses in self.responses.items():
            if keyword in message_lower:
                return random.choice(responses)
        
        # Ответ по умолчанию с вариациями
        return random.choice(self.responses["default"])

# Глобальный экземпляр бота
chat_bot = SmartChatBot()

# --- API для чата ---
@app.post("/chat/")
async def chat(message: str = Form(...)):
    """Обработка сообщений в чате"""
    try:
        logger.info(f"Получено сообщение: {message}")
        
        # Генерируем ответ с помощью умного бота
        reply = chat_bot.generate_response(message)
        
        # Добавляем контекстный ответ если есть ключевые слова
        if any(word in message.lower() for word in ['эксель', 'excel', 'файл', 'загрузить']):
            reply += "\n\nДля загрузки сметы используйте кнопку 'Загрузить Excel' выше."
        
        elif any(word in message.lower() for word in ['цена', 'стоимость', 'расчет']):
            reply += "\n\nЯ могу автоматически найти актуальные цены для вашей сметы!"
        
        logger.info(f"Ответ: {reply}")
        return {"reply": reply}
        
    except Exception as e:
        logger.error(f"Ошибка в чате: {e}")
        return {"reply": "Извините, произошла ошибка. Попробуйте еще раз."}

# --- Получение истории чата ---
@app.get("/chat_history/")
async def get_chat_history():
    """Получение истории сообщений"""
    return {"history": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
