FROM python:3.9-alpine
WORKDIR /usr/src/bot
COPY bot.py ./
COPY config.ini ./
COPY sql.py ./
COPY requirements.txt ./
RUN\
    apk add --no-cache postgresql-libs && \
    apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev && \
    pip install --no-cache-dir -r requirements.txt
CMD ["python3","-m", "bot.py"]