FROM python:3.12-slim

WORKDIR /app

COPY deck_controller/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY deck_controller/ /app/
COPY deck/   /app/deck/
COPY player/ /app/player/

# deck.yaml and the music library are bind-mounted at runtime so the button
# layout and the song folders can change without rebuilding the image.
ENV DECK_CONFIG=/config/deck.yaml \
    MUSIC_LIBRARY=/songs \
    DECK_HTTP_PORT=8095

EXPOSE 8095

CMD ["python", "app.py"]
