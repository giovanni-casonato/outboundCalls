from fastapi import WebSocket
from .tts_provider import TTSProvider
from tts.providers.tts_deepgram import DeepgramTTS
from tts.providers.tts_openai import OpenaiTTS

class TTSFactory:
    """
    Factory class to create TTS provider instances based on configuration.
    """
    @staticmethod
    def create_tts_provider(provider_name: str, ws: WebSocket, stream_sid: str, **kwargs) -> TTSProvider:
        """
        Create a TTS provider instance based on the provider name.
        
        Args:
            provider_name: The name of the TTS provider to create
            ws: WebSocket connection
            stream_sid: Stream SID for Twilio
            **kwargs: Additional provider-specific parameters
            
        Returns:
            TTSProvider: An instance of the requested TTS provider
            
        Raises:
            ValueError: If the provider name is not recognized
        """
        if provider_name.lower() == "deepgram":
            return DeepgramTTS(ws, stream_sid)
        elif provider_name.lower() == "openai":
            return OpenaiTTS(ws, stream_sid)
        else:
            raise ValueError(f"Unsupported TTS provider: {provider_name}")