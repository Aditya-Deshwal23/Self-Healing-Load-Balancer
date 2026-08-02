FROM node:24-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd AS frontend-build

ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts

COPY frontend/ ./
RUN npm run build

FROM nginx:1.30.4-alpine3.24@sha256:97d490c12ba55b4946b01546d1c3ed324e8d41ab1c9fcb2a616aa470620e5b46

RUN apk add --no-cache openssl

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/40-generate-lab-cert.sh /docker-entrypoint.d/40-generate-lab-cert.sh
COPY --from=frontend-build /frontend/out/ /usr/share/nginx/html/

RUN chmod 0755 /docker-entrypoint.d/40-generate-lab-cert.sh
