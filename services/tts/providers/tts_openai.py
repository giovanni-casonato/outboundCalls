import base64
import json
import audioop
from fastapi import WebSocket
from openai import AsyncOpenAI
from services.tts.tts_provider import TTSProvider

class OpenAITTS(TTSProvider):
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
                        
                        # Convert chunk from PCM to mu-law
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
        
    def _convert_pcm_to_mulaw(self, pcm_data, from_rate=24000, to_rate=8000):
        """
        Convert PCM audio data to mu-law encoding suitable for Twilio
        
        Args:
            pcm_data: PCM audio data (bytes or bytearray)
            from_rate: Sample rate of the input PCM (default: 24kHz for OpenAI)
            to_rate: Target sample rate (default: 8kHz for Twilio)
            
        Returns:
            bytes: mu-law encoded audio data at 8kHz
        """
        try:
            # First downsample from 24kHz to 8kHz (assuming 16-bit PCM)
            # 2 bytes per sample for 16-bit PCM
            resampled = audioop.ratecv(bytes(pcm_data), 2, 1, from_rate, to_rate, None)[0]
            
            # Then convert to 8-bit mu-law
            mulaw_data = audioop.lin2ulaw(resampled, 2)
            
            return mulaw_data
        except Exception as e:
            print(f"Error converting PCM to mu-law: {str(e)}")
            # Return original data if conversion fails
            return pcm_data