FROM python:3.14.6-alpine3.23@sha256:b165067c5afc37fa5608a3c05609cc3d51aafd808a30fbfd822ee594fef55ad4

WORKDIR /app
COPY demo-backend/app.py /app/app.py

USER 65532:65532
EXPOSE 8080
CMD ["python", "/app/app.py"]
