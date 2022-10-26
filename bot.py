import configparser

config = configparser.ConfigParser()
config.read("config.ini")

print(config["main"]["TOKEN"])

