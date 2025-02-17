FROM vaathi/bulb:latest

WORKDIR /usr/src/app
COPY . .

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

RUN set -ex \
    && chmod 777 /usr/src/app \
    && cp netrc /usr/src/app/.netrc \
    && cp extract pextract /usr/local/bin \
    && chmod +x /usr/local/bin/extract /usr/local/bin/pextract

CMD ["bash","start.sh"]
