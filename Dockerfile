# syntax=docker/dockerfile:1
# Build stage has pip and a shell; the runtime stage below has neither (distroless).
FROM cgr.dev/chainguard/python:latest-dev AS build
USER root
WORKDIR /build

# Official Ookla speedtest CLI: a single statically linked binary, so it needs no
# distro packages. Each arch's tarball is pinned by checksum; bump versions and both
# checksums together to upgrade.
ARG TARGETARCH
ARG OOKLA_VERSION=1.2.0
ARG OOKLA_SHA256_AMD64=5690596c54ff9bed63fa3732f818a05dbc2db19ad36ed68f21ca5f64d5cfeeb7
ARG OOKLA_SHA256_ARM64=3953d231da3783e2bf8904b6dd72767c5c6e533e163d3742fd0437affa431bd3
RUN case "${TARGETARCH}" in \
      amd64) A=x86_64; H="${OOKLA_SHA256_AMD64}" ;; \
      arm64) A=aarch64; H="${OOKLA_SHA256_ARM64}" ;; \
      *) echo "unsupported arch ${TARGETARCH}"; exit 1 ;; \
    esac \
 && python -c "import hashlib,sys,tarfile,urllib.request as u; \
v='${OOKLA_VERSION}'; d=u.urlopen(f'https://install.speedtest.net/app/cli/ookla-speedtest-{v}-linux-$A.tgz').read(); \
sys.exit('checksum mismatch') if hashlib.sha256(d).hexdigest()!='$H' else None; \
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
