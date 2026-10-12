from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    get_container,
)
from relatorios_service.services.dataset_service import DatasetStorageError


router = APIRouter()


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

    try:
        return container.dataset_service.preview(file.filename, content)
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


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
    try:
        return container.dataset_service.store_csv(file.filename, content)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except DatasetStorageError as error:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível armazenar o CSV.",
        ) from error


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
