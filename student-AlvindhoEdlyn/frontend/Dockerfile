FROM nginx:alpine

WORKDIR /usr/share/nginx/html

# Clean default NGINX HTML files
RUN rm -rf ./*

# Copy custom NGINX configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy assets and all individual HTML pages
COPY css/ ./css/
COPY index.html .
COPY mcp_frontend.html .
COPY rag_frontend.html .
COPY js/ /usr/share/nginx/html/js/

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]