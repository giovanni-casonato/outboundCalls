# services/tts/providers/tts_elevenlabs.py
import os
import json
import base64
import httpx
import numpy as np
from fastapi import WebSocket
from ..tts_provider import TTSProvider

class ElevenLabsTTS(TTSProvider):
    def __init__(self, ws: WebSocket, stream_sid):
        super().__init__(ws, stream_sid)
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ElevenLabs API key not found.")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Default voice: Rachel
        self.model_id = "eleven_turbo_v2"
        self.base_url = "https://api.elevenlabs.io/v1"
        
    def pcm_to_ulaw(self, pcm_data):
        """Convert 16-bit PCM to μ-law"""
        # Convert to numpy array
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Normalize to [-1, 1]
        normalized = audio_array.astype(np.float32) / 32768.0
        
        # Apply μ-law compression
        mu = 255.0
        sign = np.sign(normalized)
        magnitude = np.abs(normalized)
        
        # μ-law formula
        compressed = sign * np.log(1 + mu * magnitude) / np.log(1 + mu)
        
        # Convert to 8-bit unsigned (0-255)
        ulaw_int = ((compressed + 1) * 127.5).astype(np.uint8)
        
        return ulaw_int.tobytes()
        
    async def get_audio_from_text(self, text: str) -> bool:
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/text-to-speech/{self.voice_id}",
                    headers=headers,
                    json=payload,
                    timeout=10.0
                )
                
            if response.status_code == 200:
                # Process the audio data for Twilio
                audio_data = response.content
                
                # Convert to mu-law encoding
                mulaw_data = self.pcm_to_ulaw(audio_data)
                
                # Encode to base64 for Twilio
                payload_b64 = base64.b64encode(mulaw_data).decode('utf-8')
                
                # Send to Twilio WebSocket
                await self.ws.send_text(json.dumps({
                    'event': 'media',
                    'streamSid': f"{self.stream_sid}",
                    'media': {'payload': payload_b64}
                }))
                
                return True
            else:
                print(f"ElevenLabs API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error in ElevenLabs TTS: {str(e)}")
            return False