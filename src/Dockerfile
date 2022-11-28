FROM python:alpine3.15

RUN apk add --no-cache bash \
    && pip install --upgrade pip \
    && rm -rf /var/cache/apk/*

COPY . /app

WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt



ENTRYPOINT [ "python3" ]

CMD ["app.py"]