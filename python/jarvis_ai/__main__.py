import uvicorn

from jarvis_ai.api.main import app
from jarvis_ai.config.settings import Settings

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(app, host=settings.python_api_host, port=settings.python_api_port)
