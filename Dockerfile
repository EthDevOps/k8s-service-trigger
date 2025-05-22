FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY service_monitor.py .
RUN chmod +x service_monitor.py

CMD ["./service_monitor.py"]
