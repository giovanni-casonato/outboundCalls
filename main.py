import os
import json
import base64
from twilio.rest import Client
from fastapi import FastAPI, Request, WebSocket, Response, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.tts.tts_factory import TTSFactory
from services.llm.openai_async import LargeLanguageModel
from services.stt.deepgram import DeepgramTranscriber

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

# Twilio sends audio data as 160 byte messages containing 20ms of audio each
# We buffer 5 twilio messages corresponding to 100 ms of audio
BUFFER_SIZE = 5 * 160
TWILIO_SAMPLE_RATE = 8000

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
            url="https://orca-app-se5sx.ondigitalocean.app/twiml/instructions"
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
            <Connect>
                <Stream url="wss://orca-app-se5sx.ondigitalocean.app/twilio"/>
            </Connect>
        </Response>''',
        media_type="application/xml"
    )


@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await websocket.accept()
    buffer = bytearray(b'')
    empty_byte_received = False
    try:
        async for message in websocket.iter_text():
            data = json.loads(message)
            match data['event']:
                case "start":
                    stream_sid = data['streamSid']
                    print(f"Call started for stream_sid: {stream_sid}")

                    text_to_speech = TTSFactory.create_tts_provider("openai", websocket, stream_sid)                    
                    await text_to_speech.get_audio_from_text(f"Hello?!")

                    openai_llm = LargeLanguageModel(text_to_speech)
                    openai_llm.init_chat()

                    deepgram_transcriber = DeepgramTranscriber(openai_llm, websocket, stream_sid)
                    await deepgram_transcriber.deepgram_connect()

                case "connected":
                    print('Websocket connected')

                case "media":
                    # sending audio to deepgram websocket
                    payload_b64 = data['media']['payload']
                    payload_mulaw = base64.b64decode(payload_b64)
                    buffer.extend(payload_mulaw)
                    if payload_mulaw == b'':
                        empty_byte_received = True
                    if len(buffer) >= BUFFER_SIZE or empty_byte_received:
                        await deepgram_transcriber.dg_connection.send(buffer)
                        buffer = bytearray(b'')
                
                case "stop":
                    await deepgram_transcriber.deepgram_close()
                    print("Stop message received")

    except Exception as e:
        print(f"Websocket error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)