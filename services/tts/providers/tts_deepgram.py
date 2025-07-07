import os
import base64
import json
import httpx
from fastapi import WebSocket
from ..tts_provider import TTSProvider

class DeepgramTTS(TTSProvider):
    def __init__(self, ws: WebSocket, stream_sid):
        # initializing websocket connection
        super().__init__(ws, stream_sid)
        self.url = "https://api.deepgram.com/v1/speak?model=aura-2-amalthea-en"
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("Deepgram API key not found.")
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

    async def get_audio_from_text(self, text):
        payload = {"text": text}
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, headers=self.headers, json=payload, params={"encoding": "mulaw"})

        if response.status_code == 200:
            audio_data = response.content
            audio_data = audio_data[400:]
            payload_b64 = base64.b64encode(audio_data).decode('utf-8')
    
            # sending tts audio back to twilio
            await self.ws.send_text(json.dumps({
                'event': 'media',
                'streamSid': f"{self.stream_sid}",
                'media': {'payload': payload_b64}
                }))  
            return True
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return False