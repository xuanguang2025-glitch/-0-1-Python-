# 社区版 compose 不认识 `include`，这里用 nginx 的公共配置片段，
# 由 docker-compose.yml 挂载为 /etc/nginx/conf.d/proxy_params.inc
proxy_http_version 1.1;
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_buffering off;
proxy_read_timeout 120s;
proxy_send_timeout 120s;
