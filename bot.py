import configparser
import telebot
from telebot import types
import sql
import datetime

list_param_schedule = ['client', 'id', 'price', 'date', 'time', 'rent_debt', 'type_train', 'client_list']

class Client:
    def __init__(self, name, surname, phone):
        self.name = name
        self.surname = surname
        self.phone = phone


class Record_in_schedule(Client):
    def __init__(self, *args, **kwargs):
        self.list_param = ['client', 'id', 'price', 'date', 'time', 'rent_debt', 'type_train', 'client_list']
        super().__init__(
            phone=kwargs['client'],
            name=kwargs['name'],
            surname=kwargs['surname'])
        for key, value in kwargs.items():
            setattr(self, key, value)






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
def current_data_clear(process=None):
    global current_data, dict_date
    current_data = {
        'process': process,  # текущий pipeline процесса
        'operation': None,  # определенное действие в рамках процесса
        'client': None,  # клиент для одиночной трени
        'client_multi': None,  # массив клиентов для групповой трени
        'train': None,
        'date': None,
        'time': None,
        'price': None,
        'list_train': None,
        'list_client': None,
        'list_time': None,
        'is_group': None,
        'train_price': None,
        'service_data': None,
        'list_multi_select': None  # массив для хранения выбранных клиентов для групповых тренировок

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


def generator_inline(list_button):
    return [types.InlineKeyboardButton(f"{i[0]}", callback_data=f'{i[1]}') for i in list_button]


def validate_phone(message):
    phone_number = message.contact.phone_number
    if len(phone_number) == 12 and phone_number[0:2] == '+7':
        return int(phone_number[2:])
    elif len(phone_number) == 11:
        if phone_number[0:1] == '7' or phone_number[0:1] == '8':
            return int(phone_number[1:])
    else:
        bot.send_message(message.from_user.id, "Операция не выполнена! Не верный формат номера")
        return None


@bot.message_handler(commands=['button_return_to_start'])
def button_return_to_start():
    return "🔙 В главное меню"


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button_list = ("➕ Новый клиент",
                   # "📓 Расписание тренировок",
                   # "💰 Учет тренировок",
                   "➕🤸‍ Добавить перс. тренировку",
                   "➕👯 Добавить груп. тренировку",
                   # "🛠 Настройка тренировок"
                   )

    markup.add(*button_list)
    markup.add(button_return_to_start())
    bot.send_message(message.chat.id, text="Привет, Катюнь! Что будем делать?".format(message.from_user),
                     reply_markup=markup)
    current_data_clear()


@bot.message_handler(commands=['input_train_price'])
def input_train_price(message):
    current_data['operation'] = 'input_train_price'
    bot.send_message(message.chat.id, 'Укажи сумму тренировки',
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(button_return_to_start()))


@bot.message_handler(commands=['show_schedule_for_client'])
def show_schedule_for_client(message):
    pass



@bot.message_handler(commands=['schedule_query_by_date'])
def schedule_query_by_date(message):
    result = sql.schedule_query_by_date(list_param_schedule, current_data['service_data']['date_for_search'])
    pass



@bot.message_handler(commands=['show_all_type_train'])
def show_all_type_train(message, group=False):
    current_data['list_train'] = sql.list_all_train(group)[2]
    markup = types.InlineKeyboardMarkup(row_width=2)
    current_data['operation'] = 'choose_train'
    if len(current_data['list_train']) > 0:
        list_button = [
            types.InlineKeyboardButton(f"{current_data['list_train'][i]['type_train']}", callback_data=f'{i}')
            for i in range(len(current_data['list_train']))]
        markup.add(*list_button)
        bot.send_message(message.chat.id, "Доступные тренировки:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Список тренировок пуст!')


@bot.message_handler(commands=['show_list_client'])
def show_list_client(message, show_all=False):
    """Аргументом функция принимает флаг show_all
    Если True - выводится список всех клиентов из БД (main.client)
    ЕСли False - выводится список из посещавщих занятия"""
    current_data['is_group'] = False
    if show_all == False:
        current_data['list_client'] = sql.select_last_client()[2]
        text_message = 'Клиенты ранее посетившие занятия:'
    else:
        current_data['list_client'] = sql.show_all_clients()[2]
        text_message = 'Все клиенты из базы:'
    markup = types.InlineKeyboardMarkup(row_width=2)
    current_data['operation'] = 'choose_client'
    if len(current_data['list_client']) > 0:
        list_button = [types.InlineKeyboardButton(f'{current_data["list_client"][i]["name"]}', callback_data=f'{i}')
                       for i in range(len(current_data['list_client']))]
        markup.add(*list_button)
    else:
        bot.send_message(message.chat.id, 'Список клиентов пуст!')
    all_client_button = types.InlineKeyboardButton(f'Показать всех клиентов', callback_data="show_all_client_single")
    markup.add(all_client_button)
    bot.send_message(message.chat.id, f"{text_message}", reply_markup=markup)


@bot.message_handler(commands=['show_multi_list_client'])
def show_multi_list_client(message, request_all_client=False):
    current_data['operation'] = 'choose_client_multi'
    current_data['is_group'] = True
    # Заглушка
    current_data['client'] = {'client': -1}

    if current_data['list_multi_select'] is None:
        current_data['list_multi_select'] = sql.select_last_client()[2]
        for i in current_data['list_multi_select']:
            i['select'] = False
    if request_all_client:
        list_all_client = sql.show_all_clients()[2]
        selected_list = [i['client'] for i in current_data['list_multi_select'] if i['select']]
        for client in list_all_client:
            if client['client'] in selected_list:
                client['select'] = True
            current_data['list_multi_select'] = list_all_client
    markup = types.InlineKeyboardMarkup(row_width=2)
    button_list = []
    for client in current_data['list_multi_select']:
        pre_fix = '✅' if client['select'] else ''
        post_fix = '✅' if client['select'] else ''
        button_list.append(types.InlineKeyboardButton(f'{pre_fix}{client["name"]}{post_fix}',
                                                      callback_data=f'{client["client"]}'))
    markup.add(*button_list)
    markup.add(types.InlineKeyboardButton('Показать всех клиентов', callback_data='show_all_client_multi'))
    markup.add(types.InlineKeyboardButton('Подвердить ввод', callback_data='confirm_multi_list_client'))
    bot.send_message(message.chat.id, "Добавить клиентов в групповую тренировку:",
                     parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(commands=['show_time'])
def confirm_add(message, list_current_select=[]):
    list_client = sql.select_last_client()
    markup = types.InlineKeyboardMarkup(row_width=2)
    list_button = [types.InlineKeyboardButton(f'{list_client[2][i]["name"]}', callback_data=f'{i}')
                   for i in range(len(list_client[2]))]
    markup.add(*list_button)


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


@bot.message_handler(content_types=['contact'])
def add_new_client(message):
    if current_data['operation'] == 'add_client':
        phone_number = validate_phone(message)
        if phone_number is not None:
            search_client = sql.search_client(phone_number)
            if int(search_client[1]) != 0:
                bot.send_message(message.from_user.id, "Такой клиент уже существует в базе")
            else:
                result = sql.insert_client_data(phone_number,
                                                message.contact.first_name,
                                                message.contact.last_name)
                if result['failed'] == 0:
                    bot.send_message(message.from_user.id, "Ага, добавил")
                else:
                    bot.send_message(message.from_user.id, "Ошибка добавления")
        else:
            start(message)

    else:
        bot.send_message(message.from_user.id, "Для добавления клиента нужно выбрать пункт <➕ Новый клиент>")


@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    if message.content_type == 'text':
        if message.text == '➕ Новый клиент':
            bot.send_message(message.from_user.id, "Отправь мне контакт и я добавлю его в клиенты")
            current_data['operation'] = 'add_client'
        elif message.text == '📓 Расписание тренировок':
            markup = types.InlineKeyboardMarkup(row_width=1)
            list_button = [("Вывести расписание на сегодня", 'show_schedule_today'),
                           ("Вывести расписание на дату", 'show_schedule_date'),
                           ("Вывести расписание клиента", 'show_schedule_client')
                           ]
            markup.add(*generator_inline(list_button))
            bot.send_message(message.chat.id, "Поработаем с расписанием?", reply_markup=markup)
        elif message.text == '🔙 В главное меню':
            start(message)
        elif message.text == '➕🤸‍ Добавить перс. тренировку':
            current_data_clear('add_single_train_in_schedule')
            show_list_client(message)
        elif message.text == '➕👯 Добавить груп. тренировку':
            current_data_clear('add_multi_train_in_schedule')
            show_all_type_train(message, True)
        elif message.text == '📑 Список тренировок клиента':
            current_data_clear('list_train_for_client')
            show_list_client(message)
        elif current_data['operation'] == 'input_train_price':
            if message.text.isdigit():
                current_data['train_price'] = int(message.text)
                confirm_add(message)
            else:
                bot.send_message(message.chat.id, 'Введено не корректное значение!')
                input_train_price(message)


@bot.message_handler(commands=['confirm_add'])
def confirm_add(message):
    current_data['operation'] = 'confirm_add'
    markup = types.InlineKeyboardMarkup()
    confirm = types.InlineKeyboardButton("✅ Добавить", callback_data='approve_add')
    cancel = types.InlineKeyboardButton("❌ Отменить", callback_data='cancel_add')
    markup.add(confirm, cancel)
    # if len(current_data['client_multi']) > 1:
    text_client = "".join([f'{i + 1}. {current_data["client_multi"][i][1]}\n'
                           for i in range(len(current_data['client_multi']))])
    # else:
    #     text_client = f'Клиент *{current_data["client_multi"][0][1]}*\n'
    bot.send_message(message.chat.id, f"Добавить тренировку *{current_data['train']['type_train']}*\n"
                                      f"{text_client}"
                                      f"На дату: *{current_data['date']}*\n"
                                      f"На время: *{current_data['time']}*\n"
                                      f"Цена тренировки *{current_data['train_price']}*?",
                     parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        if current_data['process'] == 'add_single_train_in_schedule':
            if current_data['operation'] == 'choose_client':
                if call.data == 'show_all_client_single':
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_list_client(call.message, True)
                else:
                    current_data['client'] = current_data['list_client'][int(call.data)]
                    current_data['client_multi'] = [(current_data['client']['client'],
                                                     f"{current_data['client']['name']} {current_data['client']['surname']}")]
                    show_all_type_train(call.message)
            elif current_data['operation'] == 'choose_train':
                current_data['train'] = current_data['list_train'][int(call.data)]
                current_data['process'] = None
                show_date(call.message)
        elif current_data['process'] == 'add_multi_train_in_schedule':
            if current_data['operation'] == 'choose_train':
                current_data['train'] = current_data['list_train'][int(call.data)]
                show_multi_list_client(call.message)
            elif current_data['operation'] == 'choose_client_multi':
                if call.data == 'confirm_multi_list_client':
                    current_data['client_multi'] = [(i['client'], f'{i["name"]} {i["surname"]}')
                                                    for i in current_data['list_multi_select'] if i['select']]
                    current_data['process'] = None
                    show_date(call.message)
                elif call.data == 'show_all_client_multi':
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_multi_list_client(call.message, True)
                else:
                    for i in current_data['list_multi_select']:
                        if i['client'] == int(call.data):
                            i['select'] = not i['select']
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_multi_list_client(call.message)
        else:
            if current_data['operation'] == 'choose_date':
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
                input_train_price(call.message)
            elif current_data['operation'] == 'confirm_add':
                if call.data == 'approve_add':
                    if current_data['client_multi'] is None:
                        current_data['client_multi'] = [current_data['client']]
                    elif current_data['client'] is None:
                        current_data['client'] = [i for i in current_data]
                    if current_data['client_multi'] is None:
                        current_data['client_multi'] = [x['client'] for x in current_data['list_multi_select'] if
                                                        x['select']]

                    insert_data(message=call.message,
                                date=current_data['date'],
                                client=current_data['client']['client'],
                                client_list=f"{{{','.join([str(i[0]) for i in current_data['client_multi']])}}}",
                                # client_list=current_data['client_multi'],
                                is_group=current_data['is_group'],
                                time=current_data['time'],
                                rent_debt=current_data['train']['rent_debt'],
                                type_train=current_data['train']['type_train'],
                                train_price=current_data['train_price']
                                )
                elif call.data == 'cancel_add':
                    bot.send_message(call.message.chat.id, "Действие отменено!")
                    start(call.message)






def insert_data(message, date, client, client_list, time, rent_debt, type_train, is_group, train_price):
    try:
        result_request = sql.insert_in_schedule(date, client, client_list, time, rent_debt, type_train, is_group,
                                                train_price)
        bot.send_message(message.chat.id, "✅Запись добавлена!✅")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка добавления записи!❌")


bot.infinity_polling()
