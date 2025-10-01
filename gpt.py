import os
import json
import logging
import threading
from typing import List, Dict, Any
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from datetime import datetime
import re
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
PRICES_FILE = os.path.join(BASE_DIR, "prices.json")

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

history = []
history_lock = threading.Lock()
prices_data = []
prices_lock = threading.Lock()

def load_prices():
    """Загружает цены из JSON-файла с проверкой структуры"""
    global prices_data
    try:
        if os.path.exists(PRICES_FILE):
            with open(PRICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            logger.info(f"[PRICES] Прочитано из файла: {len(data)} записей")
            
            if isinstance(data, list):
                valid_items = []
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        price_record = {
                            "номер": item.get("номер", i + 1),
                            "наименование": item.get("наименование", ""),
                            "единица": item.get("единица", "шт"),
                            "цена_голден": item.get("цена_голден"),
                            "цена_уткур": item.get("цена_уткур")
                        }
                        if price_record["наименование"]:
                            valid_items.append(price_record)
                        else:
                            logger.warning(f"[PRICES] Пропущена запись без наименования: {item}")
                
                prices_data = valid_items
                logger.info(f"[PRICES] Успешно загружено {len(prices_data)} позиций")
                save_prices()
            else:
                logger.warning("[PRICES] Файл prices.json должен содержать массив объектов")
                prices_data = []
        else:
            logger.warning(f"[PRICES] Файл не найден: {PRICES_FILE}")
            sample_data = [
                {"номер": 1, "наименование": "Пример работы", "единица": "м2", "цена_голден": 100, "цена_уткур": 120}
            ]
            with open(PRICES_FILE, "w", encoding="utf-8") as f:
                json.dump(sample_data, f, ensure_ascii=False, indent=2)
            prices_data = sample_data
            logger.info("[PRICES] Создан файл с примером данных")
    except Exception as e:
        logger.error(f"[PRICES] Ошибка загрузки: {e}")
        prices_data = []

def save_prices():
    """Сохраняет цены в файл"""
    try:
        with prices_lock:
            sorted_prices = sorted(prices_data, key=lambda x: x["номер"])
            with open(PRICES_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted_prices, f, ensure_ascii=False, indent=2)
            logger.info(f"[PRICES] Цены сохранены: {len(sorted_prices)} позиций")
            return True
    except Exception as e:
        logger.error(f"[PRICES] Ошибка сохранения: {e}")
        return False

def get_price(work_name, vendor="голден"):
    """Возвращает цену по наименованию работы."""
    key = "цена_голден" if vendor.lower() == "голден" else "цена_уткур"
    with prices_lock:
        for item in prices_data:
            if item.get("наименование") == work_name:
                return item.get(key)
    return None

def load_history():
    global history
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            logger.info(f"[LOAD] История загружена: {len(history)} записей")
        except Exception as e:
            logger.error(f"[LOAD] Ошибка: {e}")
            history = []
    else:
        history = []
        logger.info(f"[LOAD] Файл истории отсутствует ({HISTORY_FILE})")

def save_history():
    try:
        tmp_file = HISTORY_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, HISTORY_FILE)
        app.logger.info(f"[SAVE] История сохранена, записей: {len(history)}")
    except Exception as e:
        app.logger.error(f"[SAVE] Ошибка сохранения истории: {e}")

def load_api_key():
    paths = [
        os.path.join(BASE_DIR, "secret", "openai_key.txt"),
        os.path.join(BASE_DIR, "openai_key.txt"),
        "secret/openai_key.txt",
        "openai_key.txt"
    ]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    key = f.read().strip()
                    if key:
                        logger.info(f"[KEY] найден в {path}")
                        return key
            except Exception as e:
                logger.warning(f"[KEY] Ошибка чтения {path}: {e}")
    logger.error("[KEY] Не найден API ключ")
    return None

def full_prices_table():
    """Возвращает все цены из prices.json в виде Markdown-таблицы"""
    if not prices_data:
        return ""
    header = "| № | Наименование | Ед. изм. | Цена Голден | Цена Уткур |\n"
    separator = "|---|--------------|----------|-------------|------------|\n"
    rows = []
    with prices_lock:
        for p in prices_data:
            rows.append(f"| {p['номер']} | {p['наименование']} | {p['единица']} | {p.get('цена_голден','')} | {p.get('цена_уткур','')} |")
    return header + separator + "\n".join(rows)

