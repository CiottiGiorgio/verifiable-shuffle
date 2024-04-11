# On GH this multi-stage build will fail because of some problem with Actions
#  and linux/arm64 node:20.
# This fixes that issue and determines the platform for the build while we still get an arm64 image.
FROM --platform=linux/amd64 node:20 as BUILDER

WORKDIR /app
COPY package*.json ./

RUN npm ci

COPY . .
RUN npx tsc
RUN npx vite build

FROM nginx:1.24-alpine

COPY --from=BUILDER /app/dist/ /usr/share/nginx/html/

EXPOSE 80