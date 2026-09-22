import uvicorn
from infrastructure.api.controllers import app


def main():
    print("Starting Telegnize API Server on http://0.0.0.0:8000...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
