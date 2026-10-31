# Frontend estático servido con Nginx
FROM nginx:1.27-alpine
COPY index.html styles.css app.js config.js /usr/share/nginx/html/
# Nginx ejecuta los scripts de /docker-entrypoint.d al iniciar:
# así la URL de la API se configura con una variable de entorno sin reconstruir.
COPY generar_config.sh /docker-entrypoint.d/40-generar-config.sh
RUN chmod +x /docker-entrypoint.d/40-generar-config.sh
EXPOSE 80
