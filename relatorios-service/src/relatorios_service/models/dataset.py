from dataclasses import dataclass


@dataclass(frozen=True)
class StoredDataset:
    dataset_id: str
    filename: str
    content: bytes