def _to_number(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        s = str(x).strip().replace('\xa0','').replace(' ','').replace(',', '.')
        s = re.sub(r'[^0-9\.\-]', '', s)
        if s in ('', '.', '-'):
            return None
        return float(s)
    except Exception:
        return None

def _normalize(s: str) -> str:
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r'[\t\r\n]', ' ', s)
    s = re.sub(r'[.,:;()\"\'«»]', ' ', s)
    s = re.sub(r'[-/–—]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def prepare_prices_for_gpt(smeta_items: List[Dict[str, Any]]) -> str:
    if not smeta_items:
        return ""
    header = "| № п/п | Тип | Обоснование | Наименование | Ед. измерения | Количество | Сметная цена | Цена Голден | Цена Уткур | Максимальная цена | Средняя цена |\n"
    separator = "|-------|-----|-------------|--------------|---------------|------------|--------------|-------------|------------|-------------------|--------------|\n"
    rows = []
    with prices_lock:
        prepped_prices = []
        for p in prices_data:
            pname = p.get("наименование") or ""
            prepped_prices.append({"raw": p, "name_norm": _normalize(pname)})
        for idx, item in enumerate(smeta_items, start=1):
            type_field = item.get("Тип", "") or item.get("тип", "")
            obosnovanie = item.get("Обоснование", "") or item.get("обоснование", "")
            name = item.get("Наименование", "") or item.get("наименование", "")
            unit = item.get("Ед. измерения", "") or item.get("единица", "")
            qty = item.get("Количество", "") or item.get("количество", "")
            smet_price = item.get("Сметная цена", "")

            golden_price = "не найдено"
            utkur_price = "не найдено"
            max_price = "не найдено"
            avg_price = "не найдено"

            name_norm = _normalize(name)

            for p in prepped_prices:
                pn = p["name_norm"]
                if pn and (pn == name_norm or pn in name_norm or name_norm in pn):
                    raw = p["raw"]
                    g = _to_number(raw.get("цена_голден"))
                    u = _to_number(raw.get("цена_уткур"))
                    if g is not None:
                        golden_price = g
                    if u is not None:
                        utkur_price = u
                    
                    if g is not None and u is not None:
                        max_price = max(g, u)
                        avg_price = round((g + u) / 2, 2)
                    elif g is not None:
                        max_price = g
                        avg_price = g
                    elif u is not None:
                        max_price = u
                        avg_price = u
                    
                    break
            rows.append(
                f"| {idx} | {type_field} | {obosnovanie} | {name} | {unit} | {qty} | {smet_price} | {golden_price} | {utkur_price} | {max_price} | {avg_price} |"
            )
    return header + separator + "\n".join(rows)

# Инициализация
load_prices()
load_history()
OPENAI_API_KEY = load_api_key()
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, 'gpt.html')

@app.route("/ask", methods=["POST"])
def ask():
    if not client:
        return jsonify({"error": "API ключ не настроен"}), 500
    data = request.json or {}
    prompt = (data.get("prompt") or "").strip()
    chat_history = data.get("history", [])
    smeta_items = data.get("smeta_items", [])
    if not prompt:
        return jsonify({"error": "Пустой запрос"}), 400
    logger.info(f"[ASK] Запрос пользователя: {prompt!r}")
    messages = [{"role":"system","content":"Ты специалист по составлению строительных смет. Используй только локальные цены из прайс-листа."}]
    prices_table_text = prepare_prices_for_gpt(smeta_items) or full_prices_table()
    if prices_table_text:
        messages.append({"role":"system","content":f"Прайс-лист:\n{prices_table_text}"})
        max_history = 10
        limited_history = chat_history[-max_history:]
        for msg in limited_history:
            messages.append({"role": msg.get("role"), "content": msg.get("content", "")})
            messages.append({"role": "user","content": f"""{prompt}
                             Важно: всегда отвечай в три части: 1. Краткое объяснение (перед таблицей). 2. Таблица в формате Markdown.3. Выводы и рекомендации после таблицы."""})
            entry_user = {"role":"user","content":prompt,"time":datetime.utcnow().isoformat()}
            with history_lock:
                history.append(entry_user)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.5,
            max_tokens=5000
        )
        resp_text = response.choices[0].message.content
        entry_gpt = {"role":"assistant","content":resp_text,"time":datetime.utcnow().isoformat()}
        with history_lock:
            history.append(entry_gpt)
            save_history()
        return jsonify({"response": resp_text})
    except Exception as e:
        err_msg = f"Ошибка сервера: {str(e)}"
        entry_err = {"role":"error","content":err_msg,"time":datetime.utcnow().isoformat()}
        with history_lock:
            history.append(entry_err)
            save_history()
        logger.error(f"[ASK] Ошибка OpenAI: {e}")
        return jsonify({"error": err_msg}), 500

