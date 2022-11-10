import configparser
import telebot
from telebot import types
import sql
import datetime

config = configparser.ConfigParser()
config.read("config.ini")
token = config["main"]["TOKEN"]
bot = telebot.TeleBot(token)
allow_add_client = 0
current_data = {}
current_operation = None
dict_date = {}
work_hour = {'start': 7, 'end': 23}


# инициализация структур и сброс к дефолту
def current_data_clear():
    global current_data, dict_date
    current_data = {
        'operation': None,
        'client': None,
        'train': None,
        'date': None,
        'time': None,
        'price': None,
        'list_train': None,
        'list_client': None,
        'list_time': None
    }

    dict_date = {
        '1': None,
        '2': None,
        '3': None,
        '4': None,
        '5': None,
        '6': None,
        '7': None
    }


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
    btn4 = types.KeyboardButton("➕📅 Добавить тренировку")
    markup.add(btn1, btn4)
    markup.add(btn2, btn3)
    bot.send_message(message.chat.id, text="Привет, Катюнь! Что будем делать?".format(message.from_user),
                     reply_markup=markup)
    current_data_clear()


@bot.message_handler(commands=['show_all_type_train'])
def show_all_type_train(message):
    current_data['list_train'] = sql.list_all_train()[2]
    markup = types.InlineKeyboardMarkup(row_width=3)
    current_data['operation'] = 'choose_train'
    if len(current_data['list_train']) > 0:

        list_button = [types.InlineKeyboardButton(f"{current_data['list_train'][i]['type_train']}", callback_data=f'{i}')
                       for i in range(len(current_data['list_train']))]
        markup.add(*list_button)
        bot.send_message(message.chat.id, "Доступные тренировки:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Список тренировок пуст!')


@bot.message_handler(commands=['show_list_client'])
def show_list_client(message):
    list_client = sql.select_last_client()
    markup = types.InlineKeyboardMarkup(row_width=2)
    current_data['operation'] = 'choose_client'
    if int(list_client[1]) > 0:
        current_data['list_client'] = list_client[2]
        list_button = [types.InlineKeyboardButton(f'{list_client[2][i]["name"]}', callback_data=f'{i}')
                       for i in range(len(list_client[2]))]
        markup.add(*list_button)
        bot.send_message(message.chat.id, "Все клиенты:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Список клиентов пуст!')


@bot.message_handler(commands=['show_date'])
def show_date(message, date=datetime.date.today()):
    global dict_date, current_data
    current_data['operation'] = 'choose_date'

    markup = types.InlineKeyboardMarkup(row_width=5)
    button_prev_week = types.InlineKeyboardButton(f'<< неделя', callback_data=f'prev_week')
    button_current_week = types.InlineKeyboardButton(f'Эта неделя', callback_data=f'current_week')
    button_next_week = types.InlineKeyboardButton(f'неделя >>', callback_data=f'next_week')
    markup.add(button_prev_week, button_current_week, button_next_week)

    weekday = date.isoweekday()
    first_day_cur_week = date - datetime.timedelta(days=weekday - 1)
    date_list = [first_day_cur_week + datetime.timedelta(days=d) for d in range(7)]
    for i in range(7):
        dict_date[f'{i}'] = date_list[i]
    list_button = [types.InlineKeyboardButton(f'{date_list[i]:%d %a}',
                                              callback_data=f'{i}') for i in range(7)]

    markup.add(*list_button)
    bot.send_message(message.chat.id, "Выбор даты для расписания:", parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(commands=['show_time'])
def show_available_time(message):
    current_data['operation'] = 'choose_time'
    time_list = [datetime.time(i, 0) for i in range(work_hour['start'], work_hour['end'])]
    list_not_available = sql.select_time_at_data(current_data['date'])
    result = sorted(list(set(time_list) ^ set(list_not_available)))
    current_data['list_time'] = result
    list_button = [types.InlineKeyboardButton(f'{result[i]:%H:%M}',
                                              callback_data=f'{i}') for i in range(len(result))]
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(*list_button)
    bot.send_message(message.chat.id, f'Выбор времени на дату: {current_data["operation"]}', reply_markup=markup)


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
        elif message.text == '➕📅 Добавить тренировку':
            show_list_client(message)



@bot.message_handler(commands=['show_time'])
def confirm_add(message):
    current_data['operation'] = 'confirm_add'
    markup = types.InlineKeyboardMarkup()
    confirm = types.InlineKeyboardButton("✅ Добавить", callback_data='approve_add')
    cancel = types.InlineKeyboardButton("❌ Отменить", callback_data='cancel_add')
    markup.add(confirm, cancel)
    bot.send_message(message.chat.id, f"Добавить тренировку *{current_data['train']['type_train']}*\n"
                                      f"Клиент *{current_data['client']['name']}* *{current_data['client']['surname']}*\n"
                                      f"На дату: *{current_data['date']}*\n"
                                      f"На время: *{current_data['time']}*?",
                     parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        if current_data['operation'] == 'choose_client':
            current_data['client'] = current_data['list_client'][int(call.data)]
            show_all_type_train(call.message)
        elif current_data['operation'] == 'choose_train':
            current_data['train'] = current_data['list_train'][int(call.data)]
            show_date(call.message)
        elif current_data['operation'] == 'choose_date':
            if call.data == 'prev_week':
                bot.delete_message(call.message.chat.id, call.message.id)
                show_date(call.message, dict_date['0'] - datetime.timedelta(days=7))
            elif call.data == 'current_week':
                bot.delete_message(call.message.chat.id, call.message.id)
                show_date(call.message)
            elif call.data == 'next_week':
                bot.delete_message(call.message.chat.id, call.message.id)
                show_date(call.message, dict_date['0'] + datetime.timedelta(days=7))
            elif len(call.data) == 1:
                current_data['date'] = dict_date[call.data]
                show_available_time(call.message)
        elif current_data['operation'] == 'choose_time':
            current_data['time'] = current_data['list_time'][int(call.data)]
            confirm_add(call.message)
        elif current_data['operation'] == 'confirm_add':
            if call.data == 'approve_add':
                try:
                    result_request = sql.insert_in_schedule(date=current_data['date'],
                                                            client_id=current_data['client']['client'],
                                                            time=current_data['time'],
                                                            rent_debt=current_data['train']['rent_debt'],
                                                            type_train=current_data['train']['type_train'])
                    bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                except:
                    bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
            elif call.data == 'cancel_add':
                start(call.message)


bot.infinity_polling()
