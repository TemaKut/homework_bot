import os
import time
from http import HTTPStatus

import requests
import logging

import telegram
from telegram.ext import Updater


logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(filename)s, %(lineno)s, %(levelname)s, %(message)s',
    encoding='UTF-8',
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def send_message(bot, message):
    """Отправляем сообщение в чат ТГ."""
    try:
        logging.info('Пытаемся отправить сообщение.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Сообщение не отправлено! {error}')
        raise f'Ошибка отправки в телеграм сообщения: {error}'
    else:
        logging.info('Сообщение отправилось!')


def get_api_answer(current_timestamp):
    """Получаем список домашних работ за определённое время."""
    timestamp = current_timestamp or int(time.time())
    try:
        logging.info('Проверяем статус запроса к Yandex')
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})

        if response.status_code != HTTPStatus.OK:
            raise 'Статус кода яндекса != ОК'

    except Exception as error:
        logging.error(f'Ошибка получения статуса кода {error}')
        raise f'Ошибка получения статуса кода {error}'
    else:
        return response.json()


def check_response(response):
    """Проверяем получение json."""
    if not isinstance(response, dict):
        logging.error('response не является словарём.')
        raise TypeError('Ответ API отличен от словаря')

    try:
        homeworks = response['homeworks']
        if not isinstance(homeworks, list):
            logging.error('homeworks не список')
            raise 'homeworks не список'
    except Exception as error:
        logging.error('Ошибка словаря по ключу homeworks')
        raise f'Ошибка словаря по ключу homeworks {error}'

    try:
        response['current_date']
    except Exception as error:
        logging.error(f'Ошибка получения current_date {error}')
        raise f'Ошибка получения current_date {error}'
    try:
        homework = homeworks[0]
    except IndexError:
        logging.error('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')

    return homework


def parse_status(homework):
    """Проверяем статус определённой домашки."""
    if 'homework_name' not in homework:
        raise KeyError('Нет ключа "homework_name" в ответе API Yandex')

    if 'status' not in homework:
        raise Exception('Нет ключа "status" в ответе API Yandex')

    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Нет ключа в словаре статусов: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем наличие токенов."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    updater = Updater(TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logging.critical('Отсутствуют одна или несколько переменных окружения')
        raise Exception('Отсутствуют одна или несколько переменных окружения')

    while True:
        try:
            current_timestamp = current_timestamp - RETRY_TIME
            verified_response = check_response(
                get_api_answer(current_timestamp))
            message = parse_status(verified_response)
            send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            logging.info('Ошибок нет. Всё круто!')
            time.sleep(RETRY_TIME)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