@app.route("/history", methods=["GET"])
def get_history():
    user_history = [msg for msg in history if msg.get("role") == "user"]
    logger.info(f"[HISTORY] Запрос истории: {len(user_history)} записей пользователя")
    return jsonify(user_history)

@app.route("/full_history", methods=["GET"])
def get_full_history():
    limit = int(request.args.get("limit", 50)) 
    with history_lock:
        return jsonify(history[-limit:])

@app.route("/clear_history", methods=["POST"])
def clear_history():
    global history
    with history_lock:
        history = []
        save_history()
    logger.info("[HISTORY] История очищена")
    return jsonify({"status": "ok"})

@app.route("/reload_prices", methods=["POST"])
def reload_prices():
    load_prices()
    return jsonify({"status": "ok", "prices_loaded": len(prices_data)})

@app.route("/prices_status", methods=["GET"])
def prices_status():
    return jsonify({
        "prices_loaded": len(prices_data),
        "prices_file_exists": os.path.exists(PRICES_FILE),
        "prices_sample": prices_data[:3] if prices_data else []
    })

@app.route("/get_prices", methods=["GET"])
def get_prices():
    with prices_lock:
        return jsonify(prices_data)

@app.route("/update_price", methods=["POST"])
def update_price():
    data = request.json or {}
    required_fields = ["номер", "наименование", "единица"]
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Отсутствует обязательное поле: {field}"}), 400
    try:
        number = int(data["номер"])
    except ValueError:
        return jsonify({"error": "Поле 'номер' должно быть числом"}), 400
    golden = data.get("цена_голден") or None
    utkur = data.get("цена_уткур") or None
    with prices_lock:
        found_index = -1
        for i, item in enumerate(prices_data):
            item_number = item.get("номер")
            if isinstance(item_number, str):
                try:
                    item_number = int(item_number)
                except ValueError:
                    continue
            if item_number == number:
                found_index = i
                break
        price_record = {
            "номер": number,
            "наименование": data["наименование"],
            "единица": data["единица"],
            "цена_голден": golden,
            "цена_уткур": utkur
        }
        if found_index >= 0:
            prices_data[found_index] = price_record
            message = "Цена обновлена"
        else:
            prices_data.append(price_record)
            message = "Новая цена добавлена"
        success = save_prices()
        if not success:
            return jsonify({"status": "error", "error": "Ошибка сохранения файла"}), 500
        return jsonify({"status": "ok", "message": message})

@app.route("/delete_price/<int:price_id>", methods=["DELETE"])
def delete_price(price_id):
    with prices_lock:
        initial_length = len(prices_data)
        new_prices_data = [item for item in prices_data if int(item.get("номер",0)) != price_id]
        prices_data[:] = new_prices_data
        if len(prices_data) < initial_length:
            if save_prices():
                return jsonify({"status": "ok", "message": "Цена удалена", "total_prices": len(prices_data)})
            else:
                return jsonify({"error": "Ошибка сохранения после удаления"}), 500
        else:
            return jsonify({"error": "Цена не найдена"}), 404

if __name__ == "__main__":
    logger.info(f"[START] Сервер запущен. Файл истории: {HISTORY_FILE}")
    logger.info(f"[START] Файл цен: {PRICES_FILE}")
    logger.info(f"[START] Загружено {len(prices_data)} позиций цен")
    app.run(host="127.0.0.1", port=5000, debug=True)