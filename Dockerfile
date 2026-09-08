FROM node:20-bookworm-slim

# Headless Chromium deps (for Remotion) + ffmpeg + python3 for the driver script
RUN echo "Types: deb\nURIs: http://mirrors.edge.kernel.org/debian\nSuites: bookworm bookworm-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg" > /etc/apt/sources.list.d/debian.sources && \
    apt-get update -o Acquire::Retries=5 && apt-get install -y --no-install-recommends -o Acquire::Retries=5 \
    ffmpeg python3 chromium \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY remotion/package.json ./remotion/package.json
RUN cd remotion && npm install && npm cache clean --force

COPY remotion ./remotion
COPY assets ./assets
COPY data ./data
COPY python ./python

# Fonts must live under remotion/public/ for staticFile() to find them
RUN mkdir -p remotion/public/fonts && cp assets/fonts/*.ttf remotion/public/fonts/

# Use the system chromium we installed via apt-get
ENV REMOTION_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

CMD ["bash"]
