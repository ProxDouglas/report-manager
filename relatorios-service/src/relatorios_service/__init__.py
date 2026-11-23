import argparse


def main() -> None:
    from relatorios_service.config import get_settings
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true")
    arguments = parser.parse_args()
    settings = get_settings()

    uvicorn.run(
        "relatorios_service.main:app",
        port=settings.app_port,
        reload=arguments.reload,
    )
