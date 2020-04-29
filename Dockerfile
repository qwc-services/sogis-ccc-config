# WSGI service environment

FROM sourcepole/qwc-uwsgi-base:alpine-latest

ADD . /srv/qwc_service
RUN pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt
RUN pip3 install --no-cache-dir flask_cors
