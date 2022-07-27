import sys
import os
from os import path, remove
import time
from http import HTTPStatus

import requests
import logging
from logging.handlers import RotatingFileHandler

import telegram
from telegram.ext import Updater

if path.isfile("homework.log"):
    remove("homework.log")

logging.basicConfig(
    level=logging.INFO,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(filename)s, %(lineno)s, %(levelname)s, %(message)s',
    encoding='UTF-8',
)
logger = logging.getLogger('simple_example')
logger.setLevel(logging.DEBUG)

ch = RotatingFileHandler(
    'homework.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='UTF-8',
)
ch.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    '%(asctime)s, %(filename)s, %(lineno)s, %(levelname)s, %(message)s')
ch.setFormatter(formatter)

logger.addHandler(ch)


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
    logger.info('Пытаемся отправить сообщение.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Сообщение не отправлено! {error}')
        raise Exception(f'Ошибка отправки в телеграм сообщения: {error}')
    else:
        logger.info('Сообщение отправилось!')


def get_api_answer(current_timestamp):
    """Получаем список домашних работ за определённое время."""
    timestamp = current_timestamp or int(time.time())
    logger.info('Проверяем статус запроса к Yandex')
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
        try:
            response_json = response.json()
        except Exception as error:
            logger.error(f'Ошибка получения json {error}')
            raise Exception(f'Ошибка получения json {error}')

        if response.status_code != HTTPStatus.OK:
            raise Exception('Статус кода яндекса != ОК')

    except Exception as error:
        logger.error(f'Ошибка получения статуса кода {error}')
        raise Exception(f'Ошибка получения статуса кода {error}')
    else:
        return response_json


def check_response(response):
    """Проверяем получение json."""
    if not isinstance(response, dict):
        logger.error('response не является словарём.')
        raise TypeError('Ответ API отличен от словаря')

    try:
        homeworks = response['homeworks']
        if not isinstance(homeworks, list):
            logger.error('homeworks не список')
            raise Exception('homeworks не список')
    except Exception as error:
        logger.error('Ошибка словаря по ключу homeworks')
        raise Exception(f'Ошибка словаря по ключу homeworks {error}')

    try:
        response['current_date']
    except Exception as error:
        logger.error(f'Ошибка получения current_date {error}')
        raise Exception(f'Ошибка получения current_date {error}')

    try:
        homework = homeworks[0]
        return homework
    except IndexError:
        logger.info('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')


def parse_status(homework):
    """Проверяем статус определённой домашки."""
    if 'homework_name' not in homework:
        logger.error('Нет ключа "homework_name" в ответе API Yandex')
        raise KeyError('Нет ключа "homework_name" в ответе API Yandex')

    if 'status' not in homework:
        logger.error('Нет ключа "status" в ответе API Yandex')
        raise Exception('Нет ключа "status" в ответе API Yandex')

    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error(f'Нет ключа в словаре статусов: {homework_status}')
        raise Exception(f'Нет ключа в словаре статусов: {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем наличие токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    updater = Updater(TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens():
        logger.critical('Отсутствуют одна или несколько переменных окружения')
        sys.exit()

    while True:
        try:
            current_timestamp = current_timestamp - RETRY_TIME
            verified_response = check_response(
                get_api_answer(current_timestamp))
            message = parse_status(verified_response)
            send_message(bot, message)
        except IndexError:
            logger.info('Словили пустой список')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)

        else:
            logger.info('Ошибок нет. Всё круто!')

        finally:
            time.sleep(RETRY_TIME)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
