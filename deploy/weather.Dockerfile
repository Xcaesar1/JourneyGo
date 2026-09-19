# Weather release layer for an existing compatible JourneyGo staging image.
ARG BASE_IMAGE=journeygo-app:latest
FROM ${BASE_IMAGE}
USER root
COPY backend/weather-requirements.lock /opt/weather-requirements.lock
RUN uv venv /opt/weather && uv pip sync --python /opt/weather/bin/python /opt/weather-requirements.lock
COPY --chown=journeygo:journeygo backend/ /app/backend/
COPY --chown=journeygo:journeygo frontend/dist/ /app/frontend/dist/
USER journeygo
