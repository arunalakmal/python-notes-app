FROM python:3.10.8-slim-buster

WORKDIR /notes

COPY requirements.txt requirements.txt

RUN pip3 install -r requirements.txt

COPY . .

EXPOSE 3000

RUN chgrp -R 0 /notes && \
    chmod -R g=u /notes

USER 10001

CMD ["python3", "-m" , "flask", "run", "--host=0.0.0.0", "--port=3000"]