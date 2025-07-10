from fastapi import WebSocket
from .tts_provider import TTSProvider
from services.tts.providers.tts_deepgram import DeepgramTTS
from services.tts.providers.tts_openai import OpenAITTS
from services.tts.providers.tts_elevenlabs import ElevenLabsTTS

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
        providers = {
            "deepgram": DeepgramTTS,
            "openai": OpenAITTS,
            "elevenlabs": ElevenLabsTTS,
        }

        provider_class = providers.get(provider_name.lower())
        if provider_class:
            return provider_class(ws, stream_sid, **kwargs)
        else:
            available_providers = ", ".join(providers.keys())
            raise ValueError(f"Unsupported TTS provider: {provider_name}. Available providers: {available_providers}")