import configparser
import telebot


def client(phone_number):
    print(phone_number)


config = configparser.ConfigParser()
config.read("config.ini")
token = config["main"]["TOKEN"]

bot = telebot.TeleBot(token)


@bot.message_handler(content_types=['text', 'contact'])
def get_text_messages(message):
    if message.content_type == 'contact':
        client(message.contact.phone_number)
    elif message.content_type == 'text':
        if message.text == "/command":
            bot.send_message(message.from_user.id, "Обработчик команды")


bot.infinity_polling()
