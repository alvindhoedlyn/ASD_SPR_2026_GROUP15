FROM nginx:alpine

COPY . /usr/share/nginx/html/

# nginx:alpine renders /etc/nginx/templates/*.template with the container's environment
# variables (BACKEND_URL) at startup.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80