import argparse


def main() -> None:
    from relatorios_service.config import settings
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true")
    arguments = parser.parse_args()

    uvicorn.run(
        "relatorios_service.main:app",
        port=settings.app_port,
        reload=arguments.reload,
    )
