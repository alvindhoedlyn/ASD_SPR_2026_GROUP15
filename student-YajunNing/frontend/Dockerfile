FROM nginx:alpine

COPY index.html /usr/share/nginx/html/index.html
COPY style.css /usr/share/nginx/html/static/style.css
COPY flight-hero-sunset.png /usr/share/nginx/html/static/flight-hero-sunset.png
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
