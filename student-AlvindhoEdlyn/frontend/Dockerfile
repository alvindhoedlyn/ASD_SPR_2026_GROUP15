FROM nginx:alpine

WORKDIR /usr/share/nginx/html

RUN rm -rf ./*

COPY frontend/css/ ./css/
COPY frontend/index.html .
COPY frontend/script.js .

EXPOSE 80