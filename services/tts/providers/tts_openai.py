import os
import io
import base64
import json
import numpy as np
from scipy.io import wavfile
from fastapi import WebSocket
from ..tts_provider import TTSProvider
from openai import OpenAI
from scipy.signal import resample

class OpenAITTS(TTSProvider):
    def __init__(self, ws: WebSocket, stream_sid):
        super().__init__(ws, stream_sid)
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found.")
        self.client = OpenAI(api_key=self.api_key)
    
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
        
    def linear_to_mulaw(self, linear_sample):
        '''Convert a 16-bit linear PCM sample to μ-law'''
        BIAS = 0x84
        CLIP = 32635
        
        if linear_sample < 0:
            linear_sample = -linear_sample
            sign = 0x80
        else:
            sign = 0x00
            
        if linear_sample > CLIP:
            linear_sample = CLIP
            
        linear_sample += BIAS
        
        exponent = 7
        for i in range(7):
            if linear_sample <= (0x1F << (exponent + 2)):
                break
            exponent -= 1
            
        mantissa = (linear_sample >> (exponent + 3)) & 0x0F
        mulaw_sample = ~(sign | (exponent << 4) | mantissa)
        
        return mulaw_sample & 0xFF
        
    def convert_to_mulaw_8khz(self, audio_data: bytes, input_format: str = "wav") -> bytes:
        '''
        Convert audio data to μ-law 8kHz format using numpy/scipy
        '''
        try:
            # Read WAV data using scipy
            sample_rate, audio_array = wavfile.read(io.BytesIO(audio_data))
            
            # Convert to float for processing
            if audio_array.dtype == np.int16:
                audio_array = audio_array.astype(np.float32) / 32768.0
            elif audio_array.dtype == np.int32:
                audio_array = audio_array.astype(np.float32) / 2147483648.0
            elif audio_array.dtype == np.uint8:
                audio_array = (audio_array.astype(np.float32) - 128) / 128.0
            
            # Convert stereo to mono
            if audio_array.ndim == 2:
                audio_array = np.mean(audio_array, axis=1)
            
            # Resample to 8kHz if needed
            if sample_rate != 8000:
                num_samples = int(len(audio_array) * 8000 / sample_rate)
                audio_array = resample(audio_array, num_samples)
            
            # Convert back to 16-bit integers
            audio_array = np.clip(audio_array * 32767, -32768, 32767).astype(np.int16)
            
            # Convert to μ-law
            mulaw_data = bytes([self.linear_to_mulaw(sample) for sample in audio_array])
            
            return mulaw_data
            
        except Exception as e:
            print(f"Error converting audio with numpy: {str(e)}")
            raise