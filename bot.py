import logging
import telebot
import sql
import datetime

from telebot import types
from src.Kate_Fit_Notes.domain import (
    parse_prepaid,
    parse_price,
    price_per_train,
    shift_week,
    time_choice_caption,
    week_days,
)
from src.Kate_Fit_Notes.session import SessionStore
from src.Kate_Fit_Notes.services.booking import BookingService
from src.Kate_Fit_Notes.services.clients import ClientService
from src.Kate_Fit_Notes.services.errors import (
    DuplicateClientError,
    EmptyParticipantsError,
    InvalidPhoneError,
    InvalidPrepaidError,
    MultiplePrepaidError,
    SlotTakenError,
)
from src.Kate_Fit_Notes.services.prepaid import PrepaidService
from src.Kate_Fit_Notes.services.report import ReportService
from src.Kate_Fit_Notes.settings import load_settings

logging.basicConfig(level=logging.INFO)
_settings = load_settings()
bot = telebot.TeleBot(_settings.telegram_token)
client_service = ClientService(sql.repository)
booking_service = BookingService(sql.repository)
prepaid_service = PrepaidService(sql.repository)
report_service = ReportService(sql.repository)
sessions = SessionStore()
work_hour = {'start': 7, 'end': 23}


def generator_inline(list_button):
    return [types.InlineKeyboardButton(f"{i[0]}", callback_data=f'{i[1]}') for i in list_button]


@bot.message_handler(commands=['button_return_to_start'])
def button_return_to_start():
    return "🔙 В главное меню"


@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    button_list = ("➕ Новый клиент",
                   "Добавить оплату",
                   # "📓 Расписание тренировок",
                   "💰 Отчет по тренировкам",
                   "➕🤸‍ Добавить перс. тренировку",
                   "➕👯 Добавить груп. тренировку",
                   # "🛠 Настройка тренировок"
                   )

    markup.add(*button_list)
    markup.add(button_return_to_start())
    bot.send_message(message.chat.id, text="Привет, Катюнь! Что будем делать?".format(message.from_user),
                     reply_markup=markup)
    sessions.clear(message.chat.id)


@bot.message_handler(commands=['universal_text_input'])
def universal_text_input(text_message, command, message):
    state = sessions.get(message.chat.id)
    state.operation = command
    bot.send_message(message.chat.id, text_message,
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(button_return_to_start()))


@bot.message_handler(commands=['input_train_price'])
def input_train_price(message):
    state = sessions.get(message.chat.id)
    state.operation = 'input_train_price'

    additional_text = ""
    if not state.is_group:
        try:
            hint = booking_service.suggest_personal_price(
                state.client['client'],
                state.train['id'],
            )
        except MultiplePrepaidError as exc:
            bot.send_message(
                message.chat.id,
                f"!!!У клиента {exc.count} не закрытых тренировок!!!id {exc.ids}",
            )
            bot.send_message(
                message.chat.id,
                'Запись не будет добавлена!',
                reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                    button_return_to_start()
                ),
            )
            start(message)
            return
        if hint.prepaid_price is not None:
            additional_text = f"Стоимость предоплаченных тренировок {hint.prepaid_price}"
        elif hint.last_prices:
            additional_text = 'Стоимость последних тренировок:\n'
            for row in hint.last_prices:
                additional_text += f"\n{row['price']}"

    bot.send_message(message.chat.id, f'Укажи сумму тренировки\n{additional_text}',
                     reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(button_return_to_start()))


@bot.message_handler(commands=['show_schedule_for_client'])
def show_schedule_for_client(message):
    pass


