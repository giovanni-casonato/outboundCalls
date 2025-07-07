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
                    pcm_buffer.extend(chunk)
            
            # Convert all PCM data to μ-law at once
            mulaw_data = self._convert_pcm_to_mulaw(bytes(pcm_buffer))
            
            # Send in 160-byte chunks (20ms at 8kHz μ-law)
            chunk_size = 160
            for i in range(0, len(mulaw_data), chunk_size):
                audio_chunk = mulaw_data[i:i + chunk_size]
                
                # Pad last chunk if needed
                if len(audio_chunk) < chunk_size:
                    audio_chunk += b'\x7F' * (chunk_size - len(audio_chunk))
                
                payload_b64 = base64.b64encode(audio_chunk).decode('utf-8')
                
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
        Assumes 16-bit PCM input at 8kHz sample rate.
        """
        import numpy as np
        
        try:
            # Ensure we have an even number of bytes (complete 16-bit samples)
            if len(pcm_data) % 2 != 0:
                # Pad with a zero byte if odd length
                pcm_data = pcm_data + b'\x00'
            
            # Convert bytes to numpy array of 16-bit signed integers
            pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            # Convert to μ-law using the standard μ-law compression algorithm
            # First normalize to [-1, 1] range
            normalized = pcm_array.astype(np.float32) / 32768.0
            
            # Apply μ-law compression
            mu = 255.0
            sign = np.sign(normalized)
            magnitude = np.abs(normalized)
            
            # μ-law formula: sign * log(1 + μ * |x|) / log(1 + μ)
            compressed = sign * np.log(1 + mu * magnitude) / np.log(1 + mu)
            
            # Convert to 8-bit μ-law values (0-255)
            mulaw_values = np.clip(compressed * 127 + 128, 0, 255).astype(np.uint8)
            
            return mulaw_values.tobytes()
            
        except Exception as e:
            # Handle any conversion errors
            print(f"PCM to μ-law conversion error: {e}")
            # Return silence (μ-law 0x7F is silence)
            return b'\x7F' * (len(pcm_data) // 2)  # Half the length since μ-law is 8-bit