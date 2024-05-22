FROM python:3
WORKDIR /usr/src/app
COPY . .
RUN touch database.sqlite && pip install --no-cache-dir -r requirements.txt
EXPOSE 9999
CMD [ "python", "src/main.py" ]