@bot.message_handler(commands=['show_all_type_train'])
def show_all_type_train(message, group=False):
    state = sessions.get(message.chat.id)
    state.list_train = sql.list_all_train(group)
    markup = types.InlineKeyboardMarkup(row_width=2)
    state.operation = 'choose_train'
    if len(state.list_train) > 0:
        list_button = [
            types.InlineKeyboardButton(f"{state.list_train[i]['type_train']}", callback_data=f'{i}')
            for i in range(len(state.list_train))]
        markup.add(*list_button)
        bot.send_message(message.chat.id, "Доступные тренировки:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, 'Список тренировок пуст!')


@bot.message_handler(commands=['show_list_client'])
def show_list_client(message, show_all=False):
    """Аргументом функция принимает флаг show_all
    Если True - выводится список всех клиентов из БД (main.client)
    ЕСли False - выводится список из посещавщих занятия"""
    state = sessions.get(message.chat.id)
    state.is_group = False

    if not show_all:
        state.list_client = client_service.list_recent()
        text_message = 'Клиенты ранее посетившие занятия:'
    else:
        state.list_client = client_service.list_all()
        text_message = 'Все клиенты из базы:'
    markup = types.InlineKeyboardMarkup(row_width=2)
    state.operation = 'choose_client'
    if len(state.list_client) > 0:
        list_button = [types.InlineKeyboardButton(f'{state.list_client[i]["name"]}', callback_data=f'{i}')
                       for i in range(len(state.list_client))]
        markup.add(*list_button)
    else:
        bot.send_message(message.chat.id, 'Список клиентов пуст!')
    all_client_button = types.InlineKeyboardButton(f'Показать всех клиентов', callback_data="show_all_client_single")
    markup.add(all_client_button)
    bot.send_message(message.chat.id, f"{text_message}", reply_markup=markup)


@bot.message_handler(commands=['show_multi_list_client'])
def show_multi_list_client(message, request_all_client=False):
    state = sessions.get(message.chat.id)
    state.operation = 'choose_client_multi'
    state.is_group = True
    # Заглушка
    state.client = {'client': -1}

    if state.list_multi_select is None:
        state.list_multi_select = client_service.list_recent()
        for i in state.list_multi_select:
            i['select'] = False
    if request_all_client:
        list_all_client = client_service.list_all()
        selected_list = [i['client'] for i in state.list_multi_select if i['select']]
        for client in list_all_client:
            if client['client'] in selected_list:
                client['select'] = True
            state.list_multi_select = list_all_client
    markup = types.InlineKeyboardMarkup(row_width=2)
    button_list = []
    for client in state.list_multi_select:
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
    list_button = [types.InlineKeyboardButton(f'{list_client[i]["name"]}', callback_data=f'{i}')
                   for i in range(len(list_client))]
    markup.add(*list_button)


@bot.message_handler(commands=['show_date'])
def show_date(message, date=None):
    state = sessions.get(message.chat.id)

    if date is None:
        date = datetime.date.today()

    state.operation = 'choose_date'

    markup = types.InlineKeyboardMarkup(row_width=5)
    button_prev_week = types.InlineKeyboardButton(f'<< неделя', callback_data=f'prev_week')
    button_current_week = types.InlineKeyboardButton(f'Эта неделя', callback_data=f'current_week')
    button_next_week = types.InlineKeyboardButton(f'неделя >>', callback_data=f'next_week')
    markup.add(button_prev_week, button_current_week, button_next_week)

    date_list = week_days(date)
    for i in range(7):
        state.week_dates[f'{i}'] = date_list[i]
    list_button = [types.InlineKeyboardButton(f'{date_list[i]:%d %a}',
                                              callback_data=f'{i}') for i in range(7)]
    markup.add(*list_button)
    bot.send_message(message.chat.id, "Выбор даты для расписания:", parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(commands=['show_time'])
def show_available_time(message):
    state = sessions.get(message.chat.id)
    state.operation = 'choose_time'
    result = booking_service.list_available_slots(state.date)
    state.list_time = result
    list_button = [types.InlineKeyboardButton(f'{result[i]:%H:%M}',
                                              callback_data=f'{i}') for i in range(len(result))]
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(*list_button)
    bot.send_message(message.chat.id, time_choice_caption(state.date), reply_markup=markup)


@bot.message_handler(content_types=['text', 'contact'])
def get_text_messages(message):
    state = sessions.get(message.chat.id)
    if message.content_type == 'contact':
        if state.allow_add_client:
            try:
                client_service.create(
                    message.contact.phone_number,
                    message.contact.first_name,
                    message.contact.last_name,
                )
                bot.send_message(message.from_user.id, "Ага, добавил")
            except InvalidPhoneError:
                bot.send_message(message.from_user.id, "Операция не выполнена! Не верный формат номера")
            except DuplicateClientError:
                bot.send_message(message.from_user.id, "Такой клиент уже существует в базе")
        else:
            bot.send_message(message.from_user.id, "Для добавления клиента нужно выбрать пункт <➕ Новый клиент>")
        state.allow_add_client = False
    elif message.content_type == 'text':
        if message.text == '➕ Новый клиент':
            logging.info("Выбран пункт «Новый клиент»")
            bot.send_message(message.from_user.id, "Отправь мне контакт и я добавлю его в клиенты")
            state.allow_add_client = True
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
            sessions.clear(message.chat.id, 'add_single_train_in_schedule')
            show_list_client(message)
        elif message.text == '➕👯 Добавить груп. тренировку':
            sessions.clear(message.chat.id, 'add_multi_train_in_schedule')
            show_all_type_train(message, True)
        elif message.text == '📑 Список тренировок клиента':
            sessions.clear(message.chat.id, 'list_train_for_client')
            show_list_client(message)
        elif message.text == '💰 Отчет по тренировкам':
            try:
                result = report_service.monthly_report()
                if not result:
                    text = (
                        "Дата:     *—*\n"
                        "Прибыль:  *0*\n"
                        "Аренда:   *0*\n"
                        "Всего:    *0*\n"
                        "========================="
                    )
                else:
                    text = "\n".join(
                        [
                            f'Дата:     *{_["month"].strftime("%m.%Y")}*\n'
                            f'Прибыль:  *{_["income"]}*\n'
                            f'Аренда:   *{_["sum_rent"]}*\n'
                            f'Всего:    *{_["total_sum"]}*\n'
                            f'========================='
                            for _ in result
                        ]
                    )
                bot.send_message(message.chat.id, text=text, parse_mode='Markdown')
            except Exception:
                logging.exception("Ошибка отчёта по тренировкам")
                bot.send_message(message.chat.id, "❌ Ошибка формирования отчёта!❌")
            start(message)
        elif message.text == "Добавить оплату":
            sessions.clear(message.chat.id, "add_money_in_accounting")
            show_list_client(message)

        elif state.operation == 'input_train_price':
            parsed_price = parse_price(message.text)
            if parsed_price is not None:
                state.train_price = parsed_price
                confirm_add(message)
            else:
                bot.send_message(message.chat.id, 'Введено не корректное значение!')
                input_train_price(message)

        state = sessions.get(message.chat.id)
        match state.process, state.operation:
            case 'add_money_in_accounting', 'total_summ_and_number_train':

                prepaid = parse_prepaid(message.text)
                if prepaid is not None:
                    state.summ, state.count_train = prepaid
                    confirm_add_in_accounting(message)
                else:
                    universal_text_input(
                        text_message=f"Не корректно введено значение! {message.text}\n"
                                     "Введи общую сумму и количество тренировок\n"
                                     "Например:<1000 10>",
                        command='total_summ_and_number_train',
                        message=message
                    )


@bot.message_handler(commands=['confirm_add'])
def confirm_add(message):
    state = sessions.get(message.chat.id)
    state.operation = 'confirm_add'
    markup = types.InlineKeyboardMarkup()
    confirm = types.InlineKeyboardButton("✅ Добавить", callback_data='approve_add')
    cancel = types.InlineKeyboardButton("❌ Отменить", callback_data='cancel_add')
    markup.add(confirm, cancel)
    if state.is_group and state.client_multi:
        text_client = "".join([f'{i + 1}. {state.client_multi[i][1]}\n'
                               for i in range(len(state.client_multi))])
    elif state.client:
        client = state.client
        text_client = f"Клиент *{client.get('name')} {client.get('surname')}*\n"
    else:
        text_client = ""

    additonal_info = ""
    if not state.is_group and state.client:
        remaining = booking_service.remaining_prepaid_sessions(
            state.client['client'],
            state.train['id'],
        )
        if remaining is not None:
            additonal_info = (f"\n!У клиента есть пред оплаченные тренировки: "
                              f"{remaining}\n шт!")

    bot.send_message(message.chat.id, f"Добавить тренировку *{state.train['type_train']}*\n"
                                      f"{text_client}"
                                      f"На дату: *{state.date}*\n"
                                      f"На время: *{state.time}*\n"
                                      f"Цена тренировки *{state.train_price}*?"
                                      f"{additonal_info}",
                     parse_mode='Markdown', reply_markup=markup)


@bot.message_handler(commands=['confirm_add_accounting'])
def confirm_add_in_accounting(message):
    state = sessions.get(message.chat.id)
    state.operation = 'confirm_add_accounting'
    markup = types.InlineKeyboardMarkup()
    confirm = types.InlineKeyboardButton("✅ Добавить", callback_data='approve_add')
    cancel = types.InlineKeyboardButton("❌ Отменить", callback_data='cancel_add')
    markup.add(confirm, cancel)
    bot.send_message(message.chat.id,
                     f"Добавление предоплаты\n"
                     f"Клиент: {state.client['name']} {state.client['surname']}\n"
                     f"Тренировка: {state.train['type_train']}\n"
                     f"Общая сумма: {state.summ}\n"
                     f"Количество тренировок: {state.count_train}\n"
                     f"Стоимость 1 тренировки: {price_per_train(state.summ, state.count_train)}\n",
                     parse_mode='Markdown', reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        state = sessions.get(call.message.chat.id)
        process = state.process
        operation = state.operation
        if process == 'add_single_train_in_schedule' and operation in (
            'choose_client',
            'choose_train',
        ):
            if operation == 'choose_client':
                match call.data:
                    case 'show_all_client_single':
                        bot.delete_message(call.message.chat.id, call.message.id)
                        show_list_client(call.message, True)
                    case _:
                        state.client = state.list_client[int(call.data)]
                        show_all_type_train(call.message)

            elif operation == 'choose_train':
                state.train = state.list_train[int(call.data)]
                show_date(call.message)

        elif process == 'add_multi_train_in_schedule' and operation in (
            'choose_train',
            'choose_client_multi',
        ):
            if operation == 'choose_train':
                state.train = state.list_train[int(call.data)]
                show_multi_list_client(call.message)
            elif operation == 'choose_client_multi':
                if call.data == 'confirm_multi_list_client':
                    state.client_multi = [(i['client'], f'{i["name"]} {i["surname"]}')
                                          for i in state.list_multi_select if i['select']]
                    if not state.client_multi:
                        bot.send_message(
                            call.message.chat.id,
                            "Нужно выбрать хотя бы одного клиента",
                        )
                        return
                    show_date(call.message)
                elif call.data == 'show_all_client_multi':
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_multi_list_client(call.message, True)
                else:
                    for i in state.list_multi_select:
                        if i['client'] == int(call.data):
                            i['select'] = not i['select']
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_multi_list_client(call.message)

        elif process == "add_money_in_accounting":
            match operation:

                case "choose_client":
                    match call.data:
                        case 'show_all_client_single':
                            bot.delete_message(call.message.chat.id, call.message.id)
                            show_list_client(call.message, True)
                        case _:
                            state.client = state.list_client[int(call.data)]
                            state.client_multi = [
                                (
                                    state.client['client'],
                                    f"{state.client['name']} {state.client['surname']}"
                                )
                            ]
                            show_all_type_train(call.message)

                case 'choose_train':
                    state.train = state.list_train[int(call.data)]
                    universal_text_input(
                        text_message="Введи общую сумму и количество тренировок\n"
                                     "Например:<1000 10>",
                        command='total_summ_and_number_train',
                        message=call.message
                    )
                case 'confirm_add_accounting':
                    match call.data:
                        case 'approve_add':
                            try:
                                prepaid_service.add_package(
                                    client_id=state.client['client'],
                                    type_train_id=state.train['id'],
                                    summ=state.summ,
                                    count=state.count_train,
                                )
                                bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                            except InvalidPrepaidError:
                                bot.send_message(call.message.chat.id, "❌ Некорректные сумма или количество!❌")
                            except MultiplePrepaidError:
                                bot.send_message(call.message.chat.id, "❌ У клиента уже есть незакрытая предоплата!❌")
                            except Exception:
                                logging.exception("Ошибка добавления предоплаты")
                                bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                        case 'cancel_add':
                            bot.send_message(call.message.chat.id, "Действие отменено!")
                            start(call.message)


        else:
            if state.operation == 'choose_date':
                if call.data == 'prev_week':
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_date(call.message, shift_week(state.week_dates['0'], 'prev'))
                elif call.data == 'current_week':
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_date(call.message, shift_week(state.week_dates['0'], 'current'))
                elif call.data == 'next_week':
                    bot.delete_message(call.message.chat.id, call.message.id)
                    show_date(call.message, shift_week(state.week_dates['0'], 'next'))
                elif len(call.data) == 1:
                    state.date = state.week_dates[call.data]
                    show_available_time(call.message)
            elif state.operation == 'choose_time':
                state.time = state.list_time[int(call.data)]
                input_train_price(call.message)
            elif state.operation == 'confirm_add':
                if call.data == 'approve_add':
                    if not state.is_group:
                        try:
                            booking_service.book_personal(
                                client_id=state.client['client'],
                                type_train_id=state.train['id'],
                                session_date=state.date,
                                session_time=state.time,
                                price=state.train_price,
                            )
                            bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                        except SlotTakenError:
                            bot.send_message(call.message.chat.id, "❌ Слот уже занят!❌")
                        except MultiplePrepaidError:
                            bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                        except Exception:
                            logging.exception("Ошибка добавления записи в расписание")
                            bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                    else:
                        try:
                            booking_service.book_group(
                                client_ids=[i[0] for i in state.client_multi or []],
                                type_train_id=state.train['id'],
                                session_date=state.date,
                                session_time=state.time,
                                price=state.train_price,
                            )
                            bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                        except SlotTakenError:
                            bot.send_message(call.message.chat.id, "❌ Слот уже занят!❌")
                        except EmptyParticipantsError:
                            bot.send_message(call.message.chat.id, "❌ Нужно выбрать хотя бы одного клиента!❌")
                        except Exception:
                            logging.exception("Ошибка добавления групповой записи в расписание")
                            bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                elif call.data == 'cancel_add':
                    bot.send_message(call.message.chat.id, "Действие отменено!")
                    start(call.message)
            elif call.data == 'cancel_add':
                bot.send_message(call.message.chat.id, "Действие отменено!")
                start(call.message)


#             Отдельные команды


def insert_data(message, date, client, client_list, time, rent_debt, type_train, is_group, train_price, type_train_id,
                set_is_complete_true):
    try:
        sql.insert_in_schedule(date, client, client_list, time, rent_debt, type_train, is_group,
                                                train_price, type_train_id, set_is_complete_true)

        bot.send_message(message.chat.id, "✅Запись добавлена!✅")
    except Exception:
        logging.exception("Ошибка добавления записи в расписание")
        bot.send_message(message.chat.id, "❌ Ошибка добавления записи!❌")


bot.infinity_polling()
