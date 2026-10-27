FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 researcher
COPY agent.py /app/agent.py
RUN mkdir /runs && chown researcher:researcher /runs
USER researcher
ENTRYPOINT ["python", "/app/agent.py"]
