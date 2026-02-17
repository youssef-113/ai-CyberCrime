from fastapi import FastAPI

app = FastAPI(title="AI Cybercrime Evidence Builder")

@app.get("/")
def root():
    return {"message": "Cybercrime AI Backend Running"}
