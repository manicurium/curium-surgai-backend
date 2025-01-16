FROM python:3.11-slim

RUN apt-get update && apt-get install -y python3 python3-pip && apt-get install ffmpeg libsm6 libxext6  -y
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY  /curium_surgai_backend /curium_surgai_backend
EXPOSE 7050

WORKDIR /curium_surgai_backend
CMD python manage.py makemigrations && python manage.py migrate --run-syncdb && python manage.py migrate auth && python manage.py migrate && python manage.py runserver 0.0.0.0:7050
