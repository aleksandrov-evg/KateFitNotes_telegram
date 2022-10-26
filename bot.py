import configparser
import telebot

config = configparser.ConfigParser()
config.read("config.ini")
token = config["main"]["TOKEN"]
bot = telebot.TeleBot(token)


def client(phone_number):
    if len(phone_number) == 12 and phone_number[0:2] == '+7':
        phone_number = phone_number[2:]
    elif len(phone_number) == 11 and phone_number[0:1] == '8':
        phone_number = phone_number[1:]
    else:
        bot.send_message("Операция не выполнена! Не верный формат номера")
        return 0
    

@bot.message_handler(content_types=['text', 'contact'])
def get_text_messages(message):
    if message.content_type == 'contact':
        client(message.contact.phone_number)
    elif message.content_type == 'text':
        if message.text == "/command":
            bot.send_message(message.from_user.id, "Обработчик команды")


bot.infinity_polling()
