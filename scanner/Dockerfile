FROM python:3.12-slim

WORKDIR /app

# Install system deps for Playwright (Chromium) + Xvfb/VNC for headful recorder
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libcups2 libdbus-1-3 \
    xvfb x11vnc fluxbox websockify xdotool xclip xsel \
    && rm -rf /var/lib/apt/lists/*

# Configure fluxbox: no decorations, no toolbar, maximize everything
RUN mkdir -p /root/.fluxbox && \
    printf '[app] (.*)\n  [Maximized]\t{yes}\n  [Deco]\t{NONE}\n[end]\n' > /root/.fluxbox/apps && \
    printf 'session.screen0.toolbar.visible: false\n\
session.screen0.defaultDeco: NONE\n\
session.screen0.maxDisableMove: true\n\
session.screen0.maxDisableResize: true\n\
session.screen0.workspaces: 1\n\
session.screen0.toolbar.widthPercent: 0\n\
session.screen0.tabs.usePixmap: false\n\
session.screen0.window.focus.alpha: 255\n\
session.screen0.window.unfocus.alpha: 255\n' > /root/.fluxbox/init

# Install noVNC (web-based VNC viewer)
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && git clone --depth 1 https://github.com/novnc/noVNC.git /opt/noVNC \
    && git clone --depth 1 https://github.com/novnc/websockify.git /opt/noVNC/utils/websockify \
    && ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html \
    && apt-get purge -y git && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=600 --retries=3 -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium

COPY . .

EXPOSE 8001 6080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
