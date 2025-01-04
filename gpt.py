"""
GPT модуль для обработки текстовых запросов с использованием OpenAI API.

Модуль предоставляет функционал для:
- Обработки текстовых запросов через OpenAI GPT API
- Хранения истории диалогов в CSV файле
- Загрузки пользовательских ролей из текстового файла

Требования:
- OpenAI API ключ
- pandas для работы с CSV
- openai библиотека

Автор: Шабалин Игорь
Версия: 1.0
"""

import datetime
import os
import codecs
import pandas as pd
import openai

# Конфигурационные параметры
HISTORY_LENGTH = 8  # Количество последних сообщений для контекста
TEMPERATURE = 0.7   # Параметр температуры для GPT (0-1). Чем выше, тем более креативные ответы
HISTORY_FILE = 'history1.csv'  # Файл для хранения истории диалогов
MODEL = "gpt-4o"    # Используемая модель GPT

# Настройка прокси если необходимо
openai.proxy = {
    'http': 'http://123.123.123.123:3128',
    'https': 'http://123.123.123.123:3128'
}

def ask(user_id: int, text: str) -> str:
    """
    Обработка текстового запроса через GPT API.
    
    Функция выполняет следующие шаги:
    1. Загружает историю диалогов из CSV файла
    2. Читает файл роли для контекста
    3. Формирует запрос к GPT с учетом истории
    4. Сохраняет ответ в историю
    
    Args:
        user_id (int): Идентификатор пользователя
        text (str): Текст запроса
    
    Returns:
        str: Ответ от GPT модели
    
    Raises:
        Exception: При ошибках работы с API или файлами
    """
    print("Обработка запроса")
    
    # Установка API ключа
    gpt_key = 'your-api-key-here'  # Замените на ваш ключ API
    openai.api_key = gpt_key
    
    # Загрузка истории диалогов
    try:
        history = pd.read_csv(HISTORY_FILE)
    except OSError:
        history = pd.DataFrame(columns=['user_id', 'role', 'content'])
    
    # Чтение файла роли
    role_file = os.path.join(os.getcwd(), 'role.txt')
    with codecs.open(role_file, 'r', encoding='utf-8') as file:
        role = file.read()
    
    started = datetime.datetime.now()
    
    # Добавление нового сообщения в историю
    history = pd.concat(
        [history, pd.DataFrame.from_records([{
            'user_id': user_id,
            'role': 'user',
            'content': text
        }])],
        ignore_index=True
    )
    
    # Формирование сообщений для GPT
    messages = [
        {
            'role': 'system',
            'content': role,
            'temperature': TEMPERATURE
        },
        {
            'role': 'user',
            'content': ''
        }
    ] + history[history['user_id'] == user_id][['role', 'content']].tail(
        HISTORY_LENGTH
    ).to_dict('records')
    
    # Запрос к GPT API
    response = openai.ChatCompletion.create(
        model=MODEL,
        messages=messages
    )
    
    # Сохранение ответа в историю
    response_text = response['choices'][0]['message']['content']
    history = pd.concat(
        [history, pd.DataFrame.from_records([{
            'user_id': user_id,
            'role': 'assistant',
            'content': response_text
        }])],
        ignore_index=True
    )
    
    # Сохранение обновленной истории
    history.to_csv(HISTORY_FILE, index=False)
    
    return response_text

if __name__ == "__main__":
    # Пример использования
    response = ask(123, "как дела?")
    print(response)
