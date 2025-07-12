import os
import asyncio
import json
from fastapi import WebSocket
from typing import Optional
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions
)
from services.llm.openai_async import LargeLanguageModel


class DeepgramTranscriber:
    """Real-time speech transcription using Deepgram API"""
    
    def __init__(self, llm_instance: LargeLanguageModel, websocket: WebSocket, stream_sid: str):
        self.llm = llm_instance
        self.websocket = websocket
        self.stream_sid = stream_sid
        self.dg_connection = None
        self.deepgram_client = None
        self.is_connected = False
        self.is_finals = []
        
    async def deepgram_connect(self):
        """Initialize connection to Deepgram"""
        try:
            # Configure Deepgram client
            config = DeepgramClientOptions(
                options={
                    "keepalive": "true"}
            )
            
            self.deepgram_client = DeepgramClient("", config)
            
            # Create live transcription connection
            self.dg_connection = self.deepgram_client.listen.asyncwebsocket.v("1")
            
            # Set up event handlers
            self.dg_connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, self._on_message)
            self.dg_connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.dg_connection.on(LiveTranscriptionEvents.Close, self._on_close)
            self.dg_connection.on(LiveTranscriptionEvents.Warning, self._on_warning)

            # Deepgram configuration for Twilio audio
            options = LiveOptions(
                model="nova-3",                # Latest high-accuracy model
                language="en-US",
                encoding="mulaw",              # Twilio uses μ-law encoding
                sample_rate=8000,             # Twilio sample rate
                channels=1,                   # Mono audio
                punctuate=True,
                interim_results=True,
                endpointing="300ms",          # Voice activity detection
                smart_format=True,
                profanity_filter=False,
                redact=False,
                diarize=False,               # Set to True if you want speaker detection
                multichannel=False,
            )

            addons = {
                "no_delay": "true"
            }

            # Start connection using the exact pattern from official example
            if await self.dg_connection.start(options, addons=addons) is False:
                print("❌ Failed to connect to Deepgram")
                return False
            
            print(f"✅ Successfully connected to Deepgram for stream {self.stream_sid}")
            self.is_connected = True
            return True
            
        except Exception as e:
            print(f"❌ Error connecting to Deepgram: {e}")
            print(f"❌ Error type: {type(e).__name__}")
            return False
            

    async def _on_open(self, *args, **kwargs):
        """Called when Deepgram connection opens"""
        print("✅ Deepgram WebSocket opened")
        

    async def _on_message(self, result, **kwargs):
        """Handle transcription results - adapted from official example"""
        try:
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
                
            if result.is_final:
                # Collect finals like in official example
                self.is_finals.append(sentence)
                
                # Speech Final means we have detected sufficient silence
                if result.speech_final:
                    utterance = " ".join(self.is_finals)
                    print(f"📝 [{self.stream_sid}] Speech Final: {utterance}")
                    
                    # Send complete utterance to LLM
                    await self._process_final_transcript(utterance)
                    self.is_finals = []
                else:
                    # These are useful for real-time captioning
                    print(f"📝 [{self.stream_sid}] Is Final: {sentence}")
            else:
                # Interim results for real-time feedback
                print(f"📝 [{self.stream_sid}] Interim: {sentence}")
                
        except Exception as e:
            print(f"❌ Error processing transcript: {e}")

            
    async def _on_error(self, *args, **kwargs):
        """Handle Deepgram errors"""
        error = kwargs.get("error")
        print(f"❌ Deepgram error: {error}")
        
    async def _on_close(self, *args, **kwargs):
        """Handle Deepgram connection close"""
        print(f"🔌 Deepgram connection closed for stream {self.stream_sid}")
        self.is_connected = False
        
    async def _on_warning(self, *args, **kwargs):
        """Handle Deepgram warnings"""
        warning = kwargs.get("warning")
        print(f"⚠️ Deepgram warning: {warning}")
        
    async def _handle_transcript(self, transcript: str, is_final: bool, confidence: float):
        """Process transcript and send to LLM if final"""
        if is_final and transcript.strip():
            print(f"🤖 Sending to LLM: '{transcript}' (confidence: {confidence:.2f})")
            
            # Send to your LLM for processing
            try:
                await self.llm.run_chat(transcript)
            except Exception as e:
                print(f"❌ Error sending to LLM: {e}")
        elif not is_final:
            # You can handle interim results here if needed
            # For example, show typing indicators, real-time feedback, etc.
            pass
            
    async def _send_keepalive(self):
        """Send periodic keepalive messages to maintain connection"""
        while self.is_connected:
            try:
                await asyncio.sleep(5)  # Send every 5 seconds
                if self.dg_connection and self.is_connected:
                    keepalive_msg = {"type": "KeepAlive"}
                    await self.dg_connection.send(json.dumps(keepalive_msg))
            except Exception as e:
                print(f"❌ Keepalive error: {e}")
                break
                
    async def send_audio(self, audio_data: bytes):
        """Send audio data to Deepgram (alternative to using dg_connection.send directly)"""
        if self.dg_connection and self.is_connected:
            try:
                await self.dg_connection.send(audio_data)
            except Exception as e:
                print(f"❌ Error sending audio to Deepgram: {e}")
                
    async def deepgram_close(self):
        """Close Deepgram connection"""
        self.is_connected = False
        if self.dg_connection:
            try:
                await self.dg_connection.finish()
                print(f"🔌 Deepgram connection closed for stream {self.stream_sid}")
            except Exception as e:
                print(f"❌ Error closing Deepgram connection: {e}")
