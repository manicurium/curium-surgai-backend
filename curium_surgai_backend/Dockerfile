FROM python:3.11-slim

RUN apt-get update
RUN apt-get install -y python3 python3-pip

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY  /curium_surgai_backend /curium_surgai_backend
COPY manage.py /
COPY /data /data
EXPOSE 7050


CMD python manage.py makemigrations && python manage.py migrate && python manage.py runserver 0.0.0.0:7050
