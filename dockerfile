FROM python:3.11-alpine
WORKDIR /usr/src/bot
COPY bot.py config.ini sql.py requirements.txt test.py src ./
RUN \
    apk add --no-cache postgresql-libs && \
    apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev && \
    pip install --no-cache-dir -r requirements.txt
# CMD ["pytest", "test.py"]
CMD ["python3","-m", "bot.py"]