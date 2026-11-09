# CyberArena: engine, adapters, range and benchmark in one image.
# STATUS: written but NOT built or run (Docker is not installed on the machine this was developed on).
#
#   docker build -t cyberarena .
#   docker run --rm cyberarena version
#   docker run --rm -v "$PWD/examples:/data:ro" cyberarena triage --events /data/events.csv --tickets /data/tickets.csv --site /app/config/site.example.yaml
#   docker run --rm -p 8000:8000 -p 8100:8100 -p 5020:5020 cyberarena range serve --host 0.0.0.0
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY examples ./examples
RUN pip install --no-cache-dir ".[bench,range,xlsx]"
ENTRYPOINT ["cyberarena"]
CMD ["--help"]
