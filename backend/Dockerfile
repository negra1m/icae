FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    pandas numpy scipy scikit-learn networkx \
    fastapi uvicorn pydantic httpx
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
