"""Telegram-адаптер: хендлеры вызывают сервисы. Импорт не стартует polling."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

import telebot

from src.Kate_Fit_Notes.bot_ui import (
    BACK_TO_MENU,
    GREETING,
    MENU_ADD_PAYMENT,
    MENU_GROUP,
    MENU_NEW_CLIENT,
    MENU_PERSONAL,
    MENU_REPORT,
    back_to_menu_markup,
    booking_confirm_text,
    client_list_markup,
    confirm_markup,
    main_menu_markup,
    multi_client_markup,
    prepaid_confirm_text,
    price_prompt_text,
    report_text,
    schedule_menu_markup,
    slots_markup,
    time_slots_caption,
    train_types_markup,
    week_markup,
)
from src.Kate_Fit_Notes.domain import parse_prepaid, parse_price, shift_week, week_days
from src.Kate_Fit_Notes.repository import KateFitRepository, PostgresRepository
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
from src.Kate_Fit_Notes.session import SessionStore
from src.Kate_Fit_Notes.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def _as_int(raw: str) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _find_client(rows: list[dict] | None, raw: str) -> dict | None:
    client_id = _as_int(raw)
    if client_id is None:
        return None
    for row in rows or []:
        if row.get("client") == client_id:
            return row
    return None


def _find_train(rows: list[dict] | None, raw: str) -> dict | None:
    train_id = _as_int(raw)
    if train_id is None:
        return None
    for row in rows or []:
        if row.get("id") == train_id:
            return row
    return None


def _find_slot(slots: list | None, raw: str) -> datetime.time | None:
    for slot in slots or []:
        if slot.strftime("%H:%M") == raw:
            return slot
    return None


def _parse_iso_date(raw: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


@dataclass
class BotApp:
    bot: telebot.TeleBot
    sessions: SessionStore
    client_service: ClientService
    booking_service: BookingService
    prepaid_service: PrepaidService
    report_service: ReportService

    def register_handlers(self) -> None:
        self.bot.message_handler(commands=["start"])(self.start)
        self.bot.message_handler(content_types=["text", "contact"])(self.get_text_messages)
        self.bot.callback_query_handler(func=lambda call: True)(self.callback_inline)

    def start(self, message) -> None:
        self.bot.send_message(message.chat.id, GREETING, reply_markup=main_menu_markup())
        self.sessions.clear(message.chat.id)

    def universal_text_input(self, text_message: str, command: str, message) -> None:
        state = self.sessions.get(message.chat.id)
        state.operation = command
        self.bot.send_message(message.chat.id, text_message, reply_markup=back_to_menu_markup())

    def input_train_price(self, message) -> None:
        state = self.sessions.get(message.chat.id)
        state.operation = "input_train_price"
        additional_text = ""
        if not state.is_group:
            try:
                hint = self.booking_service.suggest_personal_price(
                    state.client["client"],
                    state.train["id"],
                )
            except MultiplePrepaidError as exc:
                self.bot.send_message(
                    message.chat.id,
                    f"!!!У клиента {exc.count} не закрытых тренировок!!!id {exc.ids}",
                )
                self.bot.send_message(
                    message.chat.id,
                    "Запись не будет добавлена!",
                    reply_markup=back_to_menu_markup(),
                )
                self.start(message)
                return
            if hint.prepaid_price is not None:
                additional_text = f"Стоимость предоплаченных тренировок {hint.prepaid_price}"
            elif hint.last_prices:
                additional_text = "Стоимость последних тренировок:\n"
                for row in hint.last_prices:
                    additional_text += f"\n{row['price']}"
        self.bot.send_message(
            message.chat.id,
            price_prompt_text(additional_text),
            reply_markup=back_to_menu_markup(),
        )

    def show_all_type_train(self, message, group: bool = False) -> None:
        state = self.sessions.get(message.chat.id)
        state.list_train = self.booking_service.list_train_types(group)
        state.operation = "choose_train"
        if state.list_train:
            self.bot.send_message(
                message.chat.id,
                "Доступные тренировки:",
                reply_markup=train_types_markup(state.list_train),
            )
        else:
            self.bot.send_message(message.chat.id, "Список тренировок пуст!")

    def show_list_client(self, message, show_all: bool = False) -> None:
        state = self.sessions.get(message.chat.id)
        state.is_group = False
        if not show_all:
            state.list_client = self.client_service.list_recent()
            text_message = "Клиенты ранее посетившие занятия:"
        else:
            state.list_client = self.client_service.list_all()
            text_message = "Все клиенты из базы:"
        state.operation = "choose_client"
        if not state.list_client:
            self.bot.send_message(message.chat.id, "Список клиентов пуст!")
        self.bot.send_message(
            message.chat.id,
            text_message,
            reply_markup=client_list_markup(state.list_client or []),
        )

    def show_multi_list_client(self, message, request_all_client: bool = False) -> None:
        state = self.sessions.get(message.chat.id)
        state.operation = "choose_client_multi"
        state.is_group = True
        state.client = {"client": -1}
        if state.list_multi_select is None:
            state.list_multi_select = self.client_service.list_recent()
            for client in state.list_multi_select:
                client["select"] = False
        if request_all_client:
            list_all_client = self.client_service.list_all()
            selected_list = [client["client"] for client in state.list_multi_select if client["select"]]
            for client in list_all_client:
                if client["client"] in selected_list:
                    client["select"] = True
            state.list_multi_select = list_all_client
        self.bot.send_message(
            message.chat.id,
            "Добавить клиентов в групповую тренировку:",
            parse_mode="Markdown",
            reply_markup=multi_client_markup(state.list_multi_select),
        )

    def show_date(self, message, date=None) -> None:
        state = self.sessions.get(message.chat.id)
        if date is None:
            date = datetime.date.today()
        state.operation = "choose_date"
        date_list = week_days(date)
        for index, day in enumerate(date_list):
            state.week_dates[f"{index}"] = day
        self.bot.send_message(
            message.chat.id,
            "Выбор даты для расписания:",
            parse_mode="Markdown",
            reply_markup=week_markup(date_list),
        )

    def show_available_time(self, message) -> None:
        state = self.sessions.get(message.chat.id)
        state.operation = "choose_time"
        result = self.booking_service.list_available_slots(state.date)
        state.list_time = result
        self.bot.send_message(
            message.chat.id,
            time_slots_caption(state.date),
            reply_markup=slots_markup(result),
        )

    def get_text_messages(self, message) -> None:
        state = self.sessions.get(message.chat.id)
        if message.content_type == "contact":
            if state.allow_add_client:
                try:
                    self.client_service.create(
                        message.contact.phone_number,
                        message.contact.first_name,
                        message.contact.last_name,
                    )
                    self.bot.send_message(message.from_user.id, "Ага, добавил")
                except InvalidPhoneError:
                    self.bot.send_message(
                        message.from_user.id,
                        "Операция не выполнена! Не верный формат номера",
                    )
                except DuplicateClientError:
                    self.bot.send_message(message.from_user.id, "Такой клиент уже существует в базе")
            else:
                self.bot.send_message(
                    message.from_user.id,
                    "Для добавления клиента нужно выбрать пункт <➕ Новый клиент>",
                )
            state.allow_add_client = False
            return
        if message.content_type != "text":
            return
        if message.text == MENU_NEW_CLIENT:
            logger.info("Выбран пункт «Новый клиент»")
            self.bot.send_message(message.from_user.id, "Отправь мне контакт и я добавлю его в клиенты")
            state.allow_add_client = True
        elif message.text == "📓 Расписание тренировок":
            self.bot.send_message(
                message.chat.id,
                "Поработаем с расписанием?",
                reply_markup=schedule_menu_markup(),
            )
        elif message.text == BACK_TO_MENU:
            self.start(message)
        elif message.text == MENU_PERSONAL:
            self.sessions.clear(message.chat.id, "add_single_train_in_schedule")
            self.show_list_client(message)
        elif message.text == MENU_GROUP:
            self.sessions.clear(message.chat.id, "add_multi_train_in_schedule")
            self.show_all_type_train(message, True)
        elif message.text == "📑 Список тренировок клиента":
            self.sessions.clear(message.chat.id, "list_train_for_client")
            self.show_list_client(message)
        elif message.text == MENU_REPORT:
            try:
                result = self.report_service.monthly_report()
                self.bot.send_message(message.chat.id, text=report_text(result), parse_mode="Markdown")
            except Exception:
                logger.exception("Ошибка отчёта по тренировкам")
                self.bot.send_message(message.chat.id, "❌ Ошибка формирования отчёта!❌")
            self.start(message)
        elif message.text == MENU_ADD_PAYMENT:
            self.sessions.clear(message.chat.id, "add_money_in_accounting")
            self.show_list_client(message)
        elif state.operation == "input_train_price":
            parsed_price = parse_price(message.text)
            if parsed_price is not None:
                state.train_price = parsed_price
                self.confirm_add(message)
            else:
                self.bot.send_message(message.chat.id, "Введено не корректное значение!")
                self.input_train_price(message)

        state = self.sessions.get(message.chat.id)
        match state.process, state.operation:
            case "add_money_in_accounting", "total_summ_and_number_train":
                prepaid = parse_prepaid(message.text)
                if prepaid is not None:
                    state.summ, state.count_train = prepaid
                    self.confirm_add_in_accounting(message)
                else:
                    self.universal_text_input(
                        text_message=(
                            f"Не корректно введено значение! {message.text}\n"
                            "Введи общую сумму и количество тренировок\n"
                            "Например:<1000 10>"
                        ),
                        command="total_summ_and_number_train",
                        message=message,
                    )

    def confirm_add(self, message) -> None:
        state = self.sessions.get(message.chat.id)
        state.operation = "confirm_add"
        if state.is_group and state.client_multi:
            text_client = "".join(
                [f"{i + 1}. {state.client_multi[i][1]}\n" for i in range(len(state.client_multi))]
            )
        elif state.client:
            client = state.client
            text_client = f"Клиент *{client.get('name')} {client.get('surname')}*\n"
        else:
            text_client = ""
        additional_info = ""
        if not state.is_group and state.client:
            remaining = self.booking_service.remaining_prepaid_sessions(
                state.client["client"],
                state.train["id"],
            )
            if remaining is not None:
                additional_info = (
                    f"\n!У клиента есть пред оплаченные тренировки: {remaining}\n шт!"
                )
        self.bot.send_message(
            message.chat.id,
            booking_confirm_text(
                state.train["type_train"],
                text_client,
                state.date,
                state.time,
                state.train_price,
                additional_info,
            ),
            parse_mode="Markdown",
            reply_markup=confirm_markup(),
        )

    def confirm_add_in_accounting(self, message) -> None:
        state = self.sessions.get(message.chat.id)
        state.operation = "confirm_add_accounting"
        self.bot.send_message(
            message.chat.id,
            prepaid_confirm_text(state.client, state.train, state.summ, state.count_train),
            parse_mode="Markdown",
            reply_markup=confirm_markup(),
        )

    def callback_inline(self, call) -> None:
        if not call.message:
            return
        state = self.sessions.get(call.message.chat.id)
        process = state.process
        operation = state.operation
        if process == "add_single_train_in_schedule" and operation in (
            "choose_client",
            "choose_train",
        ):
            if operation == "choose_client":
                if call.data == "show_all_client_single":
                    self.bot.delete_message(call.message.chat.id, call.message.id)
                    self.show_list_client(call.message, True)
                    return
                client = _find_client(state.list_client, call.data)
                if client is None:
                    return
                state.client = client
                self.show_all_type_train(call.message)
            elif operation == "choose_train":
                train = _find_train(state.list_train, call.data)
                if train is None:
                    return
                state.train = train
                self.show_date(call.message)
        elif process == "add_multi_train_in_schedule" and operation in (
            "choose_train",
            "choose_client_multi",
        ):
            if operation == "choose_train":
                train = _find_train(state.list_train, call.data)
                if train is None:
                    return
                state.train = train
                self.show_multi_list_client(call.message)
            elif operation == "choose_client_multi":
                if call.data == "confirm_multi_list_client":
                    state.client_multi = [
                        (client["client"], f'{client["name"]} {client["surname"]}')
                        for client in state.list_multi_select
                        if client["select"]
                    ]
                    if not state.client_multi:
                        self.bot.send_message(
                            call.message.chat.id,
                            "Нужно выбрать хотя бы одного клиента",
                        )
                        return
                    self.show_date(call.message)
                elif call.data == "show_all_client_multi":
                    self.bot.delete_message(call.message.chat.id, call.message.id)
                    self.show_multi_list_client(call.message, True)
                else:
                    client_id = _as_int(call.data)
                    if client_id is None:
                        return
                    found = False
                    for client in state.list_multi_select or []:
                        if client["client"] == client_id:
                            client["select"] = not client["select"]
                            found = True
                            break
                    if not found:
                        return
                    self.bot.delete_message(call.message.chat.id, call.message.id)
                    self.show_multi_list_client(call.message)
        elif process == "add_money_in_accounting":
            match operation:
                case "choose_client":
                    if call.data == "show_all_client_single":
                        self.bot.delete_message(call.message.chat.id, call.message.id)
                        self.show_list_client(call.message, True)
                        return
                    client = _find_client(state.list_client, call.data)
                    if client is None:
                        return
                    state.client = client
                    state.client_multi = [
                        (
                            state.client["client"],
                            f"{state.client['name']} {state.client['surname']}",
                        )
                    ]
                    self.show_all_type_train(call.message)
                case "choose_train":
                    train = _find_train(state.list_train, call.data)
                    if train is None:
                        return
                    state.train = train
                    self.universal_text_input(
                        text_message=(
                            "Введи общую сумму и количество тренировок\n"
                            "Например:<1000 10>"
                        ),
                        command="total_summ_and_number_train",
                        message=call.message,
                    )
                case "confirm_add_accounting":
                    if call.data == "approve_add":
                        try:
                            self.prepaid_service.add_package(
                                client_id=state.client["client"],
                                type_train_id=state.train["id"],
                                summ=state.summ,
                                count=state.count_train,
                            )
                            self.bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                        except InvalidPrepaidError:
                            self.bot.send_message(
                                call.message.chat.id,
                                "❌ Некорректные сумма или количество!❌",
                            )
                        except MultiplePrepaidError:
                            self.bot.send_message(
                                call.message.chat.id,
                                "❌ У клиента уже есть незакрытая предоплата!❌",
                            )
                        except Exception:
                            logger.exception("Ошибка добавления предоплаты")
                            self.bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                    elif call.data == "cancel_add":
                        self.bot.send_message(call.message.chat.id, "Действие отменено!")
                        self.start(call.message)
        else:
            if state.operation == "choose_date":
                if call.data == "prev_week":
                    self.bot.delete_message(call.message.chat.id, call.message.id)
                    self.show_date(call.message, shift_week(state.week_dates["0"], "prev"))
                elif call.data == "current_week":
                    self.bot.delete_message(call.message.chat.id, call.message.id)
                    self.show_date(call.message, shift_week(state.week_dates["0"], "current"))
                elif call.data == "next_week":
                    self.bot.delete_message(call.message.chat.id, call.message.id)
                    self.show_date(call.message, shift_week(state.week_dates["0"], "next"))
                else:
                    selected = _parse_iso_date(call.data)
                    if selected is None:
                        return
                    state.date = selected
                    self.show_available_time(call.message)
            elif state.operation == "choose_time":
                selected_time = _find_slot(state.list_time, call.data)
                if selected_time is None:
                    return
                state.time = selected_time
                self.input_train_price(call.message)
            elif state.operation == "confirm_add":
                if call.data == "approve_add":
                    if not state.is_group:
                        try:
                            self.booking_service.book_personal(
                                client_id=state.client["client"],
                                type_train_id=state.train["id"],
                                session_date=state.date,
                                session_time=state.time,
                                price=state.train_price,
                            )
                            self.bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                        except SlotTakenError:
                            self.bot.send_message(call.message.chat.id, "❌ Слот уже занят!❌")
                        except MultiplePrepaidError:
                            self.bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                        except Exception:
                            logger.exception("Ошибка добавления записи в расписание")
                            self.bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                    else:
                        try:
                            self.booking_service.book_group(
                                client_ids=[item[0] for item in state.client_multi or []],
                                type_train_id=state.train["id"],
                                session_date=state.date,
                                session_time=state.time,
                                price=state.train_price,
                            )
                            self.bot.send_message(call.message.chat.id, "✅Запись добавлена!✅")
                        except SlotTakenError:
                            self.bot.send_message(call.message.chat.id, "❌ Слот уже занят!❌")
                        except EmptyParticipantsError:
                            self.bot.send_message(
                                call.message.chat.id,
                                "❌ Нужно выбрать хотя бы одного клиента!❌",
                            )
                        except Exception:
                            logger.exception("Ошибка добавления групповой записи в расписание")
                            self.bot.send_message(call.message.chat.id, "❌ Ошибка добавления записи!❌")
                elif call.data == "cancel_add":
                    self.bot.send_message(call.message.chat.id, "Действие отменено!")
                    self.start(call.message)
            elif call.data == "cancel_add":
                self.bot.send_message(call.message.chat.id, "Действие отменено!")
                self.start(call.message)


def create_bot(
    settings: Settings,
    repository: KateFitRepository,
    sessions: SessionStore | None = None,
) -> BotApp:
    app = BotApp(
        bot=telebot.TeleBot(settings.telegram_token),
        sessions=sessions or SessionStore(),
        client_service=ClientService(repository),
        booking_service=BookingService(repository),
        prepaid_service=PrepaidService(repository),
        report_service=ReportService(repository),
    )
    app.register_handlers()
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _settings = load_settings()
    _app = create_bot(_settings, PostgresRepository.from_settings(_settings))
    _app.bot.infinity_polling()
