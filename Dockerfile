# Gunakan image dasar Python
FROM python:3.9-slim-buster

# Set working directory di dalam container
WORKDIR /app

# Salin requirements.txt dan instal dependensi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Salin seluruh kode aplikasi
COPY . .

# Set variabel lingkungan
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Port yang diekspos
EXPOSE 5000

# Perintah untuk menjalankan aplikasi
CMD ["flask", "run", "--host=0.0.0.0"]