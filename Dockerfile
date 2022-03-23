FROM docker.io/alpine:latest

# Install Pillow (py3-pillow) from Alpine repository to avoid compiling it.
RUN apk add git py3-pip py3-pillow

RUN git clone https://github.com/deltachat/mailadm
WORKDIR mailadm
RUN git checkout mailcow
#RUN LIBRARY_PATH=/lib:/usr/lib /bin/sh -c "pip install -q ."
RUN pip install .

#COPY .env .env
#COPY mailadm.db /mailadm.db
#ENV MAILADM_DB=/mailadm.db
#RUN . .env && mailadm init --web-endpoint $WEB_ENDPOINT --mail-domain $MAIL_DOMAIN --mailcow-endpoint $MAILCOW_ENDPOINT --mailcow-token $MAILCOW_TOKEN
#CMD ["gunicorn", "-b", ":3691", "-w", "1", "mailadm.app:app"]

