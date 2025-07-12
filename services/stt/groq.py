import os
import io
from pydub import AudioSegment
from fastapi import WebSocket
from services.llm.openai_async import LargeLanguageModel
from groq import Groq


class GroqTranscriber:
    def __init__(self, llm_instance: LargeLanguageModel, websocket: WebSocket, stream_sid):
        self.llm = llm_instance
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        self.audio_buffer = bytearray()
        self.chunk_duration = 3 # Seconds of audio before transcription
        self.sample_rate = 8000 # Twilio's sample rate
        self.chunk_size = self.sample_rate * self.chunk_duration # bytes for 3 seconds


    async def process_audio(self, audio_data):
        """Add audio data to buffer and transcribe when enough data is collected"""
        self.audio_buffer.extend(audio_data)
        
        # Process when we have enough audio (3 seconds worth)
        if len(self.audio_buffer) >= self.chunk_size:
            await self.transcribe_chunk()
            
    async def transcribe_chunk(self):
        """Send buffered audio to Groq for transcription"""
        if len(self.audio_buffer) == 0:
            return
            
        try:
            # Convert mu-law audio to WAV format for Groq
            wav_data = self.mulaw_to_wav(bytes(self.audio_buffer))
            
            # Create file-like object
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"
            
            # Send to Groq
            transcription = self.client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3-turbo",  # or "whisper-large-v3"
                response_format="json",
                language="en"  # optional, let Groq detect if you prefer
            )
            
            if transcription.text.strip():
                print(f"User: {transcription.text}")
                # Send to your LLM for processing
                await self.llm.run_chat(transcription.text)
                
        except Exception as e:
            print(f"Groq transcription error: {e}")
        finally:
            # Clear the buffer
            self.audio_buffer = bytearray()
    
    def mulaw_to_wav(self, mulaw_data):
        """Convert mu-law audio data to WAV format using pydub"""
        try:
            # Create AudioSegment from raw mu-law data
            audio = AudioSegment(
                data=mulaw_data,
                sample_width=1,  # mu-law is 8-bit
                frame_rate=8000,  # Twilio sample rate
                channels=1       # mono
            )
            
            # Convert to 16-bit PCM for better compatibility
            audio = audio.set_sample_width(2)
            
            # Export to WAV format in memory
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            print(f"Audio conversion error: {e}")
            # Fallback: create a simple WAV header and use raw data
            return self.create_simple_wav(mulaw_data)
    
    async def force_transcribe(self):
        """Force transcription of remaining buffer (called on stop)"""
        if len(self.audio_buffer) > 0:
            await self.transcribe_chunk()