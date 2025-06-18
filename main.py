import os
import json
from twilio.rest import Client
from fastapi import FastAPI, Request, WebSocket, Response, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging

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


@app.get("/debug/twilio")
async def debug_twilio():
    """Debug endpoint to check Twilio configuration"""
    if not client:
        return {"error": "Twilio client not initialized", "configured": False}
    
    try:
        # Test account access
        account = client.api.accounts(TWILIO_ACCOUNT_SID).fetch()
        
        # Get phone number details
        phone_numbers = client.incoming_phone_numbers.list(limit=10)
        twilio_number_info = None
        
        for number in phone_numbers:
            if number.phone_number == TWILIO_PHONE_NUMBER:
                twilio_number_info = {
                    "phone_number": number.phone_number,
                    "capabilities": {
                        "voice": number.capabilities.get('voice', False),
                        "sms": number.capabilities.get('sms', False)
                    },
                    "status": number.status
                }
                break
        
        return {
            "configured": True,
            "account_status": account.status,
            "account_type": account.type,
            "twilio_number": TWILIO_PHONE_NUMBER,
            "twilio_number_info": twilio_number_info,
            "total_phone_numbers": len(phone_numbers)
        }
        
    except Exception as e:
        logger.error(f"Twilio debug failed: {str(e)}")
        return {
            "error": str(e),
            "configured": False,
            "twilio_number": TWILIO_PHONE_NUMBER
        }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)