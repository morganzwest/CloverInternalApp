import os
import sys
import asyncio
import uvicorn
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.main import app

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port,
                loop="asyncio", http="h11", reload=False)
