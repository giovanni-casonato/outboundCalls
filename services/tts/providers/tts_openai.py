# services/tts/providers/tts_openai.py
import os
import json
import base64
import io
from fastapi import WebSocket
from ..tts_provider import TTSProvider
from openai import OpenAI
from pydub import AudioSegment
from pydub.utils import make_chunks

class OpenAITTS(TTSProvider):
    def __init__(self, ws: WebSocket, stream_sid):
        super().__init__(ws, stream_sid)
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found.")
        self.client = OpenAI(api_key=self.api_key)
        
    def convert_to_mulaw_8khz(self, audio_data: bytes, input_format: str = "wav") -> bytes:
        """
        Convert audio data to μ-law 8kHz format for Twilio using pydub
        """
        try:
            # Load audio with pydub
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=input_format)
            
            # Convert to mono and 8kHz
            audio = audio.set_channels(1)  # Convert to mono
            audio = audio.set_frame_rate(8000)  # Set to 8kHz
            audio = audio.set_sample_width(2)  # Set to 16-bit
            
            # Export as μ-law encoded audio
            output_buffer = io.BytesIO()
            
            # Export as raw μ-law data (no WAV header)
            audio.export(output_buffer, format="raw", codec="pcm_mulaw")
            
            # Get the raw μ-law data
            output_buffer.seek(0)
            mulaw_data = output_buffer.read()
            
            return mulaw_data
                    
        except Exception as e:
            print(f"Error converting audio to μ-law: {str(e)}")
            raise
    
    async def get_audio_from_text(self, text: str) -> bool:
        try:
            # Generate audio using OpenAI TTS
            response = self.client.audio.speech.create(
                model="tts-1",  # or "tts-1-hd" for higher quality
                voice="alloy",  # or "echo", "fable", "onyx", "nova", "shimmer"
                input=text,
                response_format="wav"  # Get WAV format for easier conversion
            )
            
            # Get the audio data
            audio_data = response.content
            
            # Convert to μ-law 8kHz
            mulaw_data = self.convert_to_mulaw_8khz(audio_data, "wav")
            
            # For streaming, we need to chunk the data
            # Twilio typically expects chunks of about 160 bytes for μ-law at 8kHz
            chunk_size = 160
            
            for i in range(0, len(mulaw_data), chunk_size):
                chunk = mulaw_data[i:i + chunk_size]
                
                # Encode chunk to base64
                payload_b64 = base64.b64encode(chunk).decode('utf-8')
                
                # Send chunk to Twilio WebSocket
                await self.ws.send_text(json.dumps({
                    'event': 'media',
                    'streamSid': f"{self.stream_sid}",
                    'media': {'payload': payload_b64}
                }))
            
            return True
                
        except Exception as e:
            print(f"Error in OpenAI TTS: {str(e)}")
            return False
