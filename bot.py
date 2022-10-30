import configparser
import telebot
from telebot import types
import sql
import datetime
import calendar

config = configparser.ConfigParser()
config.read("config.ini")
token = config["main"]["TOKEN"]
bot = telebot.TeleBot(token)
allow_add_client = 0
current_data = {}


def current_data_clear():
    # global current_data
    # current_data = {
    #     'client': None,
    #     'type_train': None,
    #     'data': None,
    #     'time': None,
    #     'price': None,
    #     'studio': None
    # }
    pass


def validate_phone(message):
    phone_number = message.contact.phone_number
    if len(phone_number) == 12 and phone_number[0:2] == '+7':
        return int(phone_number[2:])
    elif len(phone_number) == 11:
        if phone_number[0:1] == '7' or phone_number[0:1] == '8':
            return int(phone_number[1:])
    else:
        bot.send_message(message.from_user.id, "Операция не выполнена! Не верный формат номера")
        return 0


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("➕ Новый клиент")
    btn2 = types.KeyboardButton("📓 Расписание тренировок")
    btn3 = types.KeyboardButton("💰 Учет тренировок")
    markup.add(btn1, btn3)
    markup.add(btn2)
    bot.send_message(message.chat.id, text="Привет, Катюнь! Что будем делать?".format(message.from_user),
                     reply_markup=markup)


@bot.message_handler(commands=['show_all_type_train'])
def show_all_type_train(message):
    list_train = sql.list_all_train()
    markup = types.InlineKeyboardMarkup(row_width=3)
    if int(list_train[1]) > 0:
        list_button = [types.InlineKeyboardButton(f'{i["type_train"]}', callback_data=f'{i["type_train"]}')
                       for i in list_train[2]]
        markup.add(*list_button)
        bot.send_message(message.chat.id, "тест генератора", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Список тренировок пуст!')


@bot.message_handler(commands=['select_client'])
def select_client_for_operate(message):
    # сделать выбор клинета с которым будет выполняться операция (напр добавление)

    pass


@bot.message_handler(content_types=['text', 'contact'])
def get_text_messages(message):
    global allow_add_client
    if message.content_type == 'contact':
        if allow_add_client == 1:
            phone_number = validate_phone(message)
            search_client = sql.search_client(phone_number)
            if not phone_number:
                bot.send_message(message.from_user.id, "Такой клиент уже существует в базе")
            else:
                if int(search_client[1]) == 0:
                    sql.insert_client_data(phone_number,
                                           message.contact.first_name,
                                           message.contact.last_name)
                    bot.send_message(message.from_user.id, "Ага, добавил")
        else:
            bot.send_message(message.from_user.id, "Для добавления клиента нужно выбрать пункт <➕ Новый клиент>")
        allow_add_client = 0
    elif message.content_type == 'text':
        if message.text == '➕ Новый клиент':
            print('OK')
            bot.send_message(message.from_user.id, "Отправь мне контакт и я добавлю его в клиенты")
            allow_add_client = 1
        elif message.text == '📓 Расписание тренировок':
            markup = types.InlineKeyboardMarkup(row_width=2)
            button1 = types.InlineKeyboardButton("Вывести расписание", callback_data='show_schedule')
            button2 = types.InlineKeyboardButton("Добавить тренировку", callback_data='add_train')
            markup.add(button1, button2)
            bot.send_message(message.chat.id, "Поработаем с расписанием?", reply_markup=markup)
        elif message.text == '🔙 В главное меню':
            start(message)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    try:
        if call.message:
            if call.data == 'add_train':
                bot.send_message(call.message.chat.id, "Нажали вывести расписание")
                bot.send_chat_action()
            elif call.data == 'show_schedule':
                pass
    except Exception as e:
        print(repr(e))


bot.infinity_polling()
