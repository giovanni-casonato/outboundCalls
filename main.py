import os
import json
from twilio.rest import Client
from fastapi import FastAPI, Request, WebSocket, Response, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

# Serve static files (CSS, JS, etc.)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Twilio setup
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@app.get("/")
async def get_home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "twilio_number": TWILIO_PHONE_NUMBER or 'Twilio Number Not Set'
    })


@app.post("/make-call")
async def make_call(to_number: str = Form(...)):
    try:
        call = client.calls.create(
            from_=TWILIO_PHONE_NUMBER,
            to=to_number,
            url="http://demo.twilio.com/docs/classic.mp3",
            # url="https://orca-app-se5sx.ondigitalocean.app/twiml/instructions"
        )

        return {
            "success": True,
            "call_id": call.sid,
            "to": to_number,
            "status": call.status
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/twiml/instructions")
async def call_instructions():
    return Response(
        content=f'''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
        
            <Start>
                <Stream url="wss://orca-app-se5sx.ondigitalocean.app/twilio"/>
            </Start>
        </Response>''',
        media_type="application/xml"
    )


@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            print(f"Received: {message}")

            if message["event"] == "connected":
                print("Twilio connected")

            elif message["event"] == "connected":
                print("Twilio connected")

            elif message["event"] == "start":
                print(f"Call started: {message['start']['callSid']}")

            elif message["event"] == "media":
                print(f"Audio data received")

            elif message["event"] == "stop":
                print("Call ended")

    except Exception as e:
        print(f"Websocket error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)