FROM nginx:stable-alpine
COPY ui/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY ui/index.html /usr/share/nginx/html/index.html
COPY ui/src /usr/share/nginx/html/src
ENV UI_ENVIRONMENT=production
ENV NGINX_ENVSUBST_FILTER="UI_API_ORIGIN|UI_ENVIRONMENT"
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
