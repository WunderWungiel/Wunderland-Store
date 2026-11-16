FROM python:3.15-alpine3.24
WORKDIR /app
COPY ./app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app/ .
ENTRYPOINT ["./entrypoint.sh"]
