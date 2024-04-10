FROM node:20 as BUILDER

WORKDIR /app
COPY package*.json ./

RUN npm ci

COPY . .
RUN npx tsc
RUN npx vite build

FROM nginx:1.24-alpine

COPY --from=BUILDER /app/dist/ /usr/share/nginx/html/

EXPOSE 80