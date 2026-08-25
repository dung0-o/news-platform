FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8-slim

COPY ./src /app/src
COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

WORKDIR /app/src

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]