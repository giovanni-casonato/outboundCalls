import base64
import json
import numpy as np
from fastapi import WebSocket
from openai import AsyncOpenAI
from pydub import AudioSegment
from ..tts_provider import TTSProvider

class OpenaiTTS(TTSProvider):
    def __init__(self, ws: WebSocket, stream_sid: str):
        super().__init__(ws, stream_sid)
        self.client = AsyncOpenAI()
        
    async def get_audio_from_text(self, text: str) -> bool:
        try:
            # Accumulate all PCM data first
            pcm_buffer = bytearray()

            async with self.client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice="coral",
                input=text,
                instructions="Speak in a cheerful and positive tone.",
                response_format="pcm",
            ) as response:
                # Read the streaming PCM data
                async for chunk in response.iter_bytes():
                    if chunk:
                        pcm_buffer.extend(chunk)
            
            # Convert PCM to Twilio's required format using pydub
            if pcm_buffer:
                # Create AudioSegment from OpenAI's PCM (24kHz, 16-bit, mono)
                audio = AudioSegment(
                    data=pcm_buffer,
                    sample_width=2,  # 16-bit = 2 bytes
                    frame_rate=24000,  # OpenAI's sample rate
                    channels=1
                )
                
                # Resample to 8kHz for Twilio
                audio_8k = audio.set_frame_rate(8000)
                
                # Convert to μ-law
                ulaw_audio = pcm_to_ulaw(audio_8k.raw_data)
                
                # Encode to base64 for Twilio
                audio_base64 = base64.b64encode(ulaw_audio).decode('utf-8')
                
                # Send to Twilio WebSocket
                media_message = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {
                        "payload": audio_base64
                    }
                }
                
                await self.ws.send_text(json.dumps(media_message))
                
            return True

        except Exception as e:
            print(f"Error in OpenAI TTS streaming: {str(e)}")
            return False
        

def pcm_to_ulaw(pcm_data, sample_width=2):
    """Convert PCM to μ-law using numpy"""
    # Convert bytes to numpy array
    if sample_width == 2:
        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
    else:
        audio_array = np.frombuffer(pcm_data, dtype=np.int8)
    
    # Normalize to [-1, 1]
    audio_float = audio_array.astype(np.float32) / 32768.0
    
    # Apply μ-law compression
    mu = 255.0
    audio_ulaw = np.sign(audio_float) * np.log(1 + mu * np.abs(audio_float)) / np.log(1 + mu)
    
    # Convert back to 8-bit unsigned
    audio_ulaw_int = ((audio_ulaw + 1) * 127.5).astype(np.uint8)
    
    return audio_ulaw_int.tobytes()
         