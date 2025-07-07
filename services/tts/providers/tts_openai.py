import base64
import json
import numpy as np
from fastapi import WebSocket
from openai import AsyncOpenAI
from ..tts_provider import TTSProvider

class OpenaiTTS(TTSProvider):
    def __init__(self, ws: WebSocket, stream_sid: str):
        super().__init__(ws, stream_sid)
        self.client = AsyncOpenAI()
    
    def resample_audio(self, audio_data, original_rate, target_rate):
        """Simple resampling using numpy"""
        # Convert bytes to numpy array (16-bit PCM)
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        
        # Calculate resampling ratio
        ratio = target_rate / original_rate
        
        # Simple linear interpolation resampling
        original_length = len(audio_array)
        target_length = int(original_length * ratio)
        
        # Create new indices for interpolation
        original_indices = np.arange(original_length)
        target_indices = np.linspace(0, original_length - 1, target_length)
        
        # Interpolate
        resampled = np.interp(target_indices, original_indices, audio_array)
        
        return resampled.astype(np.int16).tobytes()
    
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
            
            # Convert PCM to Twilio's required format
            if pcm_buffer:
                # Resample from 24kHz to 8kHz
                resampled_audio = self.resample_audio(
                    bytes(pcm_buffer), 24000, 8000
                )
                
                # Convert to μ-law
                ulaw_audio = self.pcm_to_ulaw(resampled_audio)
                
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