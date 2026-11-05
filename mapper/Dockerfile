FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY plan.py localizer.py roomba_mapper.py import_plan.py ./
VOLUME /data
ENV DATA_DIR=/data
CMD ["python", "-u", "roomba_mapper.py"]
