# speedtest-mqtt

Runs the official Ookla Speedtest CLI on a schedule and publishes the results
to MQTT with Home Assistant MQTT discovery, so the sensors appear in Home
Assistant automatically with no YAML.

## Why this exists

Home Assistant runs on a machine with a 1 Gb/s network interface, so any
speedtest run from there tops out around 1 Gb/s and under-reports a faster
connection. This container runs on a separate machine with a **2.5 Gb/s**
interface, so the test reflects the real internet speed, and it reports the
result to Home Assistant over MQTT.

## How it works

- Runs `speedtest` (Ookla's official CLI, not the deprecated `speedtest-cli`)
  every `TEST_INTERVAL` seconds (default hourly).
- Publishes the result as JSON, retained, to `<prefix>/state`.
- Publishes HA discovery configs (retained) under `homeassistant/sensor/<prefix>/...`
  for: Download, Upload, Ping, Jitter, Packet Loss, Server, ISP.

### Availability and Last Will

- `<prefix>/availability` carries `online` / `offline` (retained). HA marks the
  sensors unavailable when it is `offline`.
- The MQTT Last Will is `offline` (retained), so the broker publishes it if the
  container drops off.
- `online` (retained) is published from paho's `on_connect`, so it is restored
  on **every** connect and reconnect, not just at startup. Without this, a
  broker restart or network blip leaves the sensors unavailable until the
  container is restarted.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MQTT_BROKER` | `192.168.1.5` | Broker host (set this) |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_USER` / `MQTT_PASSWORD` | empty | Broker credentials |
| `MQTT_TOPIC_PREFIX` | `speedtest` | Topic prefix and HA device id |
| `TEST_INTERVAL` | `3600` | Seconds between tests |

## Image

Built by GitHub Actions (`.github/workflows/build.yml`) on every push to `main` and
weekly, and published to `ghcr.io/davewins/speedtest-mqtt:latest`. The image is
distroless (Chainguard Python; no shell or package manager) with the statically
linked Ookla CLI pinned by checksum in the `Dockerfile`, so there are no OS packages
to carry CVEs. It runs as uid 65532 and is meant to run with a read-only root
filesystem, a `/tmp` tmpfs and all capabilities dropped (as `docker-compose.yml` does).

## Run

On hosts where macvlan isn't suitable, use `docker-compose.bridge.yml` instead of
`docker-compose.yml` (same variables, no `LAN_*`). The image is multi-arch (amd64, arm64).

Portainer: Stacks > Add stack > Repository, this repo, `docker-compose.yml`, with the
variables from `.env.example` as stack environment variables. Or from a shell:

```sh
cp .env.example .env    # edit values; .env is git-ignored
docker compose --env-file .env up -d
docker logs -f speedtest-mqtt
```

Run it on the host with the fastest NIC. Each test saturates the link for
roughly 15-20 seconds, so pick an interval you are happy with.

## Check it

```sh
mosquitto_sub -h <broker> -u <user> -P <pass> -v -t 'speedtest/#'
```

You should see `speedtest/availability online` and a JSON `speedtest/state`.

## License and attributions

The code in this repository is MIT licensed (see `LICENSE`). It is not affiliated
with or endorsed by Ookla.

- **Ookla Speedtest CLI** is (c) Ookla, LLC and is used under the
  [Speedtest EULA](https://www.speedtest.net/about/eula), which allows personal,
  non-commercial use only and prohibits redistribution. This repository does not
  contain the binary: the `Dockerfile` downloads it from Ookla at build time and
  verifies its checksum. Because the built image contains it, the published image
  must be kept **private** and not redistributed. Anyone else should build their
  own image. "Speedtest" and "Ookla" are trademarks of Ookla, LLC.
- **paho-mqtt** (Eclipse Foundation) is dual-licensed under EPL-2.0 / EDL-1.0 (BSD-style).
- **Base image** `cgr.dev/chainguard/python` (Chainguard) bundles Python (PSF license)
  and other open source components under their own licenses.
