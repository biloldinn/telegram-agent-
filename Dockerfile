FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV USERBOTS_ONLY=1

CMD ["python", "-u", "main.py"]
