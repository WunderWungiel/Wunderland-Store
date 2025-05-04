FROM python:3-bookworm
WORKDIR /app
COPY ./requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENTRYPOINT ["./entrypoint.sh"]
