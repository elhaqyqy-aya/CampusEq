FROM apache/airflow:2.10.5-python3.12

USER airflow
RUN pip install --no-cache-dir "pymongo>=4.8,<5" "redis>=5,<6" "psycopg2-binary>=2.9.9"
RUN mkdir -p /opt/airflow/state

COPY --chown=airflow:root axes_3_4 /opt/airflow/campusequip/axes_3_4
COPY --chown=airflow:root etudiant /opt/airflow/campusequip/etudiant

ENV PYTHONPATH=/opt/airflow/campusequip
