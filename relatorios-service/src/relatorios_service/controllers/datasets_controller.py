import logging
from collections.abc import Iterator
from contextlib import contextmanager
from zipfile import BadZipFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    get_container,
)
from relatorios_service.services.dataset_service import DatasetStorageError


logger = logging.getLogger(__name__)
router = APIRouter()


@contextmanager
def _upload_errors() -> Iterator[None]:
    try:
        yield
    except (ValueError, BadZipFile) as error:
        raise HTTPException(
            status_code=400, detail="Arquivo inválido ou formato não suportado.",
        ) from error
    except DatasetStorageError as error:
        logger.exception("Falha ao armazenar arquivos enviados.")
        raise HTTPException(
            status_code=500, detail="Não foi possível armazenar os arquivos.",
        ) from error
    except Exception as error:
        logger.exception("Falha inesperada ao processar arquivos enviados.")
        raise HTTPException(
            status_code=500, detail="Não foi possível processar os arquivos.",
        ) from error


@router.post("/files/preview")
async def preview_file(
    file: UploadFile = File(...),
    container: ApplicationContainer = Depends(get_container),
) -> dict:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="O arquivo precisa possuir um nome.",
        )
    content = await _read_upload_content(
        file,
        container.settings.max_upload_bytes,
    )

    with _upload_errors():
        return await run_in_threadpool(container.dataset_service.preview, file.filename, content)


@router.post("/datasets", status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    container: ApplicationContainer = Depends(get_container),
) -> dict:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="O arquivo precisa possuir um nome.",
        )
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Envie um arquivo com extensão .csv.",
        )

    content = await _read_upload_content(
        file,
        container.settings.max_upload_bytes,
    )
    with _upload_errors():
        return await run_in_threadpool(container.dataset_service.store_csv, file.filename, content)


@router.post("/datasets/batch", status_code=201)
async def upload_datasets(
    files: list[UploadFile] = File(...),
    container: ApplicationContainer = Depends(get_container),
) -> dict:
    if not 1 <= len(files) <= container.settings.max_upload_files:
        raise HTTPException(status_code=400, detail="Quantidade de arquivos fora do limite permitido.")
    uploads = []
    total_bytes = 0
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Todos os arquivos devem ter nome e extensão .csv.")
        remaining = container.settings.max_batch_upload_bytes - total_bytes
        content = await _read_upload_content(file, min(container.settings.max_upload_bytes, remaining))
        total_bytes += len(content)
        uploads.append((file.filename, content))
    with _upload_errors():
        datasets = await run_in_threadpool(container.dataset_service.store_many, uploads)
        return {"datasets": datasets}


@router.get("/datasets/{dataset_id}/csv")
def download_dataset(
    dataset_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> Response:
    try:
        dataset = container.dataset_repository.get(dataset_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Dataset não encontrado ou expirado.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Identificador de dataset inválido.") from error
    return Response(
        content=dataset.content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}.csv"'},
    )


async def _read_upload_content(
    file: UploadFile,
    max_upload_bytes: int,
) -> bytes:
    chunks: list[bytes] = []
    total_bytes = 0
    chunk_size = 64 * 1024

    while chunk := await file.read(chunk_size):
        total_bytes += len(chunk)
        if total_bytes > max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=(
                    "O arquivo excede o limite de "
                    f"{max_upload_bytes} bytes."
                ),
            )
        chunks.append(chunk)

    return b"".join(chunks)
