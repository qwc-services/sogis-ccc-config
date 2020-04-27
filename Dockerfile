FROM sourcepole/qwc-uwsgi-base:ubuntu-latest

ADD . /srv/qwc_service
RUN pip3 install --no-cache-dir -r /srv/qwc_service/requirements.txt

ENV SERVICE_MOUNTPOINT=/api/v1/ccc
