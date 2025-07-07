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
            # Buffer for accumulating chunks
            buffer = bytearray()
            buffer_size = 1280  # 80ms at 8kHz, 16-bit - adjust as needed for Twilio

            async with self.client.audio.speech.with_streaming_response.create(
                model="gpt-4o-mini-tts",
                voice="coral",
                input=text,
                instructions="Speak in a cheerful and positive tone.",
                response_format="pcm",
            ) as response:
                async for chunk in response.iter_bytes():
                    buffer.extend(chunk)
                    
                    # Process buffer when it reaches sufficient size
                    while len(buffer) >= buffer_size:
                        # Take a chunk from the buffer
                        chunk_to_process = buffer[:buffer_size]
                        buffer = buffer[buffer_size:]
                        
                        # Convert PCM to μ-law for Twilio
                        mulaw_chunk = self._convert_pcm_to_mulaw(chunk_to_process)

                        # Encode as base64
                        payload_b64 = base64.b64encode(mulaw_chunk).decode('utf-8')
                        
                        # Send to Twilio
                        await self.ws.send_text(json.dumps({
                            'event': 'media', 
                            'streamSid': self.stream_sid, 
                            'media': {'payload': payload_b64}
                        }))
                
                # Process any remaining data in the buffer
                if buffer:
                    mulaw_chunk = self._convert_pcm_to_mulaw(buffer)
                    payload_b64 = base64.b64encode(mulaw_chunk).decode('utf-8')
                    
                    await self.ws.send_text(json.dumps({
                        'event': 'media', 
                        'streamSid': self.stream_sid, 
                        'media': {'payload': payload_b64}
                    }))
            
            return True
            
        except Exception as e:
            print(f"Error in OpenAI TTS streaming: {str(e)}")
            return False
        
    def _convert_pcm_to_mulaw(self, pcm_data: bytes) -> bytes:
        """
        Convert PCM audio data to μ-law format required by Twilio.
        This is a placeholder - you'll need to implement the actual conversion.
        """
        # This is a simplified placeholder implementation
        # You'll need to use a proper audio library like audioop or pydub
        import audioop
        
        # Convert PCM to μ-law (assuming 16-bit PCM input)
        return audioop.lin2ulaw(pcm_data, 2)  # 2 = 16-bit samples