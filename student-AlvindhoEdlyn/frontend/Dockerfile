FROM nginx:alpine

WORKDIR /usr/share/nginx/html

# Clean default NGINX HTML files
RUN rm -rf ./*

# Copy custom NGINX configuration (if you created nginx.conf)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend assets directly from the build context
COPY css/ ./css/
COPY index.html .
COPY script.js .

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]