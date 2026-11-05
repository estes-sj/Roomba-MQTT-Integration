# Roomba web remote: static page + MQTT-over-WebSocket proxy in one small container
FROM nginx:1.27-alpine
# Where Mosquitto's WebSocket listener lives (host:port), reachable from this container
ENV MQTT_WS_UPSTREAM=mqtt:9001
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY index.html manifest.json icon.svg icon-192.png icon-512.png /usr/share/nginx/html/
COPY vendor /usr/share/nginx/html/vendor
COPY fonts /usr/share/nginx/html/fonts
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
