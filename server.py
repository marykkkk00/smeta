import requests

# Конфигурация
API_TOKEN = 'f8jnhskPMwzovgXG5dxtC7VI'  # Замените на ваш действительный токен!
BASE = 'gesn'  # База данных (gesn, ferm, fsscm и т.д.)
CODE = '11-01-011-01'  # Шифр расценки

# Формируем URL запроса
url = f'https://cs.smetnoedelo.ru/api/?token={API_TOKEN}&base={BASE}&code={CODE}'

try:
    # Отправляем GET-запрос к API
    response = requests.get(url)
    response.raise_for_status()  # Проверяем, не вернулся ли код ошибки (4xx или 5xx)

    # Парсим JSON ответ
    data = response.json()

    # Извлекаем список ресурсов
    resources = data['COMPOSITION']['RESOURCES']

    # Инициализируем переменные для подсчета
    total_man_hours = 0.0
    resources_list = []  # Список для хранения данных о каждом ресурсе

    print(f"Обрабатываем расценку: {data['CODE']} - {data['NAME']}")
    print("-" * 50)

    # Проходим по всем ресурсам в расценке
    for resource in resources:
        unit = resource['UNIT']
        quan = float(resource['QUAN'])
        code = resource['CODE']
        name = resource['NAME']

        # Проверяем, является ли единица измерения "чел.-ч"
        if unit == 'чел.-ч':
            total_man_hours += quan
            resource_type = 'Трудозатраты (чел.-ч)'
        else:
            resource_type = f'Прочий ресурс ({unit})'

        # Формируем строку для вывода информации о ресурсе
        resource_info = {
            'Тип': resource_type,
            'Код': code,
            'Наименование': name,
            'Кол-во на ед.': quan,
            'Ед. изм.': unit,
            # 'Сметная цена': 'Н/Д',  # Здесь нужно получить данные из другой базы (например, FSSCCM)
            # 'Цена из API': 'Н/Д'     # В предоставленном API явной цены нет, требуется дополнительный запрос
        }
        resources_list.append(resource_info)

    # Выводим подробную таблицу по всем ресурсам
    print("Детализация по всем ресурсам:")
    for res in resources_list:
        print(f"  * {res['Тип']}: {res['Кол-во на ед.']} {res['Ед. изм.']} - {res['Наименование']}")

    print("-" * 50)
    # Выводим итоговую сумму трудозатрат
    print(f"ИТОГО трудозатрат (чел.-ч): {total_man_hours:.2f}")

    # Выводим информацию о балансе запросов
    print(f"\nИспользовано запросов: {data['REQUESTS']['USED']}")
    print(f"Осталось запросов: {data['REQUESTS']['BALANCE']}")

except requests.exceptions.RequestException as e:
    print(f"Ошибка при выполнении запроса к API: {e}")
except KeyError as e:
    print(f"Ошибка при разборе ответа API. Ожидаемый ключ не найден: {e}")
except ValueError as e:
    print(f"Ошибка преобразования данных (например, числа из строки): {e}")