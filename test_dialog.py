from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from transformers import pipeline
from datasets import load_dataset
import os
import re
import random

app = FastAPI(title="Russian ChatBot API")

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Модели данных ===
class ChatRequest(BaseModel):
    message: str
    history: list = []

class ChatResponse(BaseModel):
    response: str
    status: str

# === Загрузка модели GPT ===
try:
    chat_model = pipeline(
        "text-generation",
        model="inkoziev/rugpt3small_based_on_gpt2",
        tokenizer="inkoziev/rugpt3small_based_on_gpt2",
        device=-1
    )
    MODEL_LOADED = True
except:
    MODEL_LOADED = False

# === Загрузка локального датасета ===
dataset_path = os.path.join(os.path.dirname(__file__), "dialogs.json")
try:
    dialog_dataset = load_dataset("json", data_files=dataset_path, split="train")
    DATA_LOADED = True
except FileNotFoundError:
    print(f"Файл {dataset_path} не найден. Бот будет работать только через GPT.")
    DATA_LOADED = False

# === Вспомогательные функции ===
def clean_response(text):
    text = re.sub(r'([!?.]){2,}', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def answer_from_dataset(message):
    if not DATA_LOADED:
        return None
    matches = [item['bot'] for item in dialog_dataset if any(word.lower() in message.lower() for word in item['user'].split())]
    if matches:
        return random.choice(matches)
    return None

# === Эндпоинт чата ===
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not MODEL_LOADED and not DATA_LOADED:
        raise HTTPException(status_code=503, detail="Model and dataset not loaded")
    
    try:
        # Сначала локальный датасет
        bot_response = answer_from_dataset(request.message)
        
        if bot_response is None:
            # Если нет подходящего ответа — GPT
            chat_history = ""
            for human, assistant in request.history:
                chat_history += f"👤: {human}\n🤖: {assistant}\n"
            
            prompt = f"{chat_history}👤: {request.message}\n🤖:"
            
            result = chat_model(
                prompt,
                max_length=250,
                num_return_sequences=1,
                temperature=0.8,
                do_sample=True,
                pad_token_id=50256,
                no_repeat_ngram_size=3
            )
            
            full_text = result[0]['generated_text']
            bot_response = full_text.split("🤖:")[-1].strip()
        
        return ChatResponse(
            response=clean_response(bot_response),
            status="success"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === HTML интерфейс ===
@app.get("/")
async def serve_interface():
    return FileResponse("chat_interface.html")

# === HTML файл ===
html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Russian ChatBot</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .chat-container { border: 1px solid #ccc; border-radius: 10px; padding: 20px; height: 500px; overflow-y: auto; margin-bottom: 20px; }
        .user { background-color: #e3f2fd; padding: 10px; border-radius: 10px; margin: 5px 0; text-align: right; }
        .bot { background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px 0; }
        .input-area { display: flex; gap: 10px; }
        input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 5px; }
        button { padding: 10px 20px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <h1>🤖 Русский Чат-Бот</h1>
    <div id="chat" class="chat-container"></div>
    <div class="input-area">
        <input type="text" id="message" placeholder="Введите сообщение..." onkeypress="if(event.key=='Enter') sendMessage()">
        <button onclick="sendMessage()">Отправить</button>
    </div>

    <script>
        const chatContainer = document.getElementById('chat');
        const messageInput = document.getElementById('message');
        let chatHistory = [];

        function addMessage(role, text) {
            const div = document.createElement('div');
            div.className = role;
            div.innerHTML = `<strong>${role === 'user' ? '👤 Вы' : '🤖 Бот'}:</strong> ${text}`;
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        async function sendMessage() {
            const message = messageInput.value.trim();
            if (!message) return;

            messageInput.disabled = true;
            addMessage('user', message);
            messageInput.value = '';

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        message: message,
                        history: chatHistory
                    })
                });

                const data = await response.json();
                if (data.status === 'success') {
                    addMessage('bot', data.response);
                    chatHistory.push([message, data.response]);
                } else {
                    addMessage('bot', 'Ошибка: ' + data.detail);
                }
            } catch (error) {
                addMessage('bot', 'Ошибка соединения');
            }

            messageInput.disabled = false;
            messageInput.focus();
        }
    </script>
</body>
</html>
"""

# === Сохраняем HTML файл ===
with open("chat_interface.html", "w", encoding="utf-8") as f:
    f.write(html_content)

# === Запуск сервера ===
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
