FROM python:3.10-slim

RUN printf "precedence ::ffff:0:0/96 100\n" >> /etc/gai.conf

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=TRUE

EXPOSE 8080

# ✅ Let socketio.run() handle the server
CMD ["python", "app.py"]