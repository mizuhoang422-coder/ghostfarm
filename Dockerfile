FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV HOME=/home/user
ENV PORT=10000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Space chay bang user 1000, can chown
RUN chown -R 1000:1000 /app /home/user

USER 1000:1000

CMD ["python", "main.py"]
