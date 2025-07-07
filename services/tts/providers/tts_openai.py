import base64
import json
from fastapi import WebSocket
from openai import AsyncOpenAI
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
                async for chunk in response.iter_bytes():
                    if chunk:
                        pcm_buffer.extend(chunk)

                
                if pcm_buffer:
                    audio_base64 = base64.b64encode(pcm_buffer).decode('utf-8')
            
                    # sending tts audio back to twilio
                    await self.ws.send_text(json.dumps({
                        'event': 'media',
                        'streamSid': f"{self.stream_sid}",
                        'media': {'payload': audio_base64}
                        }))  
                    return True
                else:
                    print(f"Error: {response.status_code} - {response.text}")
                    return False
                
        
        except Exception as e:
            print(f"Error in OpenAI TTS streaming: {str(e)}")
            return False
    
         