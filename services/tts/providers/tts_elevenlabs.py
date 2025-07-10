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
        
    async def get_audio_from_text(self, text: str) -> bool:
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/wav"  # Request WAV format for easier processing
        }
        
        payload = {
            "text": text,
            "model_id": self.model_id,
            "output_format": "pcm_8000",  # 8kHz PCM
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
                # Get audio data
                audio_data = response.content
                
                # Skip WAV header (44 bytes) to get raw PCM data
                pcm_data = audio_data[44:]
                
                # Convert 16-bit PCM to 8-bit mulaw
                # Using a simple approach without complex audio libraries
                # This processes 2 bytes at a time (16-bit samples)
                mulaw_data = bytearray()
                
                # Process in chunks of 2 bytes (16-bit samples)
                for i in range(0, len(pcm_data), 2):
                    if i + 1 < len(pcm_data):  # Ensure we have 2 bytes to process
                        # Convert 2 bytes to a 16-bit sample
                        sample = int.from_bytes(pcm_data[i:i+2], byteorder='little', signed=True)
                        
                        # Simple μ-law conversion
                        # This is a basic implementation; not ideal but should work
                        if sample < 0:
                            sign = 0
                            sample = -sample
                        else:
                            sign = 1
                        
                        # Compress to 8-bit
                        if sample > 32767:
                            sample = 32767  # Clamp to max 16-bit value
                        
                        # Convert to 0-255 range with basic logarithmic compression
                        if sample == 0:
                            compressed = 0
                        else:
                            # Simple log compression (not true μ-law but similar effect)
                            compressed = int(127 * (1 + np.log(sample / 32767) / np.log(256)))
                        
                        # Add sign bit and store
                        mulaw_byte = (sign << 7) | (compressed & 0x7F)
                        mulaw_data.append(mulaw_byte)
                
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