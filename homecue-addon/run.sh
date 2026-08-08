#!/usr/bin/with-contenv bashio

if ! bashio::services.available "mqtt"; then
  bashio::exit.nok "No Supervisor MQTT service is available. Install and configure an MQTT broker app first."
fi

export HOMECUE_MQTT_PORT="$(bashio::services mqtt "port")"
export HOMECUE_MQTT_USERNAME="$(bashio::services mqtt "username")"
export HOMECUE_MQTT_PASSWORD="$(bashio::services mqtt "password")"
export HOMECUE_MQTT_TLS="$(bashio::services mqtt "ssl")"

bashio::log.info "Starting the HomeCue pairing companion"
exec python3 /app/server.py
