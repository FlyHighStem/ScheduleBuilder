from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()

# This tells FastAPI: "When someone visits the home page (/), run this function"
@app.get("/")
def serve_dashboard():
    # This points directly to the HTML file in your Frontend folder
    return FileResponse("Frontend/homepage.html")