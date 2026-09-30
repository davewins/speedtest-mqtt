FROM python:3.12-slim

# Install the official Ookla speedtest CLI (not the deprecated python
# speedtest-cli package) from Ookla's apt repo.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates && \
    curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash && \
    apt-get install -y speedtest && \
    apt-get purge -y curl gnupg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY speedtest_mqtt.py .

CMD ["python", "-u", "speedtest_mqtt.py"]
