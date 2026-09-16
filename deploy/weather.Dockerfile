# Weather release layer for an existing compatible JourneyOps staging image.
ARG BASE_IMAGE=journeyops-app:mobile-f62e7bd
FROM ${BASE_IMAGE}
USER root
COPY backend/weather-requirements.lock /opt/weather-requirements.lock
RUN uv venv /opt/weather && uv pip sync --python /opt/weather/bin/python /opt/weather-requirements.lock
COPY --chown=journeyops:journeyops backend/ /app/backend/
COPY --chown=journeyops:journeyops frontend/dist/ /app/frontend/dist/
USER journeyops
