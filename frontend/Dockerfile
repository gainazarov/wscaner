FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libc6 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
