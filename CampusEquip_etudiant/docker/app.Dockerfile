# =====================================================================
#  CampusEquip — image unique pour le pipeline, la console et les preuves
#  Construction :  docker compose build
#  Exécution   :  docker compose up -d
# =====================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Africa/Casablanca

WORKDIR /app

# Dépendances d'abord : la couche est réutilisée tant que requirements ne change pas.
COPY requirements.txt ./
COPY axes_3_4/requirements.txt ./axes_3_4/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Code du projet
COPY . .

RUN chmod +x scripts/docker-entrypoint.sh \
 && mkdir -p rapports quarantaine resultats preuves flux_demo \
 && useradd --create-home --shell /usr/sbin/nologin campusequip \
 && chown -R campusequip:campusequip /app

USER campusequip

EXPOSE 5055

HEALTHCHECK --interval=15s --timeout=4s --start-period=25s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5055/api/sante', timeout=3).status == 200 else 1)"

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["console"]
