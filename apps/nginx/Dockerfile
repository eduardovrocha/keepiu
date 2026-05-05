FROM nginx:1.25-alpine

# Copy config
COPY nginx.conf /etc/nginx/nginx.conf

# Create directory for certbot challenge
RUN mkdir -p /var/www/certbot

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
