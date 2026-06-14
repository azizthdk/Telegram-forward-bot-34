FROM python:3.11-slim

# Install deps first (cached layer)
WORKDIR /app
COPY telegram-bot/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full bot source (working dir = telegram-bot/)
COPY telegram-bot/ .

CMD ["python", "main.py"]
