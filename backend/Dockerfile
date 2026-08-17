FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r appuser && mkdir -p /app/uploads /app/counter-data /app/clips && chown -R appuser /app && chmod 755 /app/entrypoint.sh /app/start.sh
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/start.sh"]
