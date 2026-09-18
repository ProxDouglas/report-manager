FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN addgroup --system sandbox && adduser --system --ingroup sandbox sandbox

RUN pip install --no-cache-dir \
    numpy==2.2.4 \
    pandas==2.2.3 \
    matplotlib==3.10.1 \
    openpyxl==3.1.5

WORKDIR /workspace
USER sandbox

CMD ["python"]
