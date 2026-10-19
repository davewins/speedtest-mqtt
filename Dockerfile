# syntax=docker/dockerfile:1
# Build stage has pip and a shell; the runtime stage below has neither (distroless).
FROM cgr.dev/chainguard/python:latest-dev AS build
USER root
WORKDIR /build

# Official Ookla speedtest CLI: a single statically linked binary, so it needs no
# distro packages. The tarball is pinned by checksum; bump both together to upgrade.
ARG OOKLA_VERSION=1.2.0
ARG OOKLA_SHA256=5690596c54ff9bed63fa3732f818a05dbc2db19ad36ed68f21ca5f64d5cfeeb7
RUN python -c "import hashlib,sys,tarfile,urllib.request as u; \
v='${OOKLA_VERSION}'; d=u.urlopen(f'https://install.speedtest.net/app/cli/ookla-speedtest-{v}-linux-x86_64.tgz').read(); \
sys.exit('checksum mismatch') if hashlib.sha256(d).hexdigest()!='${OOKLA_SHA256}' else None; \
open('o.tgz','wb').write(d); tarfile.open('o.tgz').extract('speedtest','/build')" \
 && chmod 0755 /build/speedtest

COPY requirements.txt .
RUN pip install --no-cache-dir --target /opt/lib -r requirements.txt

FROM cgr.dev/chainguard/python:latest
COPY --from=build /build/speedtest /usr/local/bin/speedtest
COPY --from=build /opt/lib /opt/lib
COPY speedtest_mqtt.py /app/speedtest_mqtt.py

# Fixed non-root uid; the speedtest CLI writes its licence/config state under HOME,
# so HOME points at /tmp (a tmpfs when the root filesystem is read-only).
USER 65532:65532
ENV PYTHONPATH=/opt/lib PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp

ENTRYPOINT ["python", "/app/speedtest_mqtt.py"]
