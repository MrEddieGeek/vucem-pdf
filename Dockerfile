# Imagen base con Python
FROM python:3.11-slim

# Instalar dependencias del sistema
# Ghostscript es necesario
RUN apt-get update && apt-get install -y \
    ghostscript \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero (cache de dependencias)
COPY requirements.txt .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Crear carpeta de uploads
RUN mkdir -p uploads

# Exponer puerto Flask
EXPOSE 5000

# Comando para ejecutar la app
CMD ["python", "app.py"]